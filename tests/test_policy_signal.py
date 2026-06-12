from __future__ import annotations

from policy_index.classifier import PolicyClassifier
from policy_index.crawler import PolicyCrawler
from policy_index.policy_signal import PolicySignalCalculator


def test_policy_signal_snapshot_from_offline_sample():
    result = PolicyCrawler().crawl_offline_sample("gov_cn_policy")
    assert result.status == "completed"
    classifications = PolicyClassifier().classify_all()
    assert classifications
    snapshot = PolicySignalCalculator().build_snapshot()
    assert snapshot["index_type"] == "policy_signal"
    assert snapshot["index_values"]
