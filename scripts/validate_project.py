#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy_index.config import load_policy_sources
from policy_index.paths import ensure_runtime_dirs
from policy_index.runtime_guard import assert_policy_project_isolated


def main() -> int:
    ensure_runtime_dirs()
    guard = assert_policy_project_isolated()
    sources = load_policy_sources().get("sources", {})
    payload = {
        "ok": True,
        "project_root": guard["project_root"],
        "workspace": guard["workspace"],
        "exports": guard["exports"],
        "source_count": len(sources),
        "sources": sorted(sources),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
