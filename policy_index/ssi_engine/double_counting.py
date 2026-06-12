from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import SupportObservation


@dataclass(frozen=True)
class DoubleCountDecision:
    observation_id: str
    action: str
    reason: str
    double_count_group: str | None


CONFLICT_EXCLUSIONS: tuple[tuple[frozenset[str], str, str], ...] = (
    (
        frozenset({"government_financed_berd", "direct_subsidy"}),
        "direct_subsidy",
        "BERD already captures this R&D support group",
    ),
    (
        frozenset({"r_and_d_tax_incentive", "other_tax_incentive"}),
        "other_tax_incentive",
        "other_tax_incentive must exclude the R&D tax portion",
    ),
    (
        frozenset({"guidance_fund", "direct_subsidy"}),
        "direct_subsidy",
        "guidance fund government-capital equivalent is the channel-specific support measure",
    ),
    (
        frozenset({"land_subsidy", "direct_subsidy"}),
        "direct_subsidy",
        "land support group should not also be counted as a generic local subsidy",
    ),
)


def apply_double_count_rules(
    observations: list[SupportObservation],
) -> tuple[list[SupportObservation], list[DoubleCountDecision]]:
    included: list[SupportObservation] = []
    decisions: list[DoubleCountDecision] = []
    grouped: dict[str, list[SupportObservation]] = defaultdict(list)

    for observation in observations:
        if observation.double_count_group:
            grouped[observation.double_count_group].append(observation)

    excluded_ids: set[str] = set()
    for group_id, group_observations in grouped.items():
        channels = {observation.channel for observation in group_observations}
        for conflict_channels, excluded_channel, reason in CONFLICT_EXCLUSIONS:
            if conflict_channels.issubset(channels):
                for observation in group_observations:
                    if observation.channel == excluded_channel:
                        excluded_ids.add(observation.observation_id)
                        decisions.append(
                            DoubleCountDecision(
                                observation_id=observation.observation_id,
                                action="excluded",
                                reason=reason,
                                double_count_group=group_id,
                            )
                        )

    for observation in observations:
        if observation.observation_id in excluded_ids:
            continue
        included.append(observation)
        decisions.append(
            DoubleCountDecision(
                observation_id=observation.observation_id,
                action="included",
                reason="no double-count exclusion matched",
                double_count_group=observation.double_count_group,
            )
        )

    return included, decisions
