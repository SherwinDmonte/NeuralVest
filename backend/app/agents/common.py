"""Helpers shared by all agents: persistence of results and a protocol for the LLM client."""

import logging
from typing import Any, Protocol

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.database.models import REQUEST_SCOPE_KEY, AgentResultDocument
from app.database.repository import upsert_document
from app.schemas.agents import AgentEnvelope

logger = logging.getLogger("neuralvest.agents")


class LLMClient(Protocol):
    """What agents need from the LLM layer (OllamaClient satisfies it; tests use fakes)."""

    def generate_structured(self, spec, schema, fallback): ...


def save_agent_result(
    db: Database | None,
    request_id: str | None,
    output: AgentEnvelope,
    input_summary: dict[str, Any],
    stored_output: dict[str, Any] | None = None,
    scope: str = "symbol",
) -> str | None:
    """Upsert the agent's result into `agent_results` (the authoritative store).

    Returns a warning message if saving failed. A database problem never fails the agent:
    the analysis result is still returned to the caller.
    """
    if db is None or request_id is None:
        return None
    try:
        doc = AgentResultDocument(
            request_id=request_id,
            agent_name=output.agent,
            scope=scope,
            # request-level results (e.g. correlation of several stocks) use the fixed key
            scope_key=output.symbol if scope == "symbol" else REQUEST_SCOPE_KEY,
            symbol=output.symbol if scope == "symbol" else None,
            execution_status=output.status,
            input_summary=input_summary,
            output=stored_output if stored_output is not None else output.model_dump(mode="json"),
            status_detail={"warnings": output.warnings, "errors": output.errors},
            llm_model=(output.llm or {}).get("model"),
            execution_time=round(output.execution_seconds, 3),
        )
        upsert_document(db, doc, ["request_id", "agent_name", "scope_key"])
    except (PyMongoError, ValueError) as exc:
        logger.error("Could not save %s result for %s: %s", output.agent, output.symbol, exc.__class__.__name__)
        return f"Result could not be saved to the database ({exc.__class__.__name__})."
    return None
