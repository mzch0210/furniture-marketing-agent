# MVP Product Requirements

## Positioning
An internal workflow system for furniture manufacturers creating TikTok short-form videos for English-language markets. Initial use cases cover both B2B and B2C. The product is not a generic text-to-video generator: it connects approved SKU facts, real footage, localized creative, editing, quality review and performance feedback.

## Production principles
- Real product footage first; AI scene enhancement second.
- Product facts must have a source and verification status.
- Never invent dimensions, materials, certifications, load limits, accessories, MOQ or delivery promises.
- Human approval remains required for product facts, creative and final video.
- Start as an internal tool; consider SaaS only after the workflow is validated.

## MVP workflow
SKU intake → fact review → asset library → marketing brief → English script/storyboard → footage matching → missing-shot list → optional enhancement → FFmpeg render → automated QC → human approval → manual TikTok publication → metrics and inquiry log.

## P0
Product facts; SKU-linked media assets; B2B/B2C campaign brief; script and storyboard; footage matching; reshoot checklist; deterministic rendering; QC; approval history; manual publication log; performance snapshots.

## P1
Creative variants, A/B testing, AI voiceover, localization, better semantic search, platform analytics integrations, multi-workspace SaaS and billing.

## Out of scope for MVP
Foundation video model, autonomous publishing/comment replies, microservices, full SaaS billing/permissions and replacing real footage with synthetic product imagery.

## Pilot metrics
Production time, editing minutes, revision count, factual errors, visual mismatch, QC pass rate, asset reuse, views/retention/engagement and qualified inquiries. Do not use one video's views as the only success measure.