# Public Data Demo Implementation Plan

**Repository purpose:** complete Furniture Marketing Agent product.  
**Current milestone:** Public Data Demo, a first runnable vertical slice using public data only.  
**This document does not redefine the full product scope.**

## 1. Demo objective

Show that a user can select a real furniture product from an openly accessible dataset, understand its source-backed attributes, create a US-English B2B or B2C marketing concept, map the storyboard to available public product media, render a vertical video, run quality checks and export a traceable content pack.

The Demo is an implementation milestone inside the full product repository. Its domain objects and service contracts must remain reusable for later factory data and real footage.

## 2. Primary public dataset: Amazon Berkeley Objects (ABO)

Official dataset: https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html  
AWS Open Data Registry: https://registry.opendata.aws/amazon-berkeley-objects/  
Amazon Science description: https://www.amazon.science/code-and-datasets/amazon-berkeley-objects-abo-dataset

The current official dataset page identifies the license as Creative Commons Attribution 4.0 International (CC BY 4.0). AWS Open Data Registry notes that the license was updated from CC BY-NC to CC BY in 2023. Old papers, blog posts or archived announcements may still mention the earlier license; use the current official dataset page and the license file distributed with the exact downloaded archive as the source of truth.

Dataset facts published by the official source:
- 147,702 product listings and 398,212 unique catalog images.
- 8,222 listings have turntable/360-degree images; the official page describes 72-view sequences.
- 7,953 products have glTF 2.0 3D models.
- The listings archive is approximately 83 MB.
- The downscaled image archive is approximately 3 GB; the 360-degree archive is approximately 40 GB; the 3D model archive is approximately 154 GB.

### Download strategy

1. Download the listings/metadata archive first.
2. Filter to furniture categories relevant to the Demo, initially sofas, chairs, tables and beds.
3. Prefer a small sample with a useful main image and, where available, a 360-degree sequence.
4. Resolve image IDs through the dataset image metadata and fetch only selected assets.
5. Do not download the full image, spins or 3D model archives for the first Demo.
6. Keep downloaded raw assets out of Git. Store a small product manifest and attribution metadata in the repository; let users download assets locally through the documented setup command.

The official page exposes the S3 bucket at s3://amazon-berkeley-objects/ and states that AWS CLI listing can be done without an AWS account. Use the official README and metadata tables to resolve object paths; do not guess image object keys.

## 3. License and attribution requirements

The official dataset page requires attribution to Amazon.com for data, images and 3D models, and credits the dataset builders:
- Matthieu Guillaumin
- Thomas Dideriksen
- Kenan Deng
- Himanshu Arora
- Arnab Dhua
- Xi (Brian) Zhang
- Tomas Yago-Vicente
- Jasmine Collins
- Shubham Goel
- Jitendra Malik

For publication or research use, the dataset page requests citation of the CVPR 2022 paper:

Collins, J., Goel, S., Deng, K., Luthra, A., Xu, L., Gundogdu, E., Zhang, X., Yago Vicente, T. F., Dideriksen, T., Arora, H., Guillaumin, M., & Malik, J. (2022). ABO: Dataset and Benchmarks for Real-World 3D Object Understanding. CVPR 2022.

Every Demo export must include:
- dataset name and official source URL
- CC BY 4.0 license URL
- attribution to Amazon.com and dataset creators
- source item ID and asset ID/path
- retrieval date and any resizing/cropping/editing performed
- statement that the dataset provider does not endorse the Demo or generated marketing copy

The dataset license does not prove that vendor-provided product facts are accurate, and it does not imply endorsement by Amazon or the product brand. Do not imply affiliation or endorsement. Check any additional brand/trademark or third-party rights questions separately before commercial use.

## 4. Product selection and fact handling

Initial sample target: 20–30 furniture SKUs, selected for category diversity and usable media rather than maximum dataset coverage.

Normalize only fields that exist in source records, such as item name, brand, product type, color, material, dimensions, description and source IDs. For every field store:
- original source value
- normalized value and unit, if normalization is lossless
- source record and source URL/path
- source language
- verification status = source_reported or unverified

Missing fields remain Unknown. Image recognition may suggest candidate tags but must not promote them to factual product claims without review.

## 5. End-to-end Demo workflow

1. Dataset setup: download metadata and selected public media; verify archive/license; build local catalog index.
2. Product selection: browse/search the sample catalog and open a product fact sheet.
3. Campaign setup: choose B2B or B2C, objective, audience and content angle.
4. Creative generation: produce English hook, script, voiceover, on-screen text, CTA, storyboard and captions.
5. Asset matching: map storyboard shots to product images or 360-degree frames; show missing live-action coverage.
6. Edit plan: create an editable EDL with timing, source assets, motion/crop and text overlays.
7. Rendering: use FFmpeg to produce a vertical MP4. If no 360-degree media exists, create a clearly labeled still-image motion edit; never describe it as live-action footage.
8. Quality review: check technical output, source provenance, claims, subtitles and CTA; expose approval state.
9. Export: MP4, product fact sheet, campaign brief, script, storyboard, SRT, caption/hashtags, EDL, QC report and attribution manifest.

## 6. Implementation architecture

- PublicCatalogAdapter: download/index/normalize public dataset records.
- Product and ProductFact domain models: shared with future enterprise catalog adapter.
- Strategy/Creative services: deterministic template mode first; optional LLM adapter later.
- Asset service: local cache, metadata and rights/attribution manifest.
- Production service: storyboard matching, missing-shot detection and EDL.
- FFmpeg renderer: deterministic output.
- Quality service: technical checks and source/claim checks.
- Local UI: Streamlit or equivalent; do not add complex SaaS infrastructure.

## 7. Demo boundaries

Included: public catalog import, product facts, campaign brief, English creative, asset matching, EDL, vertical video render, QC, human review state and export.

Not included yet: factory private data, customer accounts, multi-tenant SaaS, billing, automatic TikTok publishing, continuous market intelligence, full enterprise asset management or a foundation video model.

## 8. Acceptance checklist

- Clean clone and setup works using documented commands.
- No paid LLM API key is required for the default path.
- A selected public furniture SKU completes the full workflow.
- Product facts preserve source provenance and unknown values.
- Asset licensing and attribution survive through final export.
- Every storyboard shot is matched or explicitly marked missing.
- MP4 plays and passes ffprobe-based technical checks.
- Image/360-based content is labeled honestly.
- Human review can approve or reject the final artifact.
- Tests and GitHub Actions cover the core workflow.

## 9. Official source references

- ABO official dataset page: https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html
- AWS Open Data Registry: https://registry.opendata.aws/amazon-berkeley-objects/
- Amazon Science dataset page: https://www.amazon.science/code-and-datasets/amazon-berkeley-objects-abo-dataset
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
