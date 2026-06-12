# 政策分析系统 / China Policy Analyse

独立的中国政策抓取、政策语义分析和量化指数项目。

这个项目与 `/Users/alex/Documents/金融项目` 分离运行：独立 `.venv`、`.env`、workspace、logs、agent roster 和 CAMEL runtime。金融项目只通过 API 或 `exports/latest/` 读取结果。

## V1 Acceptance Scope

V1 的可验收目标是与两份 PDF 方法论一致的 `State Support Intensity Index`，不是简化版 `Policy Signal Index`。

V1 必须覆盖 PDF 口径中的九类支持渠道：

- `direct_subsidy`
- `r_and_d_tax_incentive`
- `government_financed_berd`
- `other_tax_incentive`
- `credit_subsidy`
- `guidance_fund`
- `land_subsidy`
- `soe_net_payables`
- `debt_equity_swap`

`Policy Signal Index` 只作为辅助政策热度、证据发现和缺口解释指标。它不能直接进入金额型 `State Support Intensity Index`，也不能替代缺失的支持金额、归一化基数或渠道观察值。

## Algorithm Contract

V1 指数计算以 `SupportObservation` 为最小可审计输入。每条 observation 至少包含：

- `channel`
- `industry`
- `period`
- `observed_amount`
- `currency`
- `normalization_base`
- `directness_score`
- `coverage_score`
- `confidence_score`
- `source_document_ids`
- `double_count_group`
- `method_version`
- `gap_status`

默认 PDF 一致公式：

```text
evidence_adjusted_amount =
  observed_amount
  * (1 + directness_score + coverage_score)
  * confidence_score

intensity[channel, industry, period] =
  evidence_adjusted_amount
  / normalization_base[industry, period]

SSI[industry, period] =
  100 * sum(channel_weight[channel] * intensity[channel, industry, period])

ChinaSSI[period] =
  sum(industry_weight[industry] * SSI[industry, period])
```

缺数据时不得伪造金额。系统只能输出 `missing`、`estimated` 或 `proxy` 状态，并在 composite 结果中显示覆盖率、置信度和方法说明。

## Quick Start

```bash
cd "/Users/alex/Documents/china policy analyse"
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/validate_project.py
.venv/bin/python scripts/crawl_once.py --source gov_cn_policy --offline-sample
.venv/bin/python scripts/build_index.py
```

当前脚手架可以运行离线政策样例和辅助 `policy_signal` 快照，但这只是工程底座验证，不代表 V1 指数已经验收。

## Calculation Engine

当前计算实现采用明确分层：

- `openfisca_china_policy_index/`：正式 OpenFisca 规则和公式引擎，不修改 `openfisca-core`。
- `policy_index/ssi_engine/`：SSI 编排层，负责 Pydantic/Pointblank 校验、Polars 批处理、DuckDB 存储、快照导出。
- `policy_index/ssi_engine/agent_review.py`：Camel-AI 审查 envelope，只写 audit，不允许修改指数数值。

生成 synthetic SSI 快照：

```bash
.venv/bin/python scripts/build_ssi_index.py --sample
```

输出：

- `exports/latest/state_support_index_snapshot.json`
- `exports/latest/support_observations.jsonl`
- `exports/latest/methodology.json`

## Project Boundaries

禁止共享或修改其他项目的：

- `.venv`
- `.env`
- CAMEL runtime
- workspace
- logs
- agent roster
- cache
- background sessions

所有输出必须位于本项目 `workspace/` 或 `exports/`。

## Key Docs

- `docs/development_plan_and_acceptance.md`
- `docs/china_policy_index_project_architecture.md`
- `docs/china_policy_index_current_implementation_analysis.md`
- `docs/china_policy_crawler_and_agent_design.md`
- `docs/china_policy_index_system_design.md`
