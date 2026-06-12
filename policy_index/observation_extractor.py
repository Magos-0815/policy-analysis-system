from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any

from .config import load_normalization_bases, load_scoring_weights
from .io import sha256_text
from .repository import PolicyRepository
from .ssi_engine.models import PDF_CHANNELS, SupportObservation


AMOUNT_PATTERN = re.compile(
    r"(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>万亿|千亿|百亿|亿元|亿|万元|万|元)"
)

UNIT_MULTIPLIER = {
    "万亿": 1_000_000_000_000.0,
    "千亿": 100_000_000_000.0,
    "百亿": 10_000_000_000.0,
    "亿元": 100_000_000.0,
    "亿": 100_000_000.0,
    "万元": 10_000.0,
    "万": 10_000.0,
    "元": 1.0,
}

TOTAL_AMOUNT_TERMS = (
    "安排",
    "下达",
    "拨付",
    "预算",
    "资金总额",
    "总规模",
    "规模",
    "中央财政资金",
    "财政资金",
    "专项资金",
    "补助资金",
    "补贴资金",
    "奖补资金",
    "政府出资",
    "基金规模",
    "贴息资金",
    "贷款额度",
)

NON_TOTAL_AMOUNT_TERMS = (
    "不超过",
    "最高",
    "上限",
    "每家",
    "单个",
    "每个",
    "注册资本",
    "资产总额",
    "营业收入",
    "投资额",
    "年度销售",
)

DIRECTNESS_BY_CHANNEL = {
    "direct_subsidy": 0.85,
    "r_and_d_tax_incentive": 0.75,
    "government_financed_berd": 0.75,
    "other_tax_incentive": 0.65,
    "credit_subsidy": 0.55,
    "guidance_fund": 0.65,
    "land_subsidy": 0.50,
    "soe_net_payables": 0.35,
    "debt_equity_swap": 0.45,
}


@dataclass(frozen=True)
class ExtractedAmount:
    amount: float
    raw_value: str
    unit: str
    context: str
    is_total_program_amount: bool
    confidence: float


@dataclass(frozen=True)
class NormalizationBase:
    value: float
    base_type: str
    source_document_ids: list[str]


class SupportObservationExtractor:
    """Build auditable SSI input rows from crawled public documents.

    This layer is intentionally conservative. Text-mined public policies may
    reveal a real support amount, but they only become calculable SSI rows when
    an externally sourced normalization base is configured for the same
    industry and period.
    """

    def __init__(
        self,
        repository: PolicyRepository | None = None,
        normalization_bases: dict[str, Any] | None = None,
    ) -> None:
        self.repository = repository or PolicyRepository()
        self.normalization_config = normalization_bases if normalization_bases is not None else load_normalization_bases()
        self.method_version = (
            load_scoring_weights()
            .get("state_support_intensity", {})
            .get("method_version", "ssi_v1")
        )

    def extract_all(
        self,
        classifications: list[dict[str, Any]] | None = None,
        *,
        persist: bool = False,
    ) -> list[SupportObservation]:
        class_rows = classifications if classifications is not None else self.repository.list_classifications()
        class_by_document_id = {row.get("document_id"): row for row in class_rows}
        observations: list[SupportObservation] = []
        for document in self.repository.list_documents():
            observations.extend(self.extract_document(document, class_by_document_id.get(document.get("document_id"))))

        if persist:
            from .ssi_engine.storage import SSIStorage

            SSIStorage().save_observations(observations)
        return observations

    def extract_document(
        self,
        document: dict[str, Any],
        classification: dict[str, Any] | None = None,
    ) -> list[SupportObservation]:
        text = self._document_text(document)
        classification = classification or {}
        channels = self._channel_ids(classification)
        if not channels:
            return []

        industries = self._industry_ids(classification)
        if not industries:
            industries = [("all", 0.35)]

        period = self._period(document, text)
        amount = self.best_amount_candidate(text)
        observations: list[SupportObservation] = []

        for channel, channel_confidence in channels:
            for industry, industry_confidence in industries:
                observations.append(
                    self._observation_from_match(
                        document=document,
                        channel=channel,
                        channel_confidence=channel_confidence,
                        industry=industry,
                        industry_confidence=industry_confidence,
                        period=period,
                        amount=amount,
                    )
                )
        return observations

    def best_amount_candidate(self, text: str) -> ExtractedAmount | None:
        candidates = self.amount_candidates(text)
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.is_total_program_amount, item.confidence, item.amount), reverse=True)[0]

    def amount_candidates(self, text: str) -> list[ExtractedAmount]:
        candidates: list[ExtractedAmount] = []
        normalized_text = re.sub(r"\s+", " ", text)
        for match in AMOUNT_PATTERN.finditer(normalized_text):
            raw_num = match.group("num")
            unit = match.group("unit")
            amount = float(raw_num.replace(",", "")) * UNIT_MULTIPLIER[unit]
            start = max(0, match.start() - 45)
            end = min(len(normalized_text), match.end() + 45)
            context = normalized_text[start:end]
            has_total_term = any(term in context for term in TOTAL_AMOUNT_TERMS)
            has_non_total_term = any(term in context for term in NON_TOTAL_AMOUNT_TERMS)
            confidence = 0.72 if has_total_term else 0.35
            if has_non_total_term and not has_total_term:
                confidence = 0.2
            candidates.append(
                ExtractedAmount(
                    amount=amount,
                    raw_value=match.group(0),
                    unit=unit,
                    context=context,
                    is_total_program_amount=has_total_term and not (has_non_total_term and not has_total_term),
                    confidence=confidence,
                )
            )
        return candidates

    def _observation_from_match(
        self,
        *,
        document: dict[str, Any],
        channel: str,
        channel_confidence: float,
        industry: str,
        industry_confidence: float,
        period: str,
        amount: ExtractedAmount | None,
    ) -> SupportObservation:
        base = self._normalization_base(industry, period)
        source_document_ids = [document["document_id"], *([] if not base else base.source_document_ids)]
        observation_id = self._observation_id(document["document_id"], channel, industry, period)
        directness_score = DIRECTNESS_BY_CHANNEL.get(channel, 0.45)
        coverage_score = self._coverage_score(amount, base)
        confidence_score = self._confidence_score(amount, base, channel_confidence, industry_confidence)
        double_count_group = self._double_count_group(document["document_id"], channel, industry, amount)

        if amount and amount.is_total_program_amount and base:
            return SupportObservation(
                observation_id=observation_id,
                channel=channel,
                industry=industry,
                period=period,
                observed_amount=amount.amount,
                currency="RMB",
                normalization_base=base.value,
                normalization_base_type=base.base_type,
                directness_score=directness_score,
                coverage_score=coverage_score,
                confidence_score=confidence_score,
                source_document_ids=source_document_ids,
                double_count_group=double_count_group,
                estimation_method=f"policy_text_total_amount:{amount.raw_value}",
                gap_status="proxy",
                method_version=self.method_version,
            )

        gap_reason = self._gap_reason(amount, base)
        return SupportObservation(
            observation_id=observation_id,
            channel=channel,
            industry=industry,
            period=period,
            observed_amount=amount.amount if amount and amount.is_total_program_amount else None,
            currency="RMB",
            normalization_base=base.value if base else None,
            normalization_base_type=base.base_type if base else "industry_output",
            directness_score=directness_score if amount else 0.0,
            coverage_score=coverage_score,
            confidence_score=0.0,
            source_document_ids=source_document_ids,
            double_count_group=double_count_group,
            estimation_method=gap_reason,
            gap_status="missing",
            method_version=self.method_version,
        )

    def _channel_ids(self, classification: dict[str, Any]) -> list[tuple[str, float]]:
        result: list[tuple[str, float]] = []
        for item in classification.get("support_channels", []):
            channel_id = item.get("id")
            if channel_id in PDF_CHANNELS:
                result.append((channel_id, float(item.get("confidence", 0.5))))
        return result

    def _industry_ids(self, classification: dict[str, Any]) -> list[tuple[str, float]]:
        result: list[tuple[str, float]] = []
        for item in classification.get("industries", []):
            industry_id = item.get("id")
            if industry_id:
                result.append((industry_id, float(item.get("confidence", 0.5))))
        return result

    def _document_text(self, document: dict[str, Any]) -> str:
        parts = [document.get("title", ""), " ".join(document.get("issuer", []))]
        text_path = document.get("text_path")
        if text_path:
            try:
                parts.append(Path(text_path).read_text(encoding="utf-8"))
            except OSError:
                pass
        return "\n".join(parts)

    def _period(self, document: dict[str, Any], text: str) -> str:
        for key in ("published_at", "retrieved_at"):
            value = str(document.get(key) or "")
            if len(value) >= 4 and value[:4].isdigit():
                return value[:4]
        match = re.search(r"(20\d{2})[-年./]\d{1,2}[-月./]\d{1,2}", text)
        if match:
            return match.group(1)
        return "1900"

    def _normalization_base(self, industry: str, period: str) -> NormalizationBase | None:
        bases = self.normalization_config.get("bases", {})
        candidates: list[Any] = []
        if isinstance(bases, list):
            candidates.extend(
                row for row in bases if str(row.get("industry")) == industry and str(row.get("period")) == period
            )
        elif isinstance(bases, dict):
            candidates.extend(
                value
                for key, value in bases.items()
                if key in {f"{industry}:{period}", f"{industry}/{period}", f"{industry}_{period}"}
            )
            nested_industry = bases.get(industry)
            if isinstance(nested_industry, dict):
                candidates.append(nested_industry.get(period))
            nested_period = bases.get(period)
            if isinstance(nested_period, dict):
                candidates.append(nested_period.get(industry))

        for candidate in candidates:
            parsed = self._parse_normalization_candidate(candidate)
            if parsed:
                return parsed
        return None

    def _parse_normalization_candidate(self, candidate: Any) -> NormalizationBase | None:
        if candidate is None:
            return None
        if isinstance(candidate, (int, float)):
            return NormalizationBase(value=float(candidate), base_type="industry_output", source_document_ids=[])
        if isinstance(candidate, dict):
            value = candidate.get("value", candidate.get("normalization_base"))
            if value is None:
                return None
            source_ids = candidate.get("source_document_ids") or candidate.get("source_document_id") or []
            if isinstance(source_ids, str):
                source_ids = [source_ids]
            return NormalizationBase(
                value=float(value),
                base_type=str(candidate.get("type", candidate.get("normalization_base_type", "industry_output"))),
                source_document_ids=list(source_ids),
            )
        return None

    def _coverage_score(self, amount: ExtractedAmount | None, base: NormalizationBase | None) -> float:
        if not amount or not amount.is_total_program_amount:
            return 0.0
        score = 0.25 + amount.confidence * 0.35
        if base:
            score += 0.2
        return min(0.85, score)

    def _confidence_score(
        self,
        amount: ExtractedAmount | None,
        base: NormalizationBase | None,
        channel_confidence: float,
        industry_confidence: float,
    ) -> float:
        if not amount or not amount.is_total_program_amount or not base:
            return 0.0
        return min(0.95, amount.confidence * channel_confidence * industry_confidence)

    def _gap_reason(self, amount: ExtractedAmount | None, base: NormalizationBase | None) -> str:
        if not amount:
            return "missing_policy_amount"
        if not amount.is_total_program_amount:
            return f"amount_mentioned_not_total_program:{amount.raw_value}"
        if not base:
            return f"observed_policy_amount_without_normalization_base:{amount.raw_value}"
        return "missing_calculation_input"

    def _double_count_group(
        self,
        document_id: str,
        channel: str,
        industry: str,
        amount: ExtractedAmount | None,
    ) -> str | None:
        if not amount or not amount.is_total_program_amount:
            return None
        if channel not in {"direct_subsidy", "r_and_d_tax_incentive", "government_financed_berd", "other_tax_incentive", "guidance_fund", "land_subsidy"}:
            return None
        amount_key = sha256_text(f"{amount.amount}:{amount.context}").split(":", 1)[1][:12]
        return f"{document_id}:{industry}:{amount_key}"

    def _observation_id(self, document_id: str, channel: str, industry: str, period: str) -> str:
        digest = sha256_text(f"{document_id}:{channel}:{industry}:{period}").split(":", 1)[1][:12]
        return f"obs_{channel}_{industry}_{period}_{digest}"
