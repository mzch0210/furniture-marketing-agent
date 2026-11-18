# Data Model

## 1. Core product entities

### Workspace
Internal workspace now; tenant boundary later. All business records reserve workspace_id.

### Product
id, workspace_id, sku, name, category, description, status, source_dataset, source_record_id, created_at, updated_at.

### ProductFact
id, product_id, key, value, unit, source_type, source_uri/source_asset_id, source_text, verification_status, verified_by, verified_at, claim_scope and notes.

Verification status should distinguish at least source_reported, unverified, factory_verified and rejected. A public catalog field is not automatically factory_verified.

### Asset
id, product_id, storage_key, media_type, duration, width, height, fps, codec, shot_type, tags, source_uri, source_dataset, source_asset_id, license_id, attribution_text, rights_status, retrieved_at and quality_status.

### Campaign
id, workspace_id, product_id, audience_type (B2B/B2C), target_market, objective, language, angle, channel and status.

### Creative
id, campaign_id, version, hook, script, voiceover, captions, storyboard, approval_status, prompt_version and template_version.

### VideoJob
id, creative_id, status, render_config, input_asset_ids, edit_decision_list, output_asset_id and error_details.

### QualityCheck
id, video_job_id, check_type, status, score, details and checked_at.

### Publication
id, video_job_id, platform, account_reference, published_at, url, caption, hashtags and publication_status.

### PerformanceSnapshot
id, publication_id, captured_at, views, likes, comments, shares, saves, watch_time, inquiries and conversions.

## 2. Data provenance and licensing

Add a DatasetSource/LicenseManifest record or equivalent manifest containing dataset name, publisher, official source URL, license identifier and URL, attribution requirements, version/retrieval date, modifications and local manifest path.

Each downloaded asset must retain a link to its dataset record and the required attribution. Do not assume the dataset license grants rights to unrelated logos, trademarks, endorsements or third-party content.

## 3. Demo and production boundaries

The Public Data Demo populates Product, ProductFact, Asset, Campaign, Creative, VideoJob and QualityCheck using public data. Publication and PerformanceSnapshot remain planned product entities; the Demo may export a publication-ready content pack without connecting a TikTok account.

The later enterprise adapter maps factory product records and approved footage into the same Product/ProductFact/Asset entities. Do not create a separate Demo-only product schema.

## 4. Traceability

Every output video must be traceable to campaign, SKU, source facts, source assets, creative/template version, render settings, QC result and human approval. A future published video also links to its Publication and PerformanceSnapshot records.
