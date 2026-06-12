from __future__ import annotations

import duckdb
import pytest

from policy_index.paths import EXPORTS_DIR, WORKSPACE_DIR
from policy_index.ssi_engine import StateSupportIntensityCalculator, SupportObservation
from policy_index.ssi_engine.agent_review import AgentReviewStore, CamelReviewEnvelope
from policy_index.ssi_engine.storage import SSIStorage


def observation(**overrides):
    payload = {
        "observation_id": "obs_direct",
        "channel": "direct_subsidy",
        "industry": "semiconductor",
        "period": "2026",
        "observed_amount": 100.0,
        "normalization_base": 1000.0,
        "directness_score": 0.2,
        "coverage_score": 0.1,
        "confidence_score": 0.5,
        "source_document_ids": ["doc_1"],
        "gap_status": "observed",
    }
    payload.update(overrides)
    return SupportObservation(**payload)


def test_ssi_formula_uses_openfisca_pdf_contract():
    snapshot = StateSupportIntensityCalculator().build_snapshot([observation()], persist=False)

    assert snapshot["industry_values"][0]["industry"] == "semiconductor"
    assert snapshot["industry_values"][0]["period"] == "2026"
    assert snapshot["industry_values"][0]["value"] == pytest.approx(1.04, abs=1e-6)
    result = snapshot["observation_results"][0]
    assert result["evidence_adjusted_amount"] == pytest.approx(65.0, abs=1e-6)
    assert result["support_intensity"] == pytest.approx(0.065, abs=1e-6)
    assert result["channel_weighted_intensity"] == pytest.approx(0.0104, abs=1e-6)
    assert snapshot["methodology"]["engine"]["formal_rules"].startswith("OpenFisca")


def test_double_count_excludes_direct_subsidy_when_berd_covers_same_group():
    rows = [
        observation(observation_id="obs_direct_dup", double_count_group="rd_project"),
        observation(
            observation_id="obs_berd",
            channel="government_financed_berd",
            observed_amount=50.0,
            directness_score=0.0,
            coverage_score=0.0,
            confidence_score=1.0,
            double_count_group="rd_project",
        ),
    ]

    snapshot = StateSupportIntensityCalculator().build_snapshot(rows, persist=False)

    assert [row["observation_id"] for row in snapshot["observation_results"]] == ["obs_berd"]
    assert snapshot["industry_values"][0]["value"] == pytest.approx(0.5, abs=1e-6)
    assert snapshot["excluded_observations"][0]["observation_id"] == "obs_direct_dup"
    assert "BERD" in snapshot["excluded_observations"][0]["double_count_reason"]


def test_missing_observation_is_gap_not_amount():
    missing = observation(
        observation_id="obs_land_missing",
        channel="land_subsidy",
        industry="ev",
        observed_amount=None,
        normalization_base=None,
        directness_score=0.0,
        coverage_score=0.0,
        confidence_score=0.0,
        source_document_ids=[],
        gap_status="missing",
        estimation_method="source_required",
    )

    snapshot = StateSupportIntensityCalculator().build_snapshot([missing], persist=False)

    assert snapshot["industry_values"] == []
    assert snapshot["china_values"] == []
    assert snapshot["coverage"]["calculable_observations"] == 0
    assert any(gap["observation_id"] == "obs_land_missing" for gap in snapshot["gaps"])
    assert snapshot["benchmark_warnings"][0]["code"] == "missing_required_channels"


def test_sensitivity_runs_and_policy_signal_separation():
    snapshot = StateSupportIntensityCalculator().build_snapshot([observation()], persist=False)

    modes = {run["weighting_mode"] for run in snapshot["sensitivity_runs"]}
    assert {"equal_weight", "gdp_share", "confidence_weighted"}.issubset(modes)
    assert "policy_signal" not in snapshot["methodology"]["formula"]
    assert "does not calculate SSI values" in snapshot["methodology"]["engine"]["agent_role"]


def test_ssi_storage_exports_duckdb_and_latest_files():
    storage = SSIStorage()
    snapshot = StateSupportIntensityCalculator(storage).build_snapshot([observation()], persist=True)

    assert (EXPORTS_DIR / "state_support_index_snapshot.json").exists()
    assert (EXPORTS_DIR / "support_observations.jsonl").exists()
    assert (EXPORTS_DIR / "methodology.json").exists()
    assert snapshot["index_type"] == "state_support_intensity"

    with duckdb.connect(str(WORKSPACE_DIR / "index" / "ssi_engine.duckdb")) as con:
        tables = {name for (name,) in con.execute("show tables").fetchall()}
        assert "support_observations" in tables
        assert "ssi_industry_values" in tables
        assert con.execute("select count(*) from ssi_industry_values").fetchone()[0] >= 1


def test_camel_review_layer_is_audit_only():
    store = AgentReviewStore()
    review = store.save_review(
        CamelReviewEnvelope(
            agent_id="methodology_analyst",
            task_id="ssi_sample_review",
            status="completed",
            findings=[{"severity": "info", "message": "Formula reviewed"}],
            source_document_ids=["doc_1"],
        )
    )

    assert review["affects_calculation"] is False
    assert any(item["task_id"] == "ssi_sample_review" for item in store.list_reviews())
    with pytest.raises(ValueError, match="cannot mutate"):
        CamelReviewEnvelope(
            agent_id="methodology_analyst",
            task_id="bad_review",
            status="completed",
            affects_calculation=True,
        )
