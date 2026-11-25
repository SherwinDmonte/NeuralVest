"""Write the API's OpenAPI schema to docs/openapi.json (task 14.1.5).

The schema comes from the FastAPI app itself, so it always matches the code. No database or
network is needed. Run from backend/ (venv active) after changing a route:
    python scripts/export_openapi.py
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")  # no connection is made; only the route definitions are read
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import PROJECT_ROOT  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    schema = create_app().openapi()
    path = PROJECT_ROOT / "docs" / "openapi.json"
    path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    operations = sum(len(ops) for ops in schema["paths"].values())
    print(f"{path}: OpenAPI {schema['openapi']}, {schema['info']['title']} {schema['info']['version']}, "
          f"{len(schema['paths'])} paths, {operations} operations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
