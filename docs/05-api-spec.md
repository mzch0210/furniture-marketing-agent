# API Specification

Base path for the future service API: /api/v1. This document describes the target product contract; the endpoints below are not all implemented in the current repository skeleton.

## Products and facts
- POST /products — create/import SKU.
- GET /products/{product_id} — product details and fact status.
- POST /products/{product_id}/facts — add sourced candidate fact.
- POST /products/{product_id}/facts/{fact_id}/verify — approve/reject a fact.

### Implemented Public Data Demo creative endpoint
- POST /api/creative/generate — generate a deterministic B2B/B2C creative package from a local public SKU and export JSON, Markdown script/storyboard, SRT, caption and attribution files. Requires no paid LLM key.

## Assets
- POST /assets/upload-intents — request upload location.
- POST /assets — register uploaded asset and metadata.
- GET /products/{product_id}/assets — list SKU assets.
- POST /assets/{asset_id}/analyze — enqueue visual analysis.

## Campaign and creative
- POST /campaigns — create campaign.
- POST /campaigns/{campaign_id}/brief — generate brief.
- POST /campaigns/{campaign_id}/creatives — generate script/storyboard.
- POST /creatives/{creative_id}/approve — approve/reject creative.

## Production and quality
- POST /video-jobs — create job.
- GET /video-jobs/{job_id} — inspect job status.
- POST /video-jobs/{job_id}/render — enqueue render.
- POST /video-jobs/{job_id}/quality-check — run QC.
- POST /video-jobs/{job_id}/approve — final approval.

## Publication and analytics
- POST /publications — record manually published video.
- POST /publications/{publication_id}/metrics — append metrics snapshot.
- GET /products/{product_id}/performance — product-level summary.

## Public Data Demo workflow contract

The first local UI may call application services directly rather than exposing every target API endpoint. It must still use the same domain schemas and workflow contracts for:
- importing/searching public products
- retrieving facts and source/license manifest
- creating a campaign brief and creative
- matching assets and generating an edit decision list
- rendering and checking a video job
- recording human approval and exporting the content pack

Long-running operations should eventually return job IDs. Approval actions must be auditable. Agent output is schema-validated. Provider credentials never pass through client payloads. TikTok publication remains manual until a later phase.
