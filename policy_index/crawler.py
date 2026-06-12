from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

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

    def crawl_public_source(self, source_id: str, *, limit: int = 20) -> CrawlResult:
        source = self.sources().get(source_id)
        if not source:
            return CrawlResult(source_id=source_id, status="skipped", documents=[], skipped_reason="unknown_source")
        if source.get("access_policy") not in {"public_only_no_login", "public_or_authorized_api_only"}:
            return CrawlResult(source_id=source_id, status="skipped", documents=[], skipped_reason="non_public_source")
        if source.get("parser") not in {"generic_html", "api_or_download"}:
            return CrawlResult(source_id=source_id, status="skipped", documents=[], skipped_reason="unsupported_parser")

        base_url = source.get("base_url")
        if not base_url:
            return CrawlResult(source_id=source_id, status="skipped", documents=[], skipped_reason="missing_base_url")

        try:
            list_html = self._fetch_text(base_url)
        except Exception as exc:  # noqa: BLE001 - store source-specific crawl failure
            return CrawlResult(source_id=source_id, status="skipped", documents=[], skipped_reason=f"list_fetch_failed:{exc}")

        candidates = self._extract_links(base_url, list_html, source)[:limit]
        documents: list[dict[str, Any]] = []
        failures: list[str] = []

        for candidate in candidates:
            try:
                raw = self._fetch_text(candidate["url"])
                document = self._document_from_html(source_id, source, candidate, raw)
                text = document.pop("_text")
                documents.append(self.repository.save_document(document, raw=raw, text=text))
            except Exception as exc:  # noqa: BLE001 - continue crawling other public documents
                failures.append(f"{candidate['url']}:{exc}")

        if documents and failures:
            return CrawlResult(source_id=source_id, status="partial", documents=documents, skipped_reason=";".join(failures[:5]))
        if documents:
            return CrawlResult(source_id=source_id, status="completed", documents=documents)
        return CrawlResult(source_id=source_id, status="skipped", documents=[], skipped_reason="no_documents_fetched")

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

    def _fetch_text(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ChinaPolicyAnalyse/0.1; public-policy-research)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        with httpx.Client(timeout=25, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type and "xml" not in content_type:
                raise ValueError(f"unsupported_content_type:{content_type}")
            return response.text

    def _extract_links(self, base_url: str, html: str, source: dict[str, Any]) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        allowed_domains = set(source.get("allowed_domains", []))
        links: list[dict[str, str]] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 4:
                continue
            url = urldefrag(urljoin(base_url, anchor["href"]))[0]
            if not self._is_allowed_url(url, allowed_domains):
                continue
            if url == base_url or url in seen:
                continue
            if not self._looks_like_detail_url(url):
                continue
            seen.add(url)
            parent_text = anchor.parent.get_text(" ", strip=True) if anchor.parent else title
            links.append(
                {
                    "url": url,
                    "title": title,
                    "published_at": self._extract_date(parent_text),
                }
            )
        return links

    def _document_from_html(
        self,
        source_id: str,
        source: dict[str, Any],
        candidate: dict[str, str],
        raw: str,
    ) -> dict[str, Any]:
        soup = BeautifulSoup(raw, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
        title = self._extract_title(soup) or candidate["title"]
        published_at = candidate.get("published_at") or self._extract_date(text)
        document_id = f"{source_id}_{sha256_text(candidate['url']).split(':', 1)[1][:16]}"
        return {
            "document_id": document_id,
            "source_id": source_id,
            "source_tier": source.get("tier", ""),
            "source_category": source.get("source_category", ""),
            "url": candidate["url"],
            "title": title,
            "issuer": self._extract_issuer(text, source),
            "doc_number": self._extract_doc_number(text),
            "published_at": published_at,
            "retrieved_at": utc_now_iso(),
            "policy_type": "public_html",
            "content_hash": sha256_text(text),
            "parse_status": "parsed" if text else "empty_text",
            "access_policy": source.get("access_policy", "public_only_no_login"),
            "_text": f"{title}\n\n{text}\n",
        }

    def _is_allowed_url(self, url: str, allowed_domains: set[str]) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        host = parsed.netloc.lower()
        return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)

    def _looks_like_detail_url(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        if any(path.endswith(suffix) for suffix in [".html", ".htm", ".shtml", ".xml"]):
            return True
        return bool(re.search(r"/20\d{2}[-_/]?\d{0,2}[-_/]?\d{0,2}/", path))

    def _extract_title(self, soup: BeautifulSoup) -> str:
        for selector in ["h1", ".title", "title"]:
            node = soup.select_one(selector)
            if node:
                title = " ".join(node.get_text(" ", strip=True).split())
                if title:
                    return title
        return ""

    def _extract_date(self, text: str) -> str:
        match = re.search(r"(20\d{2})[-年./](\d{1,2})[-月./](\d{1,2})", text)
        if not match:
            return ""
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    def _extract_issuer(self, text: str, source: dict[str, Any]) -> list[str]:
        issuers = []
        for issuer in ["国务院", "国家发展改革委", "工业和信息化部", "财政部", "税务总局", "中国人民银行"]:
            if issuer in text:
                issuers.append(issuer)
        return issuers or [source.get("label", "")]

    def _extract_doc_number(self, text: str) -> str:
        match = re.search(r"([\u4e00-\u9fa5]{1,8}[〔\[]20\d{2}[〕\]][第]?\d+号)", text)
        return match.group(1) if match else ""
