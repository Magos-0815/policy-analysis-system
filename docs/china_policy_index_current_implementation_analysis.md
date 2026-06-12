# China Policy Analyse：当前进展评估与 PDF 口径纠偏

日期：2026-06-12

## 1. 当前结论

项目已经在独立目录 `/Users/alex/Documents/china policy analyse` 建好基础骨架，且与 `/Users/alex/Documents/金融项目` 隔离。现有能力可以继续复用：

- 独立 Python `.venv`、配置目录、workspace 和 exports。
- P0 官方政策源配置。
- 离线政策抓取样例、基础分类器、辅助 `policy_signal` 快照。
- `runtime_guard`、`validate_project.py`、基础 pytest。
- 从原 PDF 分析迁移过来的项目文档。

但当前实现还没有达到 PDF 的指数算法口径。现有 `PolicySignalCalculator` 只是政策文本热度和可量化线索评分：

```text
score = issuer_weight * channel_weight * quantifiability_weight * evidence_quality
```

这不能作为 V1 验收指数。V1 必须直接实现 PDF 一致的 `State Support Intensity Index`：按支持渠道形成可审计 observation，归一化到行业基数，做权重聚合、双重计算控制、不确定性和外部 benchmark。

## 2. PDF 口径 vs 当前实现

| 维度 | PDF 口径 | 当前状态 | V1 要求 |
|---|---|---|---|
| 指数目标 | State Support Intensity / China State Support Index | 只有辅助 Policy Signal | 直接实现 SSI，Policy Signal 只做辅助 |
| 支持渠道 | 九类金额或代理金额渠道 | 配置里渠道较粗，且多为政策关键词 | 扩展为 PDF 九类渠道 |
| 数据输入 | 支持金额、基数、证据质量、覆盖率 | 政策文档和分类结果 | 新增 SupportObservation |
| 归一化 | 行业 GDP、产值、营收、资产、产能等 | 未实现 | 每条 observation 必须绑定 normalization_base |
| 双重计算 | R&D、BERD、税收、土地、基金要去重 | 未实现 | 引擎和测试必须覆盖 |
| 不确定性 | low/base/high、Monte Carlo 或敏感性 | 未实现 | V1 至少输出区间和 sensitivity |
| Benchmark | CSIS/IMF/OECD/WTO 对照 | 未实现 | V1 输出 methodology warning |

## 3. 进展状态

### 已完成

- 新项目目录和基础 Python 包。
- 官方政策源注册表雏形。
- 离线 HTML 样例抓取和文档存储。
- 规则分类行业、支持渠道、可量化程度。
- 辅助 `policy_signal` 快照导出。
- 项目边界检查，避免写入金融项目。
- OpenFisca country package `openfisca_china_policy_index`，用于正式 SSI 公式计算。
- `policy_index/ssi_engine`，用于 Pydantic/Pointblank 校验、Polars 聚合、DuckDB 存储和 SSI 快照导出。
- Camel-AI 审查 envelope，作为 audit-only 层，不允许修改指数数值。

### 需要纠偏

- README 和旧文档把“先做 Policy Signal”写成阶段目标，已不符合当前验收口径。
- `support_channels.yaml` 仍是政策工具分类，不是 PDF 的完整 SSI 渠道表。
- `scoring_weights.yaml` 是政策信号权重，不是 SSI 的 channel/industry 权重。
- `tests/test_policy_signal.py` 只能验证辅助信号，不能验证 PDF 指数算法。

### V1 不可用 Policy Signal 替代的内容

- 直接财政补贴金额。
- R&D 税收优惠与政府资助 BERD。
- 其他税收优惠金额。
- 信贷补贴或 SOE 融资利差。
- 政府引导基金政府资本或补贴等价。
- 土地价格差。
- SOE net payables 隐性融资优势。
- 债转股支持等价金额。

## 4. 实现方向

V1 应按以下顺序推进：

1. 文档和配置口径统一到 PDF 算法合同。
2. 新增 `SupportObservation` schema 和 observation store。
3. 按九类渠道实现数据接入或 gap 标记。
4. 实现 `StateSupportIntensityCalculator`。
5. 实现双重计算控制和缺失数据策略。
6. 实现 API/export 和方法版本追踪。
7. 用 golden fixtures 验证公式、去重、缺口、敏感性和导出 schema。

## 5. 数据源入口

V1 数据源按“官方政策证据 + quantitative observation”分工：

| 来源 | 入口 | 用途 |
|---|---|---|
| 国务院政策文件库 | `https://sousuo.www.gov.cn/zcwjk/` | 政策依据、发文机关、政策工具 |
| 发改委政策发布 | `https://www.ndrc.gov.cn/xxgk/zcfb/` | 产业、投资、价格、能源政策 |
| 工信部政策文件 | `https://www.miit.gov.cn/zwgk/zcwj/index.html` | 工业、软件、通信、汽车、制造业 |
| 财政部政策发布 | `https://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/` | 财政、补贴、预算、政府采购 |
| 税务总局政策法规库 | `https://fgk.chinatax.gov.cn/` | 税收优惠、R&D 加计扣除、退税 |
| 人民银行规范性文件 | `https://www.pbc.gov.cn/tiaofasi/144941/3581332/index.html` | 信贷、利率、金融支持政策 |
| 中国土地市场网 | `https://www.landchina.com/` | 土地出让、供地结果、地价差 |
| OECD Data | `https://www.oecd.org/en/data.html` | R&D tax support、BERD、国际 benchmark |

Wind、CSMAR、Zero2IPO 等授权源在未配置凭据前只能记录 adapter slot 和 `gap_status=missing`，不得抓取或伪造。

## 6. 验收判断

当前项目状态是“工程骨架可运行，PDF 指数算法未实现”。下一次可验收交付必须至少包含：

- 文档一致：所有项目文档不再把 Policy Signal 写成首版核心指数。
- 算法一致：代码输出的 SSI 能用 PDF 公式手算复核。
- 数据一致：每个指数值能追溯到 observation、source document、normalization base、权重和 method version。
- 边界一致：不写入 `/Users/alex/Documents/金融项目`。
