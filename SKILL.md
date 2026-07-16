---
name: tender-bid-assistant
description: 中小企业投标助手。解析招标公告，从招投标模板知识库匹配最合适模板，生成标书初稿（商务标/技术标/报价文件）、公告摘要、逐条响应矩阵、合规红线初筛、资质缺口清单、报价建议，并可输出 Word 初稿。适用于代写标书服务、招投标知识库构建、监控→生成闭环。触发词：投标、标书、招投标、代写标书、招标公告解析、标书模板、资质缺口。
---

# 投标助手（tender-bid-assistant）

帮中小企业把"看到招标公告 → 写出能交的标书"这条链路自动化。本 skill 是**代写标书服务**的提效引擎：你（或团队）做精修与最终交付，skill 负责初稿生成。

## 工作链路（catalog 版，基于真实标书库）

```
真实标书库(2354 文件,54 行业) ──build_catalog.py──> data/catalog.json(轻量索引:标题/章节/行业/快照)
                                                    │
招标公告(文本/监控推送) ──gen_bid.py──┤ 在 catalog 中按行业+章节关键词匹配 Top3 真实模板
                                       └ 重新抽取最佳模板全文 → 公告摘要 + 合规初筛 + 响应矩阵
                                                            + 标书大纲初稿 + 资质缺口 + 报价建议
                                                    │
                                  邮件/企微推送(接用户已有监控+邮件 skill)
```

> 真实库默认路径：`private_bid_docs/`（含 .doc/.docx/.pdf，用 antiword+python-docx+pdfplumber 抽取）。该目录属于私有素材，不随公开仓库发布。
> 老 `.doc` 经 antiword 抽文本、章节靠启发式识别；`.docx` 用 python-docx（含表格）；`.pdf` 用 pdfplumber。

## 用法

1. **构建库索引**（一次性，约 10 分钟，后台跑）：
   `python scripts/build_catalog.py --root "./private_bid_docs" --out-dir data`
   生成 `data/catalog.json`（轻量索引）+ `data/catalog_report.md`（各行业概览）。
2. **准备客户画像**：复制 `templates/company_profile.yaml`，填入客户公司资质、业绩、团队、服务区域和报价策略。
3. **生成标书**：拿到招标公告文本（或监控 skill 推送），运行
   `python scripts/gen_bid.py --tender 公告.txt --company 客户画像.yaml --out 输出目录 --docx`
   输出 `标书初稿.md` + `标书初稿.docx`（公告摘要、合规初筛、推荐模板、标书大纲、逐条响应矩阵、资质缺口、报价建议、交付清单、风险）。
4. **接监控闭环**：把你已有"招投标监控+邮件" skill 发现的公告，作为 `--tender` 输入，自动产出初稿并推送。

常用命令：

```powershell
python scripts/gen_bid.py `
  --tender "examples/notice.txt" `
  --company "templates/company_profile.yaml" `
  --out "output/demo" `
  --top 5 `
  --docx
```

自测：

```powershell
python _selftest/run_all.py
```

## 商业化交付建议

- 售前：用公告摘要、投标可行性、资质缺口、风险初筛判断是否接单。
- 初稿：交付 Markdown/Word 初稿，包含商务标、技术标、报价文件的章节结构和逐条响应矩阵。
- 精修：由人工补齐客户真实资质、业绩证明、人员证书、报价明细和承诺函。
- 复核：最终投递前做合规红线、评分点响应、附件完整性、格式装订、截止时间五项检查。
- 沉淀：每次中标/废标/陪跑复盘后，把评分办法、扣分点、优秀技术段落沉淀到 `knowledge/{行业}/{场景}.yaml`。

## 知识库 schema（可选深度层 knowledge/{行业}/{场景}.yaml）

catalog 已覆盖全行业匹配；若要对某行业做"填空式"精修模板，可再用旧流程：
`parse_bid_doc.py` 解析 → `build_kb.py --auto` 入库 → 在 yaml 里补全 `qualifications/scoring/snippets/deductions`。

```yaml
industry: 软件开发/IT运维/系统集成
scenario: 政府采购/国企/高校/医院
applicable: 何时用本模板
qualifications:        # 资质门槛
  - name: 营业执照
    must: true
scoring:               # 评分权重之和=100
  price: 30
  technical: 40
  commercial: 30
sections:              # 章节大纲
  - id: commercial
    title: 商务标
    outline: [公司简介, 类似业绩, 项目团队, 售后服务]
snippets:              # 可填充变量 {{company}} {{year}}
  commercial: |
    我公司 {{company}} 成立于{{found_year}}年，专注于……
deductions:            # 常见扣分项
  - 未提供社保缴纳证明
  - 技术方案未响应评分点
```

## 边界（红线）

- 买来的模板数据集通常**禁止原样转售**；本 skill 只将其作为"生成"知识库使用，不开源/转卖原始文件。
- 代写标书属咨询服务；**严禁**陪标、串标、围标等违规操作。
- 客户专有数据（资质、历史标书）按"绝不开源客户专有逻辑"红线处理。
- 初稿必须由人工审核后方可正式投递。
- 禁止虚构资质、业绩、授权、人员证书、社保纳税证明和合同发票。

## 依赖

`python-docx`、`pdfplumber`、`pyyaml`（已装在隔离 venv：`envs/tender-bid`）；`.doc` 抽取依赖系统 `antiword`。
运行：`envs/tender-bid/Scripts/python.exe scripts/build_catalog.py ...`
