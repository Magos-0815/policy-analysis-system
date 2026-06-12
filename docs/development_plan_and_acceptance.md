# China Policy Analyse 开发计划与验收标准

日期：2026-06-12

## 1. V1 目标

V1 的唯一核心交付是与两份 PDF 方法论一致的 `State Support Intensity Index`。

当前项目已有的 `Policy Signal Index` 只能作为辅助指标，用于：

- 政策热度解释。
- 缺口发现。
- 文档审查排序。
- 辅助报告叙述。

它不得作为 V1 指数验收成果，也不得直接进入金额型 SSI 聚合。

## 2. Algorithm Contract

### 2.1 支持渠道

V1 必须支持以下 PDF 渠道：

| Channel ID | 中文名称 | 典型数据 |
|---|---|---|
| `direct_subsidy` | 直接财政补贴 | 政府补助、专项资金、预算补贴、上市公司政府补助 |
| `r_and_d_tax_incentive` | R&D 税收优惠 | 研发费用加计扣除、R&D tax expenditure |
| `government_financed_berd` | 政府资助 BERD | OECD/NBS 口径政府资助企业研发 |
| `other_tax_incentive` | 其他税收优惠 | VAT、所得税、进口税、地方税费减免，扣除 R&D 部分 |
| `credit_subsidy` | 信贷补贴 / SOE 融资优势 | 利差、贴息、政策贷款、担保、结构性工具 |
| `guidance_fund` | 政府引导基金 | 政府出资、产业基金注资、补贴等价 |
| `land_subsidy` | 土地和房地产补贴 | 市场价与实际成交价差额 |
| `soe_net_payables` | SOE 净应付款优势 | 延迟付款形成的隐性融资支持 |
| `debt_equity_swap` | 债转股 | 债务成本下降或政府推动重组支持等价 |

### 2.2 SupportObservation

每条 observation 必须包含：

```text
observation_id
channel
industry
period
observed_amount
currency
normalization_base
normalization_base_type
directness_score
coverage_score
confidence_score
source_document_ids
double_count_group
estimation_method
gap_status
method_version
created_at
```

允许的 `gap_status`：

- `observed`：直接观测金额。
- `estimated`：基于明确假设估算。
- `proxy`：代理变量。
- `missing`：渠道应覆盖但当前缺失。

### 2.3 默认公式

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

### 2.4 权重和稳健性

V1 必须支持：

- `expert_default`：PDF 可解释专家权重，作为默认发布口径。
- `equal_weight`：渠道等权敏感性。
- `gdp_share`：行业 GDP 或产值权重敏感性。
- `confidence_weighted`：按 observation confidence 调整敏感性。

PCA/factor analysis 后置到历史 observation 足够后，不作为 V1 阻塞项。

### 2.5 双重计算规则

V1 必须内置并测试：

- `other_tax_incentive` 扣除 `r_and_d_tax_incentive`。
- 同一项目的 `government_financed_berd` 不再进入 `direct_subsidy`。
- `guidance_fund` 只计政府资本或补贴等价，不按总基金规模全计。
- 同一土地项目不能同时按土地价差和招商返还全额计入。
- `credit_subsidy` 与 `soe_net_payables` 分开披露，聚合时保留融资支持说明。
- `policy_signal` 永不进入 SSI 金额聚合。

## 3. Development Plan

### 当前已落地的计算底座

- `OpenFisca`：`openfisca_china_policy_index` country package 已定义 `SupportUnit` 和 SSI 公式变量。
- `DuckDB + Polars`：`policy_index/ssi_engine/storage.py` 和 `calculator.py` 已负责 observation、聚合结果和快照表。
- `Pydantic + Pointblank`：`SupportObservation` 行级校验和表级 quality gate 已接入。
- `Camel-AI`：`CamelReviewEnvelope` 已作为审查和解释层接口，验证器禁止它修改 SSI 数值。

### Phase 0：文档纠偏

交付：

- README 改为 V1 SSI 验收口径。
- 4 份既有架构/设计文档去除“先做 Policy Signal”的旧方向。
- 新增本开发计划和验收标准。

验收：

- 文档中不再把 Policy Signal 写成首版核心指数。
- 所有核心文档都写明 PDF 公式、九类渠道、observation schema 和双重计算规则。

### Phase 1：数据模型和配置

交付：

- `SupportObservation` 模型。
- channel weights、industry weights、normalization base 配置。
- `gap_status`、`method_version`、`double_count_group` 字段。
- observation repository 和 JSONL export。

验收：

- 可写入九类渠道的 synthetic observations。
- 缺失渠道可记录 `gap_status=missing`。
- observation 可追溯到 source document。

### Phase 2：数据接入

交付：

- 官方政策源用于文档证据链。
- OECD Data 接入 R&D tax support 和 government-financed BERD。
- MOF / 税务 / PBOC / LandChina / 交易所公告 adapter 形成 observation 或 gap。
- Wind、CSMAR、Zero2IPO 未授权时只保留 adapter slot 和 gap。

验收：

- 每个渠道至少有 observed、estimated、proxy 或 missing 状态。
- 不允许用政策热度填补金额。
- 所有抓取输出留存 raw、text、metadata 和 content hash。

### Phase 3：SSI 指数引擎

交付：

- `StateSupportIntensityCalculator`。
- PDF 默认公式。
- 行业聚合和 China composite。
- double count engine。
- 0-100 scale 和 `% baseline` 输出。

验收：

- synthetic golden fixture 可手算复核。
- double-counting fixture 输出符合规则。
- 缺失数据不会被填充成金额。

### Phase 4：QA、API 和导出

交付：

- `GET /api/index/state-support`
- `GET /api/support-observations`
- `GET /api/methodology`
- `exports/latest/state_support_index_snapshot.json`
- `exports/latest/support_observations.jsonl`
- `exports/latest/methodology.json`

验收：

- 每个 index value 能回链到 observation、source document、normalization base、权重和 method version。
- Agent QA warning 能进入 snapshot。
- 当前金融项目只读消费，不写政策项目内部状态。

### Phase 5：稳健性和 benchmark

交付：

- low/base/high 区间。
- sensitivity runs。
- CSIS/IMF/OECD/WTO benchmark warning。
- methodology note。

验收：

- benchmark 不一致时输出 warning，不静默覆盖。
- sensitivity 输出可复现。
- method version 变更时能回放历史口径。

## 4. Test Plan

V1 必须新增并通过：

| 测试 | 目标 |
|---|---|
| formula golden test | 用 synthetic observations 验证 PDF 公式 |
| double-counting test | 验证 R&D、BERD、税收、土地、基金去重 |
| missing-data test | 验证 `missing` 不会被伪造为金额 |
| sensitivity test | 验证 equal、GDP share、confidence weighting |
| export schema test | 验证 snapshot、observation、methodology 导出字段 |
| runtime isolation test | 验证不写 `/Users/alex/Documents/金融项目` |
| policy-signal separation test | 验证 `policy_signal` 不参与 SSI 聚合 |

## 5. Definition of Done

V1 完成必须同时满足：

- 文档、配置、代码、测试都使用同一套 PDF 算法口径。
- 九类渠道都能进入 observation schema，缺失也必须显式标记。
- SSI 输出含 industry values、China composite、channel breakdown、coverage、confidence interval、sensitivity 和 benchmark warnings。
- 任一指数值都能追溯来源、权重、基数、方法版本。
- 所有测试通过。
- 项目没有修改 `/Users/alex/Documents/金融项目` 的文档、配置、代码或运行状态。
