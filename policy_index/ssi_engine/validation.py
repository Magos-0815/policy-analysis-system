from __future__ import annotations

from typing import Any

import pointblank as pb
import polars as pl
from pydantic import ValidationError

from .models import GAP_STATUSES, PDF_CHANNELS, SupportObservation


REQUIRED_COLUMNS = [
    "observation_id",
    "channel",
    "industry",
    "period",
    "observed_amount",
    "currency",
    "normalization_base",
    "normalization_base_type",
    "directness_score",
    "coverage_score",
    "confidence_score",
    "source_document_ids",
    "double_count_group",
    "estimation_method",
    "gap_status",
    "method_version",
    "created_at",
]


def validate_observation_rows(rows: list[dict[str, Any] | SupportObservation]) -> list[SupportObservation]:
    observations: list[SupportObservation] = []
    errors: list[str] = []
    for index, row in enumerate(rows):
        if isinstance(row, SupportObservation):
            observations.append(row)
            continue
        try:
            observations.append(SupportObservation.model_validate(row))
        except ValidationError as exc:
            errors.append(f"row {index}: {exc}")
    if errors:
        raise ValueError("SupportObservation validation failed:\n" + "\n".join(errors))
    return observations


def observations_to_frame(observations: list[SupportObservation]) -> pl.DataFrame:
    records = [observation.to_record() for observation in observations]
    if not records:
        return pl.DataFrame({column: [] for column in REQUIRED_COLUMNS})
    return pl.DataFrame(records)


def run_pointblank_quality_gate(frame: pl.DataFrame) -> dict[str, Any]:
    if frame.height == 0:
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing_columns:
            raise ValueError(f"SupportObservation frame missing required columns: {missing_columns}")
        return {
            "status": "skipped",
            "reason": "no_observations",
            "row_count": 0,
            "required_columns": REQUIRED_COLUMNS,
        }

    validation = (
        pb.Validate(frame, tbl_name="support_observations", label="SSI SupportObservation quality gate")
        .col_exists(REQUIRED_COLUMNS)
        .col_vals_in_set("channel", set(PDF_CHANNELS))
        .col_vals_in_set("gap_status", set(GAP_STATUSES))
        .col_vals_between("directness_score", 0, 1)
        .col_vals_between("coverage_score", 0, 1)
        .col_vals_between("confidence_score", 0, 1)
        .interrogate()
    )
    report = validation.get_json_report()
    if not validation.all_passed():
        raise ValueError(f"Pointblank SupportObservation quality gate failed: {report}")
    return report
