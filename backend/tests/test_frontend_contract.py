"""Frontend <-> backend contract (Phase 13, task 13.1.4).

Reads every endpoint that frontend/src/services/api.js calls and checks that the FastAPI app
serves that path with that HTTP method (from the app's OpenAPI schema). A renamed or removed
route, or a frontend call to a route that does not exist yet, fails here instead of showing
"Not Found" in the browser. No server, browser or Node is needed.
"""

import re

import pytest

from app.config import BACKEND_DIR
from app.main import create_app

API_JS = BACKEND_DIR.parent / "frontend" / "src" / "services" / "api.js"
# api.get('/x'), api.post(`/analysis/${id}/rerun`, ...), also across a line break: api\n  .post(...)
_CALL = re.compile(r"\bapi\s*\.(get|post|put|delete|patch)\(\s*([`'\"])(.*?)\2", re.DOTALL)
_TEMPLATE = re.compile(r"\$\{[^}]+\}")
_PARAM = re.compile(r"\{[^}]+\}")

pytestmark = pytest.mark.skipif(not API_JS.exists(), reason="frontend/src/services/api.js not found")


def frontend_calls() -> set[tuple[str, str]]:
    source = API_JS.read_text(encoding="utf-8")
    return {(method.upper(), "/api" + _TEMPLATE.sub("{}", path)) for method, _, path in _CALL.findall(source)}


def backend_routes(settings) -> set[tuple[str, str]]:
    schema = create_app(settings).openapi()
    return {(method.upper(), _PARAM.sub("{}", path)) for path, ops in schema["paths"].items() for method in ops}


def test_api_js_is_parsed():
    calls = frontend_calls()
    # spot checks: a plain path, a template path, a call split across lines, the avatar routes
    assert ("GET", "/api/market/indices") in calls
    assert ("POST", "/api/analysis/{}/rerun") in calls
    assert ("POST", "/api/analysis/start") in calls
    assert {("PUT", "/api/auth/me/avatar"), ("DELETE", "/api/auth/me/avatar")} <= calls
    assert len(calls) >= 25


def test_every_frontend_call_has_a_backend_route(no_db_settings):
    missing = sorted(frontend_calls() - backend_routes(no_db_settings))
    assert not missing, f"the frontend calls routes the API does not serve: {missing}"


def test_report_unused_backend_routes(no_db_settings):
    """Not a failure: some routes are for Swagger or scripts only. Listed so the report can say so."""
    unused = backend_routes(no_db_settings) - frontend_calls()
    assert all(path.startswith("/api/") for _, path in unused)


def test_exported_openapi_is_current(no_db_settings):
    """docs/openapi.json must match the routes (python scripts/export_openapi.py regenerates it)."""
    import json

    exported = BACKEND_DIR.parent / "docs" / "openapi.json"
    assert exported.exists(), "run python scripts/export_openapi.py"
    assert json.loads(exported.read_text(encoding="utf-8")) == create_app(no_db_settings).openapi(), \
        "docs/openapi.json is out of date: run python scripts/export_openapi.py"
