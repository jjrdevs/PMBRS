#!/usr/bin/env python3
"""Launch the PMBRS local dashboard (Phase B) on http://127.0.0.1:8501.

Thin wrapper: puts ``src/`` on ``PYTHONPATH`` (same convention as
``conftest.py``) and delegates to ``streamlit run``. The dashboard is
read-only — see ``src/pmbrs/dashboard/app.py``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
APP = SRC / "pmbrs" / "dashboard" / "app.py"
PORT = int(os.environ.get("PMBRS_DASHBOARD_PORT", "8501"))
HOST = os.environ.get("PMBRS_DASHBOARD_HOST", "127.0.0.1")


def main() -> int:
    if not APP.is_file():
        raise SystemExit(f"dashboard app not found: {APP}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    cmd = [
        "streamlit", "run", str(APP),
        "--server.port", str(PORT),
        "--server.address", HOST,
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    try:
        return subprocess.call(cmd, env=env, cwd=str(PROJECT_ROOT))
    except FileNotFoundError as exc:
        raise SystemExit("streamlit not found on PATH — pip install -r requirements.txt first") from exc


if __name__ == "__main__":
    raise SystemExit(main())
