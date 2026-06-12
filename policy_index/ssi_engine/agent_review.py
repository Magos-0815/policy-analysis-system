from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from policy_index.io import read_json, write_json
from policy_index.paths import WORKSPACE_DIR, ensure_runtime_dirs


class CamelReviewEnvelope(BaseModel):
    agent_id: str
    task_id: str
    status: Literal["completed", "needs_revision", "blocked"]
    findings: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    method_version: str = "ssi_v1"
    affects_calculation: bool = False

    @model_validator(mode="after")
    def agent_reviews_cannot_mutate_calculation(self) -> "CamelReviewEnvelope":
        if self.affects_calculation:
            raise ValueError("Camel-AI review envelopes cannot mutate State Support Intensity calculations")
        return self


class AgentReviewStore:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        self.base_dir = WORKSPACE_DIR / "audit" / "agent_outputs"

    def review_path(self, review: CamelReviewEnvelope):
        safe_task = review.task_id.replace("/", "_")
        safe_agent = review.agent_id.replace("/", "_")
        return self.base_dir / f"{safe_task}_{safe_agent}.json"

    def save_review(self, review: CamelReviewEnvelope | dict[str, Any]) -> dict[str, Any]:
        envelope = review if isinstance(review, CamelReviewEnvelope) else CamelReviewEnvelope.model_validate(review)
        payload = envelope.model_dump(mode="json")
        write_json(self.review_path(envelope), payload)
        return payload

    def list_reviews(self) -> list[dict[str, Any]]:
        if not self.base_dir.exists():
            return []
        return [read_json(path) for path in sorted(self.base_dir.glob("*.json"))]
