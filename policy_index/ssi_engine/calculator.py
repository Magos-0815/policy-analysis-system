from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl

from policy_index.config import load_industry_taxonomy, load_scoring_weights

from .double_counting import DoubleCountDecision, apply_double_count_rules
from .models import PDF_CHANNELS, StateSupportSnapshot, SupportObservation
from .openfisca_runner import OpenFiscaSSIRunner
from .storage import SSIStorage
from .validation import observations_to_frame, run_pointblank_quality_gate, validate_observation_rows


class StateSupportIntensityCalculator:
    def __init__(
        self,
        storage: SSIStorage | None = None,
        openfisca_runner: OpenFiscaSSIRunner | None = None,
    ) -> None:
        self.storage = storage or SSIStorage()
        self.openfisca_runner = openfisca_runner or OpenFiscaSSIRunner()
        self.weights_config = load_scoring_weights().get("state_support_intensity", {})
        self.industries_config = load_industry_taxonomy().get("industries", {})

    def build_snapshot(
        self,
        rows: list[dict[str, Any] | SupportObservation] | None = None,
        *,
        weighting_mode: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        if rows is None:
            rows = self.storage.load_observations()

        observations = validate_observation_rows(rows)
        quality_report = run_pointblank_quality_gate(observations_to_frame(observations))
        if persist:
            self.storage.save_observations(observations)

        mode = weighting_mode or self.weights_config.get("default_weighting_mode", "expert_default")
        base_snapshot = self._calculate_snapshot(observations, mode, include_sensitivity=True)
        base_snapshot["methodology"]["quality_gate"] = quality_report
        snapshot = StateSupportSnapshot.model_validate(base_snapshot).model_dump(mode="json")
        if persist:
            self.storage.save_snapshot(snapshot)
        return snapshot

    def _calculate_snapshot(
        self,
        observations: list[SupportObservation],
        weighting_mode: str,
        *,
        include_sensitivity: bool,
    ) -> dict[str, Any]:
        included, decisions = apply_double_count_rules(observations)
        calculable = [observation for observation in included if observation.calculable]
        gaps = self._gaps(observations)
        channel_weights, industry_weights = self._weights_for_mode(calculable, weighting_mode)

        calculated = self._calculate_observations(calculable, channel_weights)
        industry_values = self._industry_values(calculated)
        china_values = self._china_values(industry_values, industry_weights)
        channel_breakdowns = self._channel_breakdowns(calculated)

        sensitivity_runs = []
        if include_sensitivity:
            sensitivity_runs = self._sensitivity_runs(observations, weighting_mode)

        snapshot = {
            "snapshot_date": date.today().isoformat(),
            "index_type": "state_support_intensity",
            "method_version": self.weights_config.get("method_version", "ssi_v1"),
            "weighting_mode": weighting_mode,
            "industry_values": industry_values,
            "china_values": china_values,
            "channel_breakdowns": channel_breakdowns,
            "observation_results": self._observation_records(calculated),
            "excluded_observations": self._excluded_records(observations, decisions),
            "gaps": gaps,
            "coverage": self._coverage(observations, calculable),
            "sensitivity_runs": sensitivity_runs,
            "benchmark_warnings": self._benchmark_warnings(observations, gaps),
            "methodology": {
                "engine": {
                    "formal_rules": "OpenFisca country package openfisca_china_policy_index",
                    "batch_processing": "Polars",
                    "storage": "DuckDB + JSON/JSONL exports",
                    "quality_gate": "Pydantic row validation + Pointblank table validation",
                    "agent_role": "Camel-AI reviews evidence and explanations only; it does not calculate SSI values.",
                },
                "formula": {
                    "evidence_adjusted_amount": "observed_amount * (1 + directness_score + coverage_score) * confidence_score",
                    "intensity": "evidence_adjusted_amount / normalization_base",
                    "industry_ssi": "100 * sum(channel_weight * intensity)",
                    "china_ssi": "sum(industry_weight * industry_ssi)",
                },
                "weighting_mode": weighting_mode,
                "channel_weights": channel_weights,
                "industry_weights": industry_weights,
            },
        }
        return snapshot

    def _calculate_observations(
        self,
        observations: list[SupportObservation],
        channel_weights: dict[str, float],
    ) -> pl.DataFrame:
        if not observations:
            return pl.DataFrame()

        frame = observations_to_frame(observations).with_columns(
            [
                pl.col("period").str.slice(0, 4).alias("simulation_period"),
                pl.col("channel").replace_strict(channel_weights, default=0.0).cast(pl.Float64).alias("channel_weight"),
            ]
        )
        return self.openfisca_runner.calculate(frame)

    def _industry_values(self, calculated: pl.DataFrame) -> list[dict[str, Any]]:
        if calculated.is_empty():
            return []
        frame = (
            calculated.group_by(["industry", "period"], maintain_order=True)
            .agg(
                [
                    pl.sum("channel_weighted_intensity").alias("weighted_intensity_sum"),
                    pl.len().alias("observation_count"),
                    pl.n_unique("channel").alias("channel_count"),
                ]
            )
            .with_columns((pl.col("weighted_intensity_sum") * 100).round(8).alias("value"))
            .select(["industry", "period", "value", "observation_count", "channel_count"])
            .sort(["period", "industry"])
        )
        return frame.to_dicts()

    def _china_values(
        self,
        industry_values: list[dict[str, Any]],
        industry_weights: dict[str, float],
    ) -> list[dict[str, Any]]:
        if not industry_values:
            return []
        frame = pl.DataFrame(industry_values).with_columns(
            pl.col("industry").replace_strict(industry_weights, default=0.0).cast(pl.Float64).alias("industry_weight")
        )
        frame = (
            frame.with_columns((pl.col("value") * pl.col("industry_weight")).alias("weighted_value"))
            .group_by("period", maintain_order=True)
            .agg(
                [
                    pl.sum("weighted_value").round(8).alias("value"),
                    pl.sum("industry_weight").round(8).alias("covered_industry_weight"),
                    pl.len().alias("industry_count"),
                ]
            )
            .sort("period")
        )
        return frame.to_dicts()

    def _channel_breakdowns(self, calculated: pl.DataFrame) -> list[dict[str, Any]]:
        if calculated.is_empty():
            return []
        frame = (
            calculated.group_by(["industry", "period", "channel"], maintain_order=True)
            .agg(
                [
                    pl.sum("evidence_adjusted_amount").round(8).alias("evidence_adjusted_amount"),
                    pl.sum("support_intensity").round(8).alias("support_intensity"),
                    (pl.sum("channel_weighted_intensity") * 100).round(8).alias("value"),
                    pl.len().alias("observation_count"),
                ]
            )
            .sort(["period", "industry", "channel"])
        )
        return frame.to_dicts()

    def _observation_records(self, calculated: pl.DataFrame) -> list[dict[str, Any]]:
        if calculated.is_empty():
            return []
        return (
            calculated.select(
                [
                    "observation_id",
                    "channel",
                    "industry",
                    "period",
                    "gap_status",
                    "observed_amount",
                    "normalization_base",
                    "directness_score",
                    "coverage_score",
                    "confidence_score",
                    "channel_weight",
                    "evidence_adjusted_amount",
                    "support_intensity",
                    "channel_weighted_intensity",
                    "source_document_ids",
                    "method_version",
                ]
            )
            .sort(["period", "industry", "channel", "observation_id"])
            .to_dicts()
        )

    def _excluded_records(
        self,
        observations: list[SupportObservation],
        decisions: list[DoubleCountDecision],
    ) -> list[dict[str, Any]]:
        observation_map = {observation.observation_id: observation for observation in observations}
        return [
            {
                **observation_map[decision.observation_id].to_record(),
                "double_count_action": decision.action,
                "double_count_reason": decision.reason,
            }
            for decision in decisions
            if decision.action == "excluded"
        ]

    def _gaps(self, observations: list[SupportObservation]) -> list[dict[str, Any]]:
        explicit = [
            {
                "channel": observation.channel,
                "industry": observation.industry,
                "period": observation.period,
                "gap_status": observation.gap_status,
                "observation_id": observation.observation_id,
                "reason": "explicit missing SupportObservation",
            }
            for observation in observations
            if observation.gap_status == "missing"
        ]
        observed_channels = {observation.channel for observation in observations if observation.gap_status != "missing"}
        for channel in PDF_CHANNELS:
            if channel not in observed_channels:
                explicit.append(
                    {
                        "channel": channel,
                        "industry": "all",
                        "period": "all",
                        "gap_status": "missing",
                        "observation_id": None,
                        "reason": "no calculable observation for required PDF channel",
                    }
                )
        return explicit

    def _coverage(
        self,
        observations: list[SupportObservation],
        calculable: list[SupportObservation],
    ) -> dict[str, Any]:
        calculable_channels = {observation.channel for observation in calculable}
        status_counts: dict[str, int] = {}
        for observation in observations:
            status_counts[observation.gap_status] = status_counts.get(observation.gap_status, 0) + 1
        return {
            "total_observations": len(observations),
            "calculable_observations": len(calculable),
            "required_channel_count": len(PDF_CHANNELS),
            "covered_channel_count": len(calculable_channels),
            "covered_channels": sorted(calculable_channels),
            "missing_channels": [channel for channel in PDF_CHANNELS if channel not in calculable_channels],
            "gap_status_counts": status_counts,
        }

    def _benchmark_warnings(
        self,
        observations: list[SupportObservation],
        gaps: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        warnings = []
        missing_channels = sorted({gap["channel"] for gap in gaps if gap["gap_status"] == "missing"})
        if missing_channels:
            warnings.append(
                {
                    "level": "warning",
                    "code": "missing_required_channels",
                    "message": "SSI snapshot is not externally benchmark-ready while required PDF channels are missing.",
                    "channels": missing_channels,
                }
            )
        if not observations:
            warnings.append(
                {
                    "level": "warning",
                    "code": "no_observations",
                    "message": "No SupportObservation rows were supplied; SSI cannot be calculated.",
                }
            )
        return warnings

    def _sensitivity_runs(
        self,
        observations: list[SupportObservation],
        baseline_mode: str,
    ) -> list[dict[str, Any]]:
        modes = self.weights_config.get("sensitivity_modes", [])
        runs = []
        for mode in modes:
            if mode == baseline_mode:
                continue
            snapshot = self._calculate_snapshot(observations, mode, include_sensitivity=False)
            runs.append(
                {
                    "weighting_mode": mode,
                    "china_values": snapshot["china_values"],
                    "industry_values": snapshot["industry_values"],
                }
            )
        return runs

    def _weights_for_mode(
        self,
        observations: list[SupportObservation],
        weighting_mode: str,
    ) -> tuple[dict[str, float], dict[str, float]]:
        default_channel = {
            channel: float(weight)
            for channel, weight in self.weights_config.get("channel_weight", {}).items()
        }
        default_industry = {
            industry: float(weight)
            for industry, weight in self.weights_config.get("industry_weight", {}).items()
        }
        if weighting_mode == "equal_weight":
            channel_weight = 1 / len(PDF_CHANNELS)
            observed_industries = sorted({observation.industry for observation in observations}) or sorted(self.industries_config)
            industry_weight = 1 / len(observed_industries) if observed_industries else 0.0
            return (
                {channel: channel_weight for channel in PDF_CHANNELS},
                {industry: industry_weight for industry in observed_industries},
            )
        if weighting_mode == "confidence_weighted":
            confidence_by_channel: dict[str, list[float]] = {channel: [] for channel in PDF_CHANNELS}
            for observation in observations:
                confidence_by_channel[observation.channel].append(observation.confidence_score)
            raw = {}
            for channel in PDF_CHANNELS:
                average_confidence = (
                    sum(confidence_by_channel[channel]) / len(confidence_by_channel[channel])
                    if confidence_by_channel[channel]
                    else 0.5
                )
                raw[channel] = default_channel.get(channel, 0.0) * average_confidence
            total = sum(raw.values()) or 1.0
            return ({channel: value / total for channel, value in raw.items()}, default_industry)
        if weighting_mode == "gdp_share":
            return (default_channel, default_industry)
        return (default_channel, default_industry)
