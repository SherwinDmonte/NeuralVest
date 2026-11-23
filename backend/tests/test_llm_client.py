"""Ollama client behaviour against a mock Ollama server (no model needed)."""

import json
import threading
import time
from datetime import UTC, datetime

import httpx
import pytest

from app.config import Settings
from app.llm import prompts as p
from app.llm.ollama_client import OllamaClient

GOOD_NEWS = {"summary": "TCS shares rose after strong results.", "sentiment": "positive",
             "category": "quarterly_results", "relevance": "high"}


def settings(**overrides) -> Settings:
    base = dict(llm_primary_model="qwen3:1.7b", llm_fallback_model="qwen3:0.6b", llm_min_free_ram_mb=1500)
    return Settings(_env_file=None, **{**base, **overrides})


def chat_response(content: str, done_reason: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content},
                                     "done_reason": done_reason, "eval_count": 40, "eval_duration": 1_000_000_000})


def news_spec() -> p.PromptSpec:
    return p.news_analysis_prompt("Tata Consultancy Services Limited", "TCS.NS", "TCS Q2 results beat estimates",
                                  "Revenue grew.", "Mint", datetime(2026, 11, 20, tzinfo=UTC))


def run_news(handler, ram_mb: float = 4000, **overrides):
    client = OllamaClient(settings(**overrides), transport=httpx.MockTransport(handler), ram_probe=lambda: ram_mb)
    with client:
        return client.generate_structured(news_spec(), p.NewsAnalysisOutput,
                                          p.news_analysis_fallback("TCS Q2 results beat estimates", True))


class Recorder:
    """Mock Ollama: replies from a list (one per /api/chat call) and records requests."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_valid_json_first_try_and_request_shape():
    mock = Recorder(chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock)
    assert result.source == "llm" and result.model == "qwen3:1.7b" and not result.used_fallback
    assert result.value.sentiment == "positive" and result.tokens_per_second == 40.0
    sent = mock.requests[0]
    assert sent["think"] is False and sent["stream"] is False
    assert sent["options"]["num_ctx"] == 2048 and sent["format"]["type"] == "object"
    assert "<article>" in sent["messages"][1]["content"]


def test_thinking_block_is_stripped():
    result = run_news(Recorder(chat_response("<think>hmm</think>" + json.dumps(GOOD_NEWS))))
    assert result.source == "llm" and result.value.relevance == "high"


def test_invalid_json_gets_repair_hint_then_succeeds():
    mock = Recorder(chat_response("Sure! here it is"), chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock)
    assert result.source == "llm" and len(result.attempts) == 2 and result.used_fallback
    assert "rejected" in mock.requests[1]["messages"][-1]["content"]


def test_json_wrapped_in_prose_is_recovered():
    result = run_news(Recorder(chat_response("Answer: " + json.dumps(GOOD_NEWS) + " done")))
    assert result.source == "llm" and len(result.attempts) == 1


def test_timeouts_fall_back_to_smaller_model():
    mock = Recorder(httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"), chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock)
    assert result.model == "qwen3:0.6b" and [r["model"] for r in mock.requests] == ["qwen3:1.7b"] * 2 + ["qwen3:0.6b"]


def test_everything_fails_returns_deterministic_template():
    mock = Recorder(*[httpx.Response(500)] * 4)
    result = run_news(mock)
    assert result.source == "template" and result.model is None and len(result.attempts) == 4
    assert result.value.sentiment == "uncertain"  # never a guessed sentiment
    assert result.value.summary == "TCS Q2 results beat estimates"


def test_missing_model_is_not_retried():
    mock = Recorder(httpx.Response(404, json={"error": "model not found"}), chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock)
    assert result.model == "qwen3:0.6b" and "not installed" in result.attempts[0]["reason"]


def test_ollama_down_uses_template_quickly():
    mock = Recorder(*[httpx.ConnectError("refused")] * 2)
    result = run_news(mock)
    assert result.source == "template" and len(mock.requests) == 2  # one per model, no retry


def test_truncated_output_is_rejected():
    mock = Recorder(chat_response('{"summary": "TCS', "length"), chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock)
    assert result.source == "llm" and "truncated" in result.attempts[0]["reason"]


def test_invented_number_is_rejected():
    invented = {**GOOD_NEWS, "summary": "TCS revenue grew 37% this quarter."}
    mock = Recorder(chat_response(json.dumps(invented)), chat_response(json.dumps(invented)),
                    chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock)
    assert result.model == "qwen3:0.6b" and "numbers not in the input" in result.attempts[0]["reason"]


def test_low_ram_skips_primary_model():
    mock = Recorder(chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock, ram_mb=800)
    assert [r["model"] for r in mock.requests] == ["qwen3:0.6b"] and result.model == "qwen3:0.6b"


def test_no_fallback_model_configured():
    mock = Recorder(httpx.Response(500), httpx.Response(500))
    result = run_news(mock, llm_fallback_model="")
    assert result.source == "template" and {r["model"] for r in mock.requests} == {"qwen3:1.7b"}


def test_inference_is_serialized_across_threads():
    active, peak = 0, 0
    lock = threading.Lock()

    def handler(request):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return chat_response(json.dumps(GOOD_NEWS))

    threads = [threading.Thread(target=run_news, args=(handler,)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == 1  # never two inferences at once


def test_unload_sends_keep_alive_zero():
    calls = []

    def handler(request):
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": "qwen3:0.6b"}]})
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={})

    with OllamaClient(settings(), transport=httpx.MockTransport(handler)) as client:
        assert client.unload() == ["qwen3:0.6b"]
    assert calls == [{"model": "qwen3:0.6b", "keep_alive": 0}]


def test_fallback_model_empty_string_means_none():
    assert Settings(_env_file=None, llm_fallback_model="  ").llm_fallback_model is None


def test_markup_echo_is_rejected_and_retried():
    # Phase 7 live run: the model answered a digest with just "<article>".
    echoed = {**GOOD_NEWS, "summary": "<article>"}
    mock = Recorder(chat_response(json.dumps(echoed)), chat_response(json.dumps(GOOD_NEWS)))
    result = run_news(mock)
    assert result.source == "llm" and "prompt markup" in result.attempts[0]["reason"]
