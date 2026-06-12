from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import load_policy_sources
from .io import sha256_text, utc_now_iso
from .repository import PolicyRepository


@dataclass(frozen=True)
class CrawlResult:
    source_id: str
    status: str
    documents: list[dict[str, Any]]
    skipped_reason: str = ""


class PolicyCrawler:
    def __init__(self, repository: PolicyRepository | None = None) -> None:
        self.repository = repository or PolicyRepository()
        self.registry = load_policy_sources()

    def sources(self) -> dict[str, Any]:
        return self.registry.get("sources", {})

    def crawl_offline_sample(self, source_id: str) -> CrawlResult:
        source = self.sources().get(source_id)
        if not source:
            return CrawlResult(source_id=source_id, status="skipped", documents=[], skipped_reason="unknown_source")

        sample_items = source.get("sample_items") or [
            {
                "title": f"{source.get('label', source_id)} sample policy",
                "url": source.get("base_url", ""),
                "issuer": [source.get("label", source_id)],
                "published_at": "2026-01-01",
                "body": "政策样例：支持先进制造、税收优惠、研发费用加计扣除和专项资金申报。",
            }
        ]

        documents = []
        for idx, item in enumerate(sample_items, start=1):
            document_id = f"{source_id}_sample_{idx:04d}"
            body = item.get("body", "")
            raw = self._render_sample_html(item)
            text = f"{item.get('title', '')}\n\n{body}\n"
            document = {
                "document_id": document_id,
                "source_id": source_id,
                "source_tier": source.get("tier", ""),
                "source_category": source.get("source_category", ""),
                "url": item.get("url") or source.get("base_url", ""),
                "title": item.get("title", ""),
                "issuer": item.get("issuer", []),
                "doc_number": item.get("doc_number", ""),
                "published_at": item.get("published_at", ""),
                "retrieved_at": utc_now_iso(),
                "policy_type": item.get("policy_type", "sample"),
                "content_hash": sha256_text(text),
                "parse_status": "parsed",
                "access_policy": source.get("access_policy", "public_only_no_login"),
            }
            documents.append(self.repository.save_document(document, raw=raw, text=text))
        return CrawlResult(source_id=source_id, status="completed", documents=documents)

    def _render_sample_html(self, item: dict[str, Any]) -> str:
        title = item.get("title", "")
        body = item.get("body", "")
        return f"<html><head><title>{title}</title></head><body><h1>{title}</h1><p>{body}</p></body></html>\n"
