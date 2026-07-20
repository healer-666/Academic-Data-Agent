"""Launch the React/FastAPI web workspace for Academic-Data-Agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.web.api import create_app  # noqa: E402


app = create_app(PROJECT_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the Academic-Data-Agent React web workspace.")
    parser.add_argument("--host", default="127.0.0.1", help="Server host.")
    parser.add_argument("--port", type=int, default=8000, help="Server port.")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for backend development.")
    args = parser.parse_args()

    import uvicorn

    if args.reload:
        uvicorn.run("web_app:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
