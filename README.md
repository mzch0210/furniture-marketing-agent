# Furniture Marketing Agent

家具行业端到端营销视频 Agent。**本仓库建设的是完整产品；Public Data Demo 只是当前优先实施和验证的第一个可运行阶段，不是独立的一次性原型。**

面向家具工厂，优先服务 TikTok 英语市场，覆盖 B2B 与 B2C 营销场景。产品目标是把商品信息、素材管理、市场与营销策略、脚本分镜、视频生产、质量审核、发布管理和效果分析整合为可追溯的工作流。

## Product vision

完整产品能力：

1. 商品与 SKU 管理、产品事实知识库
2. 图片/视频素材资产管理与智能检索
3. 市场研究、受众分析和营销策略
4. 英文及多语言脚本、分镜、字幕和拍摄清单
5. 实拍素材匹配、缺失镜头识别和 AI 场景增强
6. 自动剪辑、渲染、质量检查和人工审核
7. TikTok 等渠道的发布管理
8. 内容表现、询盘和转化数据回流
9. 面向未来 SaaS 的 Workspace、权限和租户隔离

## Delivery strategy

| 阶段 | 目标 | 数据 |
|---|---|---|
| Phase 0 | 完整产品设计与工程基础 | 示例/模拟数据 |
| Phase 1 — Current | Public Data Demo：跑通端到端核心链路 | ABO 等公开数据 |
| Phase 2 | 家具工厂内部试点 | 工厂授权 SKU 和实拍素材 |
| Phase 3 | 完整内部产品 | 企业商品、素材、运营数据 |
| Phase 4 | SaaS 产品化 | 多 Workspace、多用户和商业化能力 |

**当前阶段边界：** 只实现足以验证核心产品价值的一条完整纵向切片。Demo 使用公开商品图像生成动态展示视频时，必须明确标记为图片动画/360° 展示，不得将其描述为工厂实拍视频。正式产品仍坚持“实拍素材为主，AI 场景增强为辅”。

## Public Data Demo

当前优先验证的链路：

公开商品数据导入
→ 商品事实卡及来源记录
→ B2B/B2C 营销 brief
→ 英文脚本、分镜和字幕
→ 公开图片/360°素材匹配
→ 剪辑计划
→ 竖屏 MP4 渲染
→ 技术与内容质检
→ 人工审核
→ 导出视频和营销内容包

首选技术验证数据源为 [Amazon Berkeley Objects (ABO)](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html)。先读取商品列表，只下载入选 SKU 所需的图片/360°素材；不下载完整图片、360°或 3D 大型归档。注意官方落地页与 AWS Registry 当前显示的 CC BY / CC BY-NC 元数据存在不一致；在核对具体归档 LICENSE 并获得必要澄清前，不将该素材用于商业再分发。详见 [Public Data Demo Plan](docs/09-public-data-demo-plan.md)。

## Import the public ABO furniture catalog

The adapter downloads the official listings archive, license text and compressed image metadata index. It does not download large image, spin or 3D archives.

```bash
pip install -e ".[dev]"
python -m fma.data_sources.abo --data-dir data/public/abo --limit 30
```

Outputs are written under gitignored `data/public/abo/processed/`: `products.json` and `dataset-manifest.json`. Use `--offline` after downloading source files. Missing attributes remain Unknown and facts are marked `source_reported`.

## Browse the local public product catalog

After importing the ABO sample, start the read-only browser:

~~~bash
fma-catalog
# or: uvicorn fma.app:app --host 127.0.0.1 --port 8000
~~~

Open http://127.0.0.1:8000. Search/filter the local SKU sample, inspect source-backed product facts and explicit Unknown attributes, preview official catalog image references, and review the dataset/license/attribution manifest. The browser reuses the shared catalog models and does not infer product attributes.

See docs/10-public-catalog-browser.md.

## Generate a deterministic marketing creative

Generate an English B2B/B2C brief, hook, timed voiceover, on-screen copy, storyboard, subtitles and caption without a paid LLM key:

~~~bash
fma-creative --sku YOUR_IMPORTED_SKU --audience B2B --objective lead_generation --angle product_overview --duration 30
~~~

Exports are written under gitignored data/outputs/creatives/. The generator only uses eligible source-backed product facts, records fact provenance and leaves unknown attributes unclaimed. Human review is required before publication.

See docs/11-campaign-creative-generation.md.

## Render a public-data vertical MP4

After importing the ABO catalog, render a playable 9:16 H.264 MP4 from one selected public SKU:

~~~bash
fma-render --sku YOUR_IMPORTED_SKU --audience B2C --objective product_consideration --angle product_overview --duration 30
~~~

The renderer downloads only selected official product image objects, prefers original-resolution images and falls back to the small catalog image, builds an editable EDL, marks missing product shots and validates the MP4 with ffprobe. Output: \`data/renders/{campaign_id}/{sku}/\`. Install FFmpeg and a TrueType font first. This first Demo output is a silent catalog-image animation, not live-action footage.

See [Video Production](docs/12-video-production.md).

## Product architecture

- Orchestrator：工作流编排、状态机、重试和审批
- Product Agent：商品事实提取、来源追踪和审核
- Market Agent：市场、受众和内容机会
- Strategy Agent：营销目标、卖点、内容角度和 CTA
- Creative Agent：脚本、分镜、字幕和拍摄清单
- Production Agent：素材检索、镜头匹配、剪辑计划和渲染
- Quality Agent：产品事实、视觉一致性和成片质量检查

Agent 输出结构化结果；事实校验、媒体渲染和质量规则尽量由确定性工具执行。模型与媒体服务通过 Adapter 接入。

## Repository status

当前已实现公开商品导入、商品浏览、确定性营销内容生成，以及基于公开商品图片的本地 EDL/MP4 渲染切片。轻量 UI、端到端 QC、人工审核和内容包整合仍在 Issue #13 中；不要把图片动态化视频误认为工厂实拍。

## Documentation

- [Product Requirements](docs/01-product-requirements.md)
- [Technical Architecture](docs/02-technical-architecture.md)
- [Agent Design](docs/03-agent-design.md)
- [Data Model](docs/04-data-model.md)
- [API Specification](docs/05-api-spec.md)
- [Development Roadmap](docs/06-development-plan.md)
- [Video Quality Standard](docs/07-video-quality-standard.md)
- [Video Production](docs/12-video-production.md)
- [Validation Plan](docs/08-mvp-validation.md)
- [Public Data Demo Plan](docs/09-public-data-demo-plan.md)

## Development principles

1. 完整产品是长期建设目标，Demo 是阶段性验证路径。
2. 模块化单体优先，避免过早微服务化。
3. Demo 与正式产品复用领域模型、服务边界和 Agent 输出契约。
4. 数据来源、许可证、产品事实、素材权利和生成过程必须可追溯。
5. 未经验证的产品属性不得作为事实性营销声明。
6. 正式产品以真实商品和实拍素材为主，AI 只在受控范围内增强。
7. 不把私有工厂资料、客户信息、账号凭据或 API Key 提交到公开仓库。
