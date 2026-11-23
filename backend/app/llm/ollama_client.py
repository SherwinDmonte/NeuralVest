"""One shared client for the local Ollama server (architecture §10, decisions in tasks.md 1.4.5).

Design for an 8 GB RAM, CPU-only machine:
  * one process-wide lock, so two inferences never run at the same time;
  * thinking mode off (`think: false`) and small context (`num_ctx`);
  * free-RAM check before each call: below LLM_MIN_FREE_RAM_MB the smaller model is used;
  * `unload()` releases the model after a workflow (`keep_alive: 0`).

Failure ladder for every request (architecture §3.4):
  primary model -> retry once (with a repair hint if the JSON was invalid)
  -> fallback model (if configured) -> retry once -> deterministic template.
The caller always gets a result, and `source` says which step produced it.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

import httpx
import psutil
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.llm.guards import strip_thinking, suspicious_text, unsupported_numbers
from app.llm.prompts import PromptSpec

logger = logging.getLogger("neuralvest.llm")

T = TypeVar("T", bound=BaseModel)

# Process-wide: every OllamaClient instance shares it, so inference is always serialized.
_INFERENCE_LOCK = threading.Lock()


class LLMCallError(Exception):
    """One attempt failed. `retryable=False` means trying the same model again is pointless."""

    def __init__(self, reason: str, retryable: bool = True) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable


@dataclass
class LLMResult(Generic[T]):
    value: T
    source: Literal["llm", "template"]
    model: str | None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    eval_tokens: int | None = None
    tokens_per_second: float | None = None

    @property
    def used_fallback(self) -> bool:
        """True when the answer is not from the primary model on its first try."""
        return self.source == "template" or len(self.attempts) > 1

    def metadata(self) -> dict[str, Any]:
        """Compact record for agent outputs (e.g. the `llm` field of an agent result)."""
        return {"source": self.source, "model": self.model, "used_fallback": self.used_fallback,
                "attempts": self.attempts, "duration_seconds": round(self.duration_seconds, 2),
                "tokens_per_second": self.tokens_per_second}


def available_ram_mb() -> float:
    return psutil.virtual_memory().available / 1024**2


class OllamaClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None,
                 ram_probe: Callable[[], float] = available_ram_mb) -> None:
        self.settings = settings or get_settings()
        self._ram_probe = ram_probe
        self._http = httpx.Client(base_url=self.settings.ollama_base_url, transport=transport,
                                  timeout=httpx.Timeout(self.settings.llm_timeout_seconds, connect=5.0))

    # ---------------------------------------------------------------- housekeeping
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def is_available(self) -> bool:
        try:
            return self._http.get("/api/version", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False

    def installed_models(self) -> list[str]:
        try:
            return [m["name"] for m in self._http.get("/api/tags", timeout=5).json().get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError):
            return []

    def unload(self) -> list[str]:
        """Unload every loaded model to free RAM (call after each workflow)."""
        unloaded = []
        try:
            loaded = [m["name"] for m in self._http.get("/api/ps", timeout=5).json().get("models", [])]
        except (httpx.HTTPError, ValueError):
            return unloaded
        for name in loaded:
            try:
                self._http.post("/api/generate", json={"model": name, "keep_alive": 0}, timeout=15)
                unloaded.append(name)
            except httpx.HTTPError:
                logger.warning("Could not unload %s", name)
        return unloaded

    # ---------------------------------------------------------------- model choice
    def model_ladder(self) -> list[str]:
        """Models to try, in order. Low free RAM skips straight to the fallback model."""
        primary, fallback = self.settings.llm_primary_model, self.settings.llm_fallback_model
        ladder = [primary] + ([fallback] if fallback and fallback != primary else [])
        free = self._ram_probe()
        if len(ladder) > 1 and free < self.settings.llm_min_free_ram_mb:
            logger.warning("Low free RAM (%.0f MB): using %s instead of %s", free, fallback, primary)
            ladder = [fallback]
        return ladder

    # ---------------------------------------------------------------- one request
    def _chat_once(self, model: str, messages: list[dict], spec: PromptSpec, json_schema: dict | None) -> dict:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": self.settings.llm_keep_alive,
            "options": {"num_ctx": self.settings.llm_num_ctx, "temperature": self.settings.llm_temperature,
                        "num_predict": spec.max_tokens},
        }
        if json_schema is not None:
            payload["format"] = json_schema  # Ollama structured output: constrained to this schema
        try:
            with _INFERENCE_LOCK:
                resp = self._http.post("/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMCallError("timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMCallError(f"connection error: {exc.__class__.__name__}", retryable=False) from exc
        if resp.status_code == 404:
            raise LLMCallError(f"model '{model}' is not installed (run: ollama pull {model})", retryable=False)
        if resp.status_code != 200:
            raise LLMCallError(f"HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as exc:
            raise LLMCallError("invalid response from Ollama") from exc

    def _run(self, spec: PromptSpec, schema: type[T], parse: Callable[[str], T],
             fallback: Callable[[], T]) -> LLMResult[T]:
        started = time.perf_counter()
        attempts: list[dict[str, Any]] = []
        json_schema = schema.model_json_schema() if spec.json_output else None
        base_messages = [{"role": "system", "content": spec.system}, {"role": "user", "content": spec.user}]
        prompt_text = spec.system + "\n" + spec.user

        for model in self.model_ladder():
            messages = list(base_messages)
            for attempt in range(2):  # first try + one retry per model
                t0 = time.perf_counter()
                try:
                    data = self._chat_once(model, messages, spec, json_schema)
                    content = strip_thinking((data.get("message") or {}).get("content") or "")
                    if data.get("done_reason") == "length":
                        raise LLMCallError("output truncated (max tokens reached)")
                    value = parse(content)
                    for text in spec.guarded_text(value):
                        if problem := suspicious_text(text):
                            raise LLMCallError(f"invalid text: {problem}")
                    invented = unsupported_numbers(" ".join(spec.guarded_text(value)), prompt_text)
                    if invented:
                        raise LLMCallError(f"numbers not in the input: {invented[:5]}")
                except LLMCallError as exc:
                    attempts.append({"model": model, "ok": False, "reason": exc.reason,
                                     "seconds": round(time.perf_counter() - t0, 2)})
                    logger.warning("LLM %s attempt %d failed: %s", model, attempt + 1, exc.reason)
                    if not exc.retryable:
                        break
                    if exc.reason.startswith(("invalid", "numbers", "output")):
                        # Repair hint: tell the model exactly what was wrong.
                        messages = base_messages + [{"role": "user", "content": spec.repair_hint(exc.reason)}]
                    continue
                eval_count, eval_ns = data.get("eval_count"), data.get("eval_duration")
                attempts.append({"model": model, "ok": True, "seconds": round(time.perf_counter() - t0, 2)})
                return LLMResult(value=value, source="llm", model=model, attempts=attempts,
                                 duration_seconds=time.perf_counter() - started, eval_tokens=eval_count,
                                 tokens_per_second=round(eval_count / (eval_ns / 1e9), 1) if eval_count and eval_ns else None)

        logger.warning("LLM unavailable for '%s'; using deterministic template", spec.name)
        return LLMResult(value=fallback(), source="template", model=None, attempts=attempts,
                         duration_seconds=time.perf_counter() - started)

    # ---------------------------------------------------------------- public API
    def generate_structured(self, spec: PromptSpec, schema: type[T], fallback: Callable[[], T]) -> LLMResult[T]:
        """JSON output validated against `schema` (Pydantic)."""

        def parse(content: str) -> T:
            try:
                return schema.model_validate_json(content)
            except ValidationError:
                # Small models sometimes wrap JSON in prose; try the outermost {...} block once.
                start, end = content.find("{"), content.rfind("}")
                if start != -1 and end > start:
                    try:
                        return schema.model_validate(json.loads(content[start:end + 1]))
                    except (ValueError, ValidationError):
                        pass
                raise LLMCallError("invalid JSON for the expected schema") from None

        return self._run(spec, schema, parse, fallback)


_shared: OllamaClient | None = None
_shared_lock = threading.Lock()


def get_llm_client() -> OllamaClient:
    """The single shared client used by all agents."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = OllamaClient()
        return _shared
