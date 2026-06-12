from __future__ import annotations

from openfisca_core.model_api import YEAR, Variable, set_input_divide_by_period

from openfisca_china_policy_index.entities import SupportUnit


class observed_amount(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "Observed or estimated support amount"
    set_input = set_input_divide_by_period


class normalization_base(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "Industry normalization base"
    set_input = set_input_divide_by_period


class directness_score(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "Evidence directness score"
    set_input = set_input_divide_by_period


class coverage_score(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "Evidence coverage score"
    set_input = set_input_divide_by_period


class confidence_score(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "Observation confidence score"
    set_input = set_input_divide_by_period


class channel_weight(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "State Support Intensity channel weight"
    set_input = set_input_divide_by_period


class evidence_adjusted_amount(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "PDF evidence-adjusted support amount"

    def formula(support_unit, period, parameters):
        return (
            support_unit("observed_amount", period)
            * (1 + support_unit("directness_score", period) + support_unit("coverage_score", period))
            * support_unit("confidence_score", period)
        )


class support_intensity(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "Evidence-adjusted support divided by normalization base"

    def formula(support_unit, period, parameters):
        return support_unit("evidence_adjusted_amount", period) / support_unit("normalization_base", period)


class channel_weighted_intensity(Variable):
    value_type = float
    entity = SupportUnit
    definition_period = YEAR
    label = "Channel-weighted support intensity"

    def formula(support_unit, period, parameters):
        return support_unit("support_intensity", period) * support_unit("channel_weight", period)


VARIABLES = (
    observed_amount,
    normalization_base,
    directness_score,
    coverage_score,
    confidence_score,
    channel_weight,
    evidence_adjusted_amount,
    support_intensity,
    channel_weighted_intensity,
)
