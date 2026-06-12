# China Policy Analyse：当前进展评估与 PDF 口径纠偏

日期：2026-06-12

## 1. 当前结论

项目已经在独立目录 `/Users/alex/Documents/china policy analyse` 建好基础骨架，且与 `/Users/alex/Documents/金融项目` 隔离。现有能力可以继续复用：

- 独立 Python `.venv`、配置目录、workspace 和 exports。
- P0 官方政策源配置。
- 真实公开网页 crawler、基础分类器、辅助 `policy_signal` 快照。
- `runtime_guard`、`validate_project.py`、基础 pytest。
- 从原 PDF 分析迁移过来的项目文档。

当前实现已经不再停留在 `PolicySignalCalculator`。正式 SSI 计算底座、真实 `SupportObservation` 抽取管线、OECD benchmark 公开 API 入口已经落地。`PolicySignalCalculator` 仍存在，但只作为政策文本热度和可量化线索评分：

```text
score = issuer_weight * channel_weight * quantifiability_weight * evidence_quality
```

这不能作为 V1 验收指数，也不会进入 SSI 金额聚合。V1 核心现在由 `StateSupportIntensityCalculator` 和 `SupportObservation` 驱动：按支持渠道形成可审计 observation，归一化到行业基数，做权重聚合、双重计算控制、缺口披露和外部 benchmark。

## 2. PDF 口径 vs 当前实现

| 维度 | PDF 口径 | 当前状态 | V1 要求 |
|---|---|---|---|
| 指数目标 | State Support Intensity / China State Support Index | SSI 引擎已实现，Policy Signal 仅辅助 | 继续补真实数据覆盖 |
| 支持渠道 | 九类金额或代理金额渠道 | 已配置 PDF 九类渠道 | 每类渠道都要产出 observed/proxy/estimated/missing |
| 数据输入 | 支持金额、基数、证据质量、覆盖率 | `SupportObservation` 已实现 | 扩大真实源 adapter 覆盖 |
| 归一化 | 行业 GDP、产值、营收、资产、产能等 | `normalization_bases.yaml` 已接入，默认空缺 | 接入官方或授权基数，不得伪造 |
| 双重计算 | R&D、BERD、税收、土地、基金要去重 | 引擎和测试已覆盖核心规则 | 扩展交易级土地/基金去重 |
| 不确定性 | low/base/high、Monte Carlo 或敏感性 | sensitivity runs 已实现 | low/base/high 区间仍需补 |
| Benchmark | CSIS/IMF/OECD/WTO 对照 | OECD RDTAX/BERD API 已接入 benchmark 文件 | CSIS/IMF/WTO 对照仍需补 |

## 3. 进展状态

### 已完成

- 新项目目录和基础 Python 包。
- 官方政策源注册表雏形。
- 真实公开 HTML 抓取、文档 raw/text/metadata 存储和 content hash。
- 规则分类行业、支持渠道、可量化程度。
- 辅助 `policy_signal` 快照导出。
- 项目边界检查，避免写入金融项目。
- OpenFisca country package `openfisca_china_policy_index`，用于正式 SSI 公式计算。
- `policy_index/ssi_engine`，用于 Pydantic/Pointblank 校验、Polars 聚合、DuckDB 存储和 SSI 快照导出。
- Camel-AI 审查 envelope，作为 audit-only 层，不允许修改指数数值。
- `policy_index/observation_extractor.py`，从真实政策正文和分类结果抽取金额型 `SupportObservation`。
- `policy_index/oecd_benchmark.py`，通过 OECD SDMX CSV 公开 API 拉取中国 R&D tax support / BERD benchmark。
- 空 observation 状态可稳定导出 snapshot，并明确 `missing_required_channels` / `no_observations` warning。

### 需要纠偏

- 公开部委站点在当前机器上出现 TLS EOF / empty reply，真实 crawler 代码已就绪，但本机网络 smoke 暂未抓到 MOF/NDRC/PBC 文档。
- LandChina 首页可连通，但当前 generic parser 未发现详情链接，需要补 LandChina 专用列表解析。
- `normalization_bases.yaml` 默认仍为空，缺行业归一化基数时只能输出 gap，不能产生 SSI 值。
- 未授权 Wind、CSMAR、Zero2IPO 等源仍只能保留 adapter slot 和 gap。

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

V1 后续应按以下顺序推进：

1. 文档和配置口径统一到 PDF 算法合同。
2. 为 MOF/税务/PBOC/LandChina 增加站点专用 parser 和重试/镜像策略。
3. 接入可授权的财政、税务、上市公司、土地成交、基金和融资数据。
4. 填充真实 normalization base 配置。
5. 增加 low/base/high 区间和更完整 benchmark 对照。
6. 继续用 golden fixtures 验证公式、去重、缺口、敏感性和导出 schema。

## 4.1 2026-06-12 真实 smoke 结果

已在本项目目录运行：

```bash
.venv/bin/python scripts/validate_project.py
.venv/bin/python scripts/fetch_oecd_benchmark.py
.venv/bin/python scripts/extract_observations.py
.venv/bin/python scripts/build_ssi_index.py
```

结果：

- 隔离校验通过，workspace/export 均位于 `/Users/alex/Documents/china policy analyse`。
- OECD 公开 API 成功写入 `workspace/observations/oecd_rdtax_berd_china.json`，包含 7 条观测 benchmark 和 1 条 OECD 缺失状态。
- MOF、NDRC、PBC 在本机 `httpx`/`curl` 下均返回 TLS EOF；HTTP 明文入口返回 empty reply。
- 当前无公开政策文档入库时，`exports/latest/state_support_index_snapshot.json` 能稳定输出空 SSI 快照、九类渠道缺失列表和 `no_observations` warning。

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

当前项目状态是“PDF 一致计算引擎和真实数据管线已落地，但真实中国政策源抓取受本机网络/TLS 和站点专用 parser 限制，尚未形成可发布 SSI 数值”。下一次可验收交付必须至少包含：

- 文档一致：所有项目文档不再把 Policy Signal 写成首版核心指数。
- 算法一致：代码输出的 SSI 能用 PDF 公式手算复核。
- 数据一致：每个指数值能追溯到 observation、source document、normalization base、权重和 method version。
- 边界一致：不写入 `/Users/alex/Documents/金融项目`。
