from __future__ import annotations

import csv
import io
from typing import Any

import httpx

from .config import load_policy_sources
from .io import sha256_text, utc_now_iso, write_json
from .paths import WORKSPACE_DIR


OECD_CHINA_REF_AREA = "CHN"
OECD_RDTAX_MEASURES = {"RDTAX", "DF"}


class OecdRDTaxBenchmarkClient:
    """Fetch public OECD R&D tax incentive and BERD benchmark rows.

    The OECD dataset is useful as an external benchmark, but it is not
    industry-specific China SSI input. This client stores raw China rows and a
    compact benchmark summary separately from amount-based SupportObservation
    rows.
    """

    def __init__(self, api_url: str | None = None) -> None:
        sources = load_policy_sources().get("sources", {})
        configured_url = sources.get("oecd_data", {}).get("api", {}).get("rdtax_berd_csv", "")
        self.api_url = api_url or configured_url

    def fetch_china_rows(self) -> list[dict[str, Any]]:
        if not self.api_url:
            raise ValueError("OECD RDTAX API URL is not configured")
        headers = {
            "User-Agent": "ChinaPolicyAnalyse/0.1 (public-policy-research)",
            "Accept": "text/csv,application/vnd.sdmx.data+csv,*/*;q=0.8",
        }
        response = httpx.get(self.api_url, timeout=45, follow_redirects=True, headers=headers)
        response.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(response.text)))
        china_rows = [
            row
            for row in rows
            if row.get("REF_AREA") == OECD_CHINA_REF_AREA
            and row.get("MEASURE") in OECD_RDTAX_MEASURES
        ]
        return china_rows

    def build_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        observations = []
        gaps = []
        for row in rows:
            value = row.get("OBS_VALUE", "")
            record = {
                "benchmark_id": self._benchmark_id(row),
                "source_id": "oecd_data",
                "source_url": self.api_url,
                "ref_area": row.get("REF_AREA"),
                "reference_area": row.get("Reference area"),
                "measure": row.get("MEASURE"),
                "measure_label": row.get("Measure"),
                "period": row.get("TIME_PERIOD"),
                "unit": row.get("UNIT_MEASURE"),
                "unit_label": row.get("Unit of measure"),
                "obs_value": float(value) if value else None,
                "obs_status": row.get("OBS_STATUS"),
                "obs_status_label": row.get("Observation status"),
            }
            if value:
                observations.append(record)
            else:
                gaps.append(record)
        return {
            "benchmark_type": "oecd_rdtax_berd_percent_gdp",
            "retrieved_at": utc_now_iso(),
            "source_url": self.api_url,
            "methodology_note": (
                "OECD rows are national percentage-of-GDP benchmarks for R&D tax support "
                "and government-financed BERD. They are stored for external comparison and "
                "must not be added directly to industry State Support Intensity observations."
            ),
            "observations": observations,
            "gaps": gaps,
        }

    def fetch_and_save(self) -> dict[str, Any]:
        rows = self.fetch_china_rows()
        summary = self.build_summary(rows)
        write_json(WORKSPACE_DIR / "observations" / "oecd_rdtax_berd_china.json", summary)
        return summary

    def _benchmark_id(self, row: dict[str, Any]) -> str:
        digest = sha256_text(
            ":".join(
                [
                    str(row.get("REF_AREA", "")),
                    str(row.get("MEASURE", "")),
                    str(row.get("TIME_PERIOD", "")),
                    str(row.get("UNIT_MEASURE", "")),
                ]
            )
        ).split(":", 1)[1][:12]
        return f"oecd_rdtax_{digest}"
