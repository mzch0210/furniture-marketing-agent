# Data Model

## Core entities
- Workspace: internal workspace now; tenant boundary later.
- Product: id, workspace_id, SKU, name, category, description, status and timestamps.
- ProductFact: product_id, key, value, unit, source reference, verification status, verifier and time.
- Asset: product_id, storage key, media type, duration, dimensions, FPS, codec, shot type, tags, source and rights status.
- Campaign: product_id, audience type (B2B/B2C), target market, objective, language, angle and status.
- Creative: campaign_id, version, hook, script, voiceover, captions, storyboard, approval and prompt version.
- VideoJob: creative_id, status, render config, input assets, EDL, output asset and error details.
- QualityCheck: video_job_id, check type, status, score and details.
- Publication: video_job_id, platform, account reference, publication time, URL, caption and hashtags.
- PerformanceSnapshot: publication_id, capture time, views, likes, comments, shares, saves, watch time, inquiries and conversions.

## Traceability
A published video must be traceable to its campaign, SKU, approved claims, source footage, creative version, prompt/template version, render configuration, QC record and publication metrics.

Reserve workspace_id on business entities. MVP may use one workspace, but design storage and queries for future workspace isolation.