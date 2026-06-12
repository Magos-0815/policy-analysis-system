#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy_index.ssi_engine import StateSupportIntensityCalculator, SupportObservation


def sample_observations() -> list[SupportObservation]:
    return [
        SupportObservation(
            observation_id="sample_direct_subsidy_semiconductor_2026",
            channel="direct_subsidy",
            industry="semiconductor",
            period="2026",
            observed_amount=100.0,
            normalization_base=1000.0,
            directness_score=0.2,
            coverage_score=0.1,
            confidence_score=0.5,
            source_document_ids=["gov_cn_policy_sample_0001"],
            double_count_group="sample_semiconductor_support",
        ),
        SupportObservation(
            observation_id="sample_rd_tax_semiconductor_2026",
            channel="r_and_d_tax_incentive",
            industry="semiconductor",
            period="2026",
            observed_amount=80.0,
            normalization_base=1000.0,
            directness_score=0.4,
            coverage_score=0.2,
            confidence_score=0.75,
            source_document_ids=["gov_cn_policy_sample_0001"],
        ),
        SupportObservation(
            observation_id="sample_land_gap_2026",
            channel="land_subsidy",
            industry="ev",
            period="2026",
            observed_amount=None,
            normalization_base=None,
            directness_score=0.0,
            coverage_score=0.0,
            confidence_score=0.0,
            source_document_ids=[],
            gap_status="missing",
            estimation_method="required_source_missing",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the PDF-consistent State Support Intensity snapshot.")
    parser.add_argument("--sample", action="store_true", help="Use built-in synthetic observations.")
    args = parser.parse_args()

    calculator = StateSupportIntensityCalculator()
    snapshot = calculator.build_snapshot(sample_observations() if args.sample else None)
    print(
        json.dumps(
            {
                "ok": True,
                "industry_values": len(snapshot["industry_values"]),
                "china_values": len(snapshot["china_values"]),
                "exports": {
                    "state_support_index_snapshot": str(ROOT / "exports/latest/state_support_index_snapshot.json"),
                    "support_observations": str(ROOT / "exports/latest/support_observations.jsonl"),
                    "methodology": str(ROOT / "exports/latest/methodology.json"),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
