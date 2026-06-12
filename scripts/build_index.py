#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy_index.classifier import PolicyClassifier
from policy_index.exporter import SnapshotExporter
from policy_index.policy_signal import PolicySignalCalculator
from policy_index.runtime_guard import assert_policy_project_isolated


def main() -> int:
    assert_policy_project_isolated()
    classifications = PolicyClassifier().classify_all()
    snapshot = PolicySignalCalculator().build_snapshot()
    exports = SnapshotExporter().export_latest()
    print(
        json.dumps(
            {
                "ok": True,
                "classifications": len(classifications),
                "index_values": len(snapshot.get("index_values", [])),
                "exports": exports,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
