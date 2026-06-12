from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


PDF_CHANNELS = (
    "direct_subsidy",
    "r_and_d_tax_incentive",
    "government_financed_berd",
    "other_tax_incentive",
    "credit_subsidy",
    "guidance_fund",
    "land_subsidy",
    "soe_net_payables",
    "debt_equity_swap",
)

GAP_STATUSES = ("observed", "estimated", "proxy", "missing")

ChannelId = Literal[
    "direct_subsidy",
    "r_and_d_tax_incentive",
    "government_financed_berd",
    "other_tax_incentive",
    "credit_subsidy",
    "guidance_fund",
    "land_subsidy",
    "soe_net_payables",
    "debt_equity_swap",
]
GapStatus = Literal["observed", "estimated", "proxy", "missing"]


class SupportObservation(BaseModel):
    observation_id: str
    channel: ChannelId
    industry: str
    period: str
    observed_amount: float | None = None
    currency: str = "RMB"
    normalization_base: float | None = None
    normalization_base_type: str = "industry_output"
    directness_score: float = Field(ge=0.0, le=1.0)
    coverage_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_document_ids: list[str] = Field(default_factory=list)
    double_count_group: str | None = None
    estimation_method: str = "observed"
    gap_status: GapStatus = "observed"
    method_version: str = "ssi_v1"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("period")
    @classmethod
    def period_must_start_with_year(cls, value: str) -> str:
        if len(value) < 4 or not value[:4].isdigit():
            raise ValueError("period must start with a four-digit year")
        return value

    @field_validator("source_document_ids")
    @classmethod
    def source_document_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result = []
        for item in value:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @model_validator(mode="after")
    def validate_amount_fields(self) -> "SupportObservation":
        if self.gap_status == "missing":
            return self
        if self.observed_amount is None:
            raise ValueError("observed_amount is required unless gap_status is missing")
        if self.observed_amount < 0:
            raise ValueError("observed_amount must be non-negative")
        if self.normalization_base is None or self.normalization_base <= 0:
            raise ValueError("normalization_base must be positive unless gap_status is missing")
        if not self.source_document_ids:
            raise ValueError("source_document_ids is required for observed, estimated, and proxy observations")
        return self

    @property
    def simulation_period(self) -> str:
        return self.period[:4]

    @property
    def calculable(self) -> bool:
        return self.gap_status != "missing"

    def to_record(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class StateSupportSnapshot(BaseModel):
    snapshot_date: str
    index_type: Literal["state_support_intensity"] = "state_support_intensity"
    method_version: str
    weighting_mode: str
    industry_values: list[dict[str, Any]]
    china_values: list[dict[str, Any]]
    channel_breakdowns: list[dict[str, Any]]
    observation_results: list[dict[str, Any]]
    excluded_observations: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    coverage: dict[str, Any]
    sensitivity_runs: list[dict[str, Any]]
    benchmark_warnings: list[dict[str, Any]]
    methodology: dict[str, Any]
