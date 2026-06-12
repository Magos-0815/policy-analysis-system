from __future__ import annotations

import os
from pathlib import Path

from .paths import EXPORTS_DIR, PROJECT_ROOT, WORKSPACE_DIR


FORBIDDEN_PROJECT_ROOTS = {
    Path("/Users/alex/Documents/金融项目").resolve(),
}


class RuntimeIsolationError(RuntimeError):
    """Raised when the policy project would write into another project."""


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def assert_policy_project_isolated() -> dict[str, str]:
    """Fail fast if policy jobs would use another project's runtime or workspace."""
    root = PROJECT_ROOT.resolve()
    workspace = WORKSPACE_DIR.resolve()
    exports = EXPORTS_DIR.resolve()
    cwd = Path.cwd().resolve()

    if root in FORBIDDEN_PROJECT_ROOTS:
        raise RuntimeIsolationError(f"policy project root points at forbidden project: {root}")
    if not _is_relative_to(workspace, root):
        raise RuntimeIsolationError(f"workspace must live under policy project root: {workspace}")
    if not _is_relative_to(exports, root):
        raise RuntimeIsolationError(f"exports must live under policy project root: {exports}")
    if _is_relative_to(workspace, Path("/Users/alex/Documents/金融项目")):
        raise RuntimeIsolationError(f"workspace points into Deal copilot project: {workspace}")

    camel_python = os.environ.get("POLICY_INDEX_CAMEL_PYTHON", ".venv/bin/python")
    camel_path = (root / camel_python).resolve() if not Path(camel_python).is_absolute() else Path(camel_python).resolve()
    if _is_relative_to(camel_path, Path("/Users/alex/Documents/金融项目")):
        raise RuntimeIsolationError(f"CAMEL python points into Deal copilot project: {camel_path}")

    deal_env = os.environ.get("DEAL_COPILOT_CAMEL_PYTHON", "")
    if deal_env and "POLICY_INDEX_ALLOW_DEAL_ENV_FOR_TESTS" not in os.environ:
        raise RuntimeIsolationError("DEAL_COPILOT_CAMEL_PYTHON is set; unset it before running policy jobs")

    return {
        "project_root": str(root),
        "workspace": str(workspace),
        "exports": str(exports),
        "cwd": str(cwd),
        "camel_python": str(camel_path),
    }
