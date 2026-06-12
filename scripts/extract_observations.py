#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy_index.classifier import PolicyClassifier
from policy_index.observation_extractor import SupportObservationExtractor
from policy_index.runtime_guard import assert_policy_project_isolated


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PDF-contract SupportObservation rows from crawled documents.")
    parser.add_argument("--no-classify", action="store_true", help="Use existing classifications instead of rebuilding them.")
    args = parser.parse_args()

    assert_policy_project_isolated()
    classifications = None if args.no_classify else PolicyClassifier().classify_all()
    observations = SupportObservationExtractor().extract_all(classifications, persist=True)
    payload = {
        "ok": True,
        "observations": len(observations),
        "calculable": sum(1 for observation in observations if observation.calculable),
        "missing": sum(1 for observation in observations if observation.gap_status == "missing"),
        "by_status": {},
        "output": str(ROOT / "workspace/observations/support_observations.jsonl"),
    }
    for observation in observations:
        payload["by_status"][observation.gap_status] = payload["by_status"].get(observation.gap_status, 0) + 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
