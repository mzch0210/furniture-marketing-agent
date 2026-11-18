# Technical Architecture

## 1. Architecture decision

Build the complete product as a modular monolith first, with asynchronous jobs and provider adapters. The Public Data Demo is a deployable local application over a subset of these modules, not a separate throwaway codebase.

## 2. Target logical architecture

- Experience layer: internal web console; later customer-facing SaaS console.
- Application layer: product, asset, campaign, creative, video job, approval, publication and analytics use cases.
- Domain layer: Workspace, Product, ProductFact, Asset, Campaign, Creative, VideoJob, QualityCheck, Publication and PerformanceSnapshot.
- Agent layer: Orchestrator and specialized Product, Market, Strategy, Creative, Production and Quality Agents.
- Infrastructure layer: database, object storage, queue, media processing and external provider adapters.

## 3. Suggested stack

| Layer | Initial choice |
|---|---|
| Runtime | Python 3.11+ |
| API | FastAPI + Pydantic |
| Demo UI | Streamlit or equivalent lightweight local UI |
| Database | SQLite for local Demo; PostgreSQL for shared/internal deployment |
| Queue | Synchronous local execution first; Redis + RQ when jobs need background workers |
| Media | FFmpeg / ffprobe |
| Images | Pillow; OpenCV where useful |
| Storage | Local filesystem for Demo; S3-compatible object storage later |
| Tests / CI | pytest / GitHub Actions |

Do not introduce PostgreSQL, Redis, object storage or microservices into the first Demo unless an acceptance test demonstrates the need. Keep interfaces so these can be added without changing domain logic.

## 4. Data source and provider adapters

- PublicCatalogAdapter: imports ABO and other explicitly licensed public product datasets.
- EnterpriseCatalogAdapter: later imports factory spreadsheets, PIM/ERP exports or approved product feeds.
- AssetStorageAdapter: local Demo storage first; object storage later.
- LLMAdapter: deterministic templates by default; optional configured model provider.
- MediaAdapter: FFmpeg renderer and optional enhancement providers.
- ChannelAdapter: manual TikTok publication record first; platform integration later.

Adapters normalize external data into domain models. Domain logic must not depend on ABO field names or a single LLM/video vendor.

## 5. Public Data Demo execution path

Public catalog import → Product/Fact normalization → campaign brief → structured creative → asset matching → edit decision list → FFmpeg render → QC → human approval/export.

The Demo must work in offline/template mode after the public sample data and assets have been downloaded. Network access is needed only for initial dataset acquisition or optional external model calls.

## 6. Workflow state machine

DRAFT → PRODUCT_FACT_REVIEW → ASSET_ANALYSIS → MARKETING_BRIEF → CREATIVE_REVIEW → SHOT_MATCHING → OPTIONAL_SCENE_ENHANCEMENT → RENDERING → QUALITY_CHECK → FINAL_VIDEO_REVIEW → READY_TO_PUBLISH → PUBLISHED → PERFORMANCE_LOGGED.

The Demo may omit later publication/analytics states from its executable path, but must not redefine or conflict with the full product state model.

## 7. Video production

Original video or product images/360° frames → metadata normalization → shot selection → optional approved enhancement → edit decision list → FFmpeg render → subtitles/audio → technical and content QC → reviewable MP4.

Image-based motion and 360° turntable output must be labeled as such. It is not equivalent to live-action product footage. The production product continues to prioritize real footage, with AI scene enhancement as a supporting capability.

## 8. Product truth, rights and traceability

- Every factual claim links to ProductFact records and source provenance.
- Every Asset records source, license/rights status, attribution and retrieval time.
- AI output cannot silently promote unverified facts to verified facts.
- Every output records prompt/template version, model/provider (if any), source assets and render settings.
- Public dataset licensing does not imply product endorsement or guarantee the accuracy of vendor-supplied descriptions.

## 9. Security and SaaS evolution

The public repository must never contain API keys, private factory documents, unpublished footage, account credentials or customer personal data. Use local environment files and GitHub Actions secrets.

Keep workspace_id in business entities from the start. Run one local workspace for Demo; add authentication, role-based access, tenant isolation, billing and enterprise controls only in later SaaS phases.
