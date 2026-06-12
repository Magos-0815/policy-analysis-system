from __future__ import annotations

from pathlib import Path

import pytest

from policy_index.crawler import PolicyCrawler
from policy_index.observation_extractor import SupportObservationExtractor
from policy_index.oecd_benchmark import OecdRDTaxBenchmarkClient
from policy_index.repository import PolicyRepository
from policy_index.ssi_engine import StateSupportIntensityCalculator


def test_public_crawler_persists_html_document(monkeypatch):
    crawler = PolicyCrawler(PolicyRepository())
    crawler.registry = {
        "sources": {
            "test_public": {
                "label": "测试公开源",
                "tier": "P0",
                "source_category": "official_policy",
                "base_url": "https://example.gov.cn/list/",
                "allowed_domains": ["example.gov.cn"],
                "parser": "generic_html",
                "access_policy": "public_only_no_login",
            }
        }
    }
    html_by_url = {
        "https://example.gov.cn/list/": '<a href="/2026/06/notice.html">关于下达集成电路专项资金的通知</a>',
        "https://example.gov.cn/2026/06/notice.html": """
            <html><head><title>关于下达集成电路专项资金的通知</title></head>
            <body><h1>关于下达集成电路专项资金的通知</h1>
            <p>财政部 2026年6月1日 下达专项资金5亿元，支持集成电路产业。</p></body></html>
        """,
    }

    monkeypatch.setattr(crawler, "_fetch_text", lambda url: html_by_url[url])

    result = crawler.crawl_public_source("test_public", limit=1)

    assert result.status == "completed"
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document["source_id"] == "test_public"
    assert document["title"] == "关于下达集成电路专项资金的通知"
    assert Path(document["text_path"]).read_text(encoding="utf-8").find("专项资金5亿元") >= 0


def test_observation_extractor_creates_calculable_proxy_when_base_exists(tmp_path):
    text_path = tmp_path / "doc.txt"
    text_path.write_text("财政部 2026年6月1日 下达专项资金5亿元，支持集成电路产业。", encoding="utf-8")
    document = {
        "document_id": "doc_real_amount",
        "title": "关于下达集成电路专项资金的通知",
        "issuer": ["财政部"],
        "published_at": "2026-06-01",
        "text_path": str(text_path),
    }
    classification = {
        "document_id": "doc_real_amount",
        "industries": [{"id": "semiconductor", "confidence": 0.85}],
        "support_channels": [{"id": "direct_subsidy", "confidence": 0.9}],
    }
    extractor = SupportObservationExtractor(
        normalization_bases={
            "bases": {
                "semiconductor": {
                    "2026": {
                        "value": 100_000_000_000,
                        "type": "industry_output",
                        "source_document_ids": ["stats_semiconductor_2026"],
                    }
                }
            }
        }
    )

    observations = extractor.extract_document(document, classification)
    observation = observations[0]

    assert observation.gap_status == "proxy"
    assert observation.observed_amount == pytest.approx(500_000_000.0)
    assert observation.normalization_base == pytest.approx(100_000_000_000.0)
    assert observation.source_document_ids == ["doc_real_amount", "stats_semiconductor_2026"]

    snapshot = StateSupportIntensityCalculator().build_snapshot(observations, persist=False)
    assert snapshot["industry_values"][0]["industry"] == "semiconductor"
    assert snapshot["coverage"]["calculable_observations"] == 1


def test_observation_extractor_keeps_real_amount_as_gap_without_base(tmp_path):
    text_path = tmp_path / "doc.txt"
    text_path.write_text("财政部下达专项资金5亿元，支持集成电路产业。", encoding="utf-8")
    document = {
        "document_id": "doc_missing_base",
        "title": "关于下达集成电路专项资金的通知",
        "issuer": ["财政部"],
        "published_at": "2026-06-01",
        "text_path": str(text_path),
    }
    classification = {
        "document_id": "doc_missing_base",
        "industries": [{"id": "semiconductor", "confidence": 0.85}],
        "support_channels": [{"id": "direct_subsidy", "confidence": 0.9}],
    }

    observations = SupportObservationExtractor(normalization_bases={"bases": {}}).extract_document(document, classification)
    observation = observations[0]

    assert observation.gap_status == "missing"
    assert observation.calculable is False
    assert observation.observed_amount == pytest.approx(500_000_000.0)
    assert observation.normalization_base is None
    assert observation.estimation_method.startswith("observed_policy_amount_without_normalization_base")

    snapshot = StateSupportIntensityCalculator().build_snapshot(observations, persist=False)
    assert snapshot["industry_values"] == []
    assert snapshot["coverage"]["calculable_observations"] == 0


def test_observation_extractor_does_not_use_cap_amount_as_support_amount(tmp_path):
    text_path = tmp_path / "doc.txt"
    text_path.write_text("对符合条件企业给予支持，单个项目最高不超过200万元。", encoding="utf-8")
    document = {
        "document_id": "doc_cap",
        "title": "关于制造业项目申报的通知",
        "issuer": ["财政部"],
        "published_at": "2026-06-01",
        "text_path": str(text_path),
    }
    classification = {
        "document_id": "doc_cap",
        "industries": [{"id": "manufacturing", "confidence": 0.85}],
        "support_channels": [{"id": "direct_subsidy", "confidence": 0.9}],
    }

    observation = SupportObservationExtractor(
        normalization_bases={"bases": {"manufacturing": {"2026": 100_000_000_000}}}
    ).extract_document(document, classification)[0]

    assert observation.gap_status == "missing"
    assert observation.observed_amount is None
    assert observation.estimation_method.startswith("amount_mentioned_not_total_program")


def test_oecd_benchmark_client_stores_benchmark_not_ssi_observation(monkeypatch):
    csv_text = """STRUCTURE,REF_AREA,Reference area,MEASURE,Measure,UNIT_MEASURE,Unit of measure,TIME_PERIOD,OBS_VALUE,OBS_STATUS,Observation status
DATAFLOW,CHN,China (People's Republic of),RDTAX,Indirect government support through R&D tax incentives (GTARD),PT_B1GQ,Percentage of GDP,2022,0.24259999,,
DATAFLOW,CHN,China (People's Republic of),DF,Government-financed BERD,PT_B1GQ,Percentage of GDP,2023,0.0403,,
DATAFLOW,CHN,China (People's Republic of),RDTAX,Indirect government support through R&D tax incentives (GTARD),PT_B1GQ,Percentage of GDP,2023,,O,Missing value
"""

    class Response:
        text = csv_text

        def raise_for_status(self):
            return None

    monkeypatch.setattr("policy_index.oecd_benchmark.httpx.get", lambda *args, **kwargs: Response())

    client = OecdRDTaxBenchmarkClient(api_url="https://sdmx.oecd.org/test.csv")
    rows = client.fetch_china_rows()
    summary = client.build_summary(rows)

    assert len(rows) == 3
    assert len(summary["observations"]) == 2
    assert len(summary["gaps"]) == 1
    assert "must not be added directly" in summary["methodology_note"]
