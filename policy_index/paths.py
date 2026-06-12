from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("POLICY_INDEX_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
WORKSPACE_DIR = (PROJECT_ROOT / os.environ.get("POLICY_INDEX_WORKSPACE", "workspace")).resolve()
EXPORTS_DIR = (PROJECT_ROOT / os.environ.get("POLICY_INDEX_EXPORTS", "exports/latest")).resolve()
CONFIG_DIR = PROJECT_ROOT / "configs"


def ensure_runtime_dirs() -> None:
    for path in (
        WORKSPACE_DIR,
        WORKSPACE_DIR / "raw",
        WORKSPACE_DIR / "text",
        WORKSPACE_DIR / "documents",
        WORKSPACE_DIR / "attachments",
        WORKSPACE_DIR / "observations",
        WORKSPACE_DIR / "index",
        WORKSPACE_DIR / "audit",
        WORKSPACE_DIR / "audit" / "agent_outputs",
        WORKSPACE_DIR / "logs",
        WORKSPACE_DIR / "events",
        EXPORTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
