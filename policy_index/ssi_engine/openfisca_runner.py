from __future__ import annotations

from typing import Any

import polars as pl
from openfisca_core.simulation_builder import SimulationBuilder

from openfisca_china_policy_index import CountryTaxBenefitSystem


OPENFISCA_OUTPUTS = (
    "evidence_adjusted_amount",
    "support_intensity",
    "channel_weighted_intensity",
)


class OpenFiscaSSIRunner:
    def __init__(self) -> None:
        self.tax_benefit_system = CountryTaxBenefitSystem()

    def calculate(self, frame: pl.DataFrame) -> pl.DataFrame:
        if frame.is_empty():
            return frame.with_columns([pl.lit(None).alias(name) for name in OPENFISCA_OUTPUTS])

        outputs: list[pl.DataFrame] = []
        for (simulation_period,), period_frame in frame.group_by("simulation_period", maintain_order=True):
            inputs: dict[str, dict[str, list[float]]] = {
                "observed_amount": {simulation_period: period_frame["observed_amount"].to_list()},
                "normalization_base": {simulation_period: period_frame["normalization_base"].to_list()},
                "directness_score": {simulation_period: period_frame["directness_score"].to_list()},
                "coverage_score": {simulation_period: period_frame["coverage_score"].to_list()},
                "confidence_score": {simulation_period: period_frame["confidence_score"].to_list()},
                "channel_weight": {simulation_period: period_frame["channel_weight"].to_list()},
            }
            simulation = SimulationBuilder().build_from_dict(self.tax_benefit_system, inputs)
            calculated: dict[str, Any] = {"observation_id": period_frame["observation_id"].to_list()}
            for variable_name in OPENFISCA_OUTPUTS:
                calculated[variable_name] = simulation.calculate(variable_name, simulation_period).tolist()
            outputs.append(pl.DataFrame(calculated))

        return frame.join(pl.concat(outputs), on="observation_id", how="left")
