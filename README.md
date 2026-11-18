# Furniture Marketing Agent

家具行业端到端营销短视频 Agent。

本项目面向家具工厂的 TikTok 英语市场营销场景，目标是把“商品信息 → 素材整理 → 营销策略 → 英文脚本/分镜 → 实拍素材匹配 → AI 场景增强 → 自动化剪辑 → 质检 → 人工发布 → 数据回流”整合为一条可复用的生产流水线。

## 当前产品决策

| 项目 | 决策 |
|---|---|
| 首要市场 | TikTok 英语市场 |
| 首批客户 | 家具工厂，B2B + B2C |
| 视频路线 | 实拍素材为主，AI 场景增强为辅 |
| 产品阶段 | 先内部系统，再 SaaS 化 |
| MVP 发布 | TikTok 首期人工发布，系统记录发布结果 |
| 默认视频 | 25–27 秒、9:16、1080×1920、30fps、H.264/MP4、英文字幕 |
| 默认镜头 | 7 组实拍镜头 |
| 内容结构 | Hook → Body → CTA |
| 核心原则 | 产品事实优先、真实产品优先、AI 不得虚构产品属性 |

## 端到端流程

商品资料导入
→ Product Agent 提取与事实审核
→ 素材上传与分析
→ Marketing Brief
→ Market Agent / Strategy Agent
→ Creative Agent 生成英文脚本、分镜与拍摄清单
→ Production Agent 素材匹配、缺口识别、AI 场景增强
→ FFmpeg 成片
→ Quality Agent 自动质检
→ 人工审核
→ 人工发布 TikTok
→ 数据与询盘回流
→ 下一轮内容优化

## Agent 角色

- Orchestrator：负责任务编排、状态机和人工审批节点。
- Product Agent：建立 SKU 产品事实卡和产品知识库。
- Market Agent：整理英语市场、受众和内容机会。
- Strategy Agent：确定内容角度、卖点优先级和 CTA。
- Creative Agent：生成英文脚本、分镜、字幕、配音文案和拍摄清单。
- Production Agent：匹配实拍素材、识别缺口、生成剪辑计划并调用视频处理能力。
- Quality Agent：检查产品事实、视觉一致性、字幕、时长、画幅、音频和成片完整性。

## MVP 人工控制点

1. 商品事实审核
2. 创意/脚本审核
3. 最终视频审核

这三个节点不是缺陷，而是 MVP 阶段保证家具产品营销准确性的核心机制。

## 项目结构

~~~
.
├── .github/workflows/ci.yml
├── docs/
│   ├── 01-product-requirements.md
│   ├── 02-technical-architecture.md
│   ├── 03-agent-design.md
│   ├── 04-data-model.md
│   ├── 05-api-spec.md
│   ├── 06-development-plan.md
│   ├── 07-video-quality-standard.md
│   └── 08-mvp-validation.md
├── src/fma/
│   ├── __init__.py
│   ├── models.py
│   └── pipeline.py
├── tests/
│   └── test_pipeline.py
├── .env.example
├── .gitignore
└── pyproject.toml
~~~

## 开发原则

1. 先跑通一条视频生产链，再扩展 Agent 数量。
2. 模块化单体优先，不在 MVP 阶段做微服务。
3. 所有模型/视频服务使用 Adapter，避免锁定单一供应商。
4. 产品事实和素材来源必须可追溯。
5. AI 生成只能增强真实产品，不得改变产品真实结构、尺寸、材质或功能。
6. SaaS 能力提前做数据边界设计，但不提前建设复杂多租户系统。

详细文档见 docs/。
