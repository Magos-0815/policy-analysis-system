from __future__ import annotations

from typing import Any

from .config import load_industry_taxonomy, load_support_channels
from .repository import PolicyRepository


class PolicyClassifier:
    def __init__(self, repository: PolicyRepository | None = None) -> None:
        self.repository = repository or PolicyRepository()
        self.industries = load_industry_taxonomy().get("industries", {})
        self.channels = load_support_channels().get("channels", {})

    def classify_document(self, document: dict[str, Any]) -> dict[str, Any]:
        text = self._document_text(document)
        industry_matches = self._match_taxonomy(text, self.industries)
        channel_matches = self._match_taxonomy(text, self.channels)
        quantifiability = self._quantifiability(text)
        classification = {
            "document_id": document["document_id"],
            "industries": industry_matches,
            "support_channels": channel_matches,
            "quantifiability": quantifiability,
            "review_status": "agent_review_required" if industry_matches or channel_matches else "needs_manual_review",
        }
        self.repository.save_classification(document["document_id"], classification)
        return classification

    def classify_all(self) -> list[dict[str, Any]]:
        return [self.classify_document(document) for document in self.repository.list_documents()]

    def _document_text(self, document: dict[str, Any]) -> str:
        parts = [
            document.get("title", ""),
            " ".join(document.get("issuer", [])),
        ]
        text_path = document.get("text_path")
        if text_path:
            try:
                from pathlib import Path

                parts.append(Path(text_path).read_text(encoding="utf-8"))
            except OSError:
                pass
        return "\n".join(parts)

    def _match_taxonomy(self, text: str, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
        matches = []
        for key, spec in taxonomy.items():
            keywords = spec.get("keywords", [])
            hits = [keyword for keyword in keywords if keyword and keyword in text]
            if hits:
                matches.append(
                    {
                        "id": key,
                        "label": spec.get("label", key),
                        "confidence": min(0.95, 0.55 + 0.1 * len(hits)),
                        "matched_keywords": hits,
                    }
                )
        return matches

    def _quantifiability(self, text: str) -> str:
        if any(token in text for token in ["亿元", "万元", "%", "比例", "上限", "额度"]):
            return "rate_or_amount"
        if any(token in text for token in ["清单", "名单", "资格", "申报"]):
            return "eligibility_only"
        return "qualitative_only"
