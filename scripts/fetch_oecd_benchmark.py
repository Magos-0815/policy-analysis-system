#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy_index.oecd_benchmark import OecdRDTaxBenchmarkClient
from policy_index.runtime_guard import assert_policy_project_isolated


def main() -> int:
    assert_policy_project_isolated()
    summary = OecdRDTaxBenchmarkClient().fetch_and_save()
    print(
        json.dumps(
            {
                "ok": True,
                "observations": len(summary["observations"]),
                "gaps": len(summary["gaps"]),
                "output": str(ROOT / "workspace/observations/oecd_rdtax_berd_china.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
