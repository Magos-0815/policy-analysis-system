from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from .config import load_scoring_weights
from .repository import PolicyRepository


class PolicySignalCalculator:
    def __init__(self, repository: PolicyRepository | None = None) -> None:
        self.repository = repository or PolicyRepository()
        self.weights = load_scoring_weights()

    def build_snapshot(self) -> dict[str, Any]:
        documents = {doc["document_id"]: doc for doc in self.repository.list_documents()}
        classifications = self.repository.list_classifications()
        rows = []
        grouped: dict[tuple[str, str], float] = defaultdict(float)
        counts: dict[tuple[str, str], int] = defaultdict(int)

        for classification in classifications:
            document = documents.get(classification["document_id"])
            if not document:
                continue
            period = self._period(document)
            score = self._score(document, classification)
            industries = classification.get("industries") or [{"id": "unclassified", "label": "Unclassified"}]
            for industry in industries:
                key = (industry["id"], period)
                grouped[key] += score
                counts[key] += 1
                rows.append(
                    {
                        "document_id": document["document_id"],
                        "industry": industry["id"],
                        "period": period,
                        "score": round(score, 4),
                        "title": document.get("title", ""),
                    }
                )

        index_values = [
            {
                "industry": industry,
                "period": period,
                "value": round(value, 4),
                "document_count": counts[(industry, period)],
                "method_version": "policy_signal_v0.1.0",
            }
            for (industry, period), value in sorted(grouped.items())
        ]
        snapshot = {
            "snapshot_date": date.today().isoformat(),
            "index_type": "policy_signal",
            "index_values": index_values,
            "document_scores": rows,
        }
        self.repository.save_index_snapshot(snapshot)
        return snapshot

    def _period(self, document: dict[str, Any]) -> str:
        published_at = document.get("published_at") or document.get("retrieved_at", "")
        return published_at[:7] if len(published_at) >= 7 else "unknown"

    def _score(self, document: dict[str, Any], classification: dict[str, Any]) -> float:
        issuer_weight = self._issuer_weight(document.get("issuer", []))
        channel_weight = self._channel_weight(classification.get("support_channels", []))
        quant_weight = {
            "rate_or_amount": 1.25,
            "eligibility_only": 1.0,
            "qualitative_only": 0.65,
        }.get(classification.get("quantifiability"), 0.65)
        evidence_weight = self.weights.get("evidence_quality", {}).get(document.get("source_category"), 1.0)
        return issuer_weight * channel_weight * quant_weight * evidence_weight

    def _issuer_weight(self, issuers: list[str]) -> float:
        weights = self.weights.get("issuer_weight", {})
        if not issuers:
            return float(weights.get("default", 1.0))
        return max(float(weights.get(issuer, weights.get("default", 1.0))) for issuer in issuers)

    def _channel_weight(self, channels: list[dict[str, Any]]) -> float:
        weights = self.weights.get("instrument_weight", {})
        if not channels:
            return float(weights.get("default", 1.0))
        return max(float(weights.get(channel["id"], weights.get("default", 1.0))) for channel in channels)
