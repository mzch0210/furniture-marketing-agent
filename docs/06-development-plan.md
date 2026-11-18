# Development Roadmap

The repository targets the complete Furniture Marketing Agent product. The first implementation milestone is a runnable Public Data Demo, not a separate throwaway project. Estimates below are planning estimates and should be adjusted after the first working vertical slice.

## Phase 0 — Product and engineering foundation

Status: product scope and initial architecture documented; Python skeleton and basic CI exist.

- Keep full product requirements, domain model and Agent boundaries.
- Keep provider adapters and workspace ownership in the architecture.
- Make explicit which functions are target contracts and which are implemented.

Exit criteria: the team agrees on the product roadmap and Demo acceptance criteria.

## Phase 1 — Public Data Demo (current priority)

Target: one local application can produce a complete, reviewable furniture marketing video package using public data only.

### Sprint 1 — Public catalog and provenance
- Implement ABO public catalog adapter.
- Select furniture categories and a small reproducible sample of SKUs.
- Normalize metadata into Product/ProductFact.
- Preserve source URL, source record ID, license, attribution and retrieval date.
- Download only selected product images/360° assets; do not mirror the full archives.

Exit criteria: browse/select a public SKU and inspect source-backed facts; unknown attributes remain unknown.

### Sprint 2 — Campaign and creative
- Implement B2B/B2C campaign brief.
- Generate English hook, script, voiceover, on-screen text, CTA and storyboard.
- Provide deterministic template mode with no paid API requirement.
- Keep optional LLM integration behind an adapter.
- Link factual claims to ProductFact IDs.

Exit criteria: structured creative output validates and contains no unsupported product claims.

### Sprint 3 — Asset matching and rendering
- Match storyboard shots to available catalog images or 360° sequences.
- Mark absent live-action shots as missing; generate a reshoot checklist.
- Produce an editable edit decision list.
- Render a 9:16 MP4 with FFmpeg.
- Clearly label image-motion and 360° turntable outputs as catalog-image-based video.

Exit criteria: selected SKU produces a playable MP4 and all shots have matched or missing status.

### Sprint 4 — UI, QC and reproducibility
- Add lightweight local UI.
- Run technical QC and content/provenance checks.
- Add human review state and export content pack.
- Add tests and CI coverage for the end-to-end path.
- Document install, data download, run, output and attribution.

Exit criteria: a new user can clone, install, run the sample workflow and produce the same class of artifacts without paid model credentials.

## Phase 2 — Internal furniture-factory pilot

- Connect one factory's authorized SKU/product data.
- Ingest factory-approved real photos and video footage.
- Test the same Product/Asset/Campaign/Creative/VideoJob model.
- Compare current manual process with Agent-assisted production.
- Record turnaround time, revision count, factual errors, QC results and TikTok performance where available.

Exit criteria: the workflow is useful with real product assets and factory facts; the image-only Demo limitations are understood.

## Phase 3 — Complete internal product

Implement and harden the full product modules:
- enterprise SKU and product fact management
- asset library, permissions and semantic retrieval
- market research and strategy workflows
- multi-creative generation and experiment management
- real-footage-first production and controlled AI enhancement
- review queues, audit logs and collaboration
- publication management and analytics/lead feedback

Exit criteria: repeatable end-to-end operation by the internal team across multiple products and campaigns.

## Phase 4 — SaaS productization

Add multi-tenant isolation, authentication, roles, billing, customer onboarding, usage limits, monitoring, data retention and customer-facing integrations only after internal workflow validation.

## Definition of Done

A milestone is done only when its acceptance criteria, tests, error handling, logs, documentation and reproducible demonstration are complete. A document or placeholder endpoint alone does not count as implementation.
