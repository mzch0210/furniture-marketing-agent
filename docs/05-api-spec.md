# MVP API Specification

Base path: /api/v1. This is an initial contract; endpoints are not all implemented yet.

## Products
- POST /products — create SKU.
- GET /products/{id} — product and fact status.
- POST /products/{id}/facts — add sourced candidate fact.
- POST /products/{id}/facts/{fact_id}/verify — approve or reject fact.

## Assets
- POST /assets/upload-intents — request upload location.
- POST /assets — register uploaded asset and metadata.
- GET /products/{id}/assets — list SKU assets.
- POST /assets/{asset_id}/analyze — enqueue visual analysis.

## Campaign and creative
- POST /campaigns — create campaign.
- POST /campaigns/{id}/brief — generate brief.
- POST /campaigns/{id}/creatives — generate script/storyboard.
- POST /creatives/{id}/approve — approve or reject creative.

## Production
- POST /video-jobs — create job.
- GET /video-jobs/{id} — inspect status.
- POST /video-jobs/{id}/render — enqueue render.
- POST /video-jobs/{id}/quality-check — run QC.
- POST /video-jobs/{id}/approve — final approval.

## Publication and analytics
- POST /publications — record manually published TikTok video.
- POST /publications/{id}/metrics — append metrics snapshot.
- GET /products/{id}/performance — product-level summary.

Long jobs return IDs. Approval actions are auditable. Agent output is schema-validated. Provider credentials never enter client payloads. TikTok publication remains manual in MVP.