# Deterministic Campaign Brief, Script and Storyboard

Issue #11 implements a no-paid-model-key creative workflow. It reads the normalized local catalog and dataset manifest, builds a structured B2B/B2C creative package and exports reviewable English assets. The output is a deterministic template draft, not live market research or a claim that a creative has been performance-tested.

## Generate from the CLI

Import the ABO sample first if it is not already present:

~~~bash
python -m fma.data_sources.abo --data-dir data/public/abo --limit 30
~~~

Generate an English B2B lead-generation creative:

~~~bash
fma-creative --sku B0EXAMPLE --audience B2B --objective lead_generation --angle material_spotlight --duration 30
~~~

Replace B0EXAMPLE with a real SKU from the local catalog. For B2C product consideration:

~~~bash
fma-creative --sku B0EXAMPLE --audience B2C --objective product_consideration --angle product_overview --duration 30
~~~

The CLI prints the structured package and export paths. Default exports are written under gitignored data/outputs/creatives/{campaign_id}/{sku}/. Override --data-dir, --output-dir, --target-market and --campaign-id as needed.

## Local API

POST /api/creative/generate

Example JSON:

~~~json
{
  "sku": "B0EXAMPLE",
  "audience": "B2B",
  "objective": "lead_generation",
  "angle": "material_spotlight",
  "target_market": "United States",
  "platform": "TikTok",
  "language": "en-US",
  "duration_seconds": 30
}
~~~

The response contains the validated brief, timed script, storyboard, claim-reference index, caveats and export file metadata. Unknown SKUs return 404; missing local catalog data returns 503; invalid request schemas return 422.

## Supported request values

- Audience: B2B, B2C.
- Objective: brand_awareness, product_consideration, lead_generation, traffic.
- Angle: product_overview, color_spotlight, material_spotlight, dimension_spotlight, brand_spotlight, style_spotlight.
- Duration: 15–60 seconds; default 30 seconds.
- Platform and language are explicit metadata; the initial copy templates are English (en-US).

## Fact-safety rules

- Only source_reported and factory_verified ProductFact records may be used as factual claims. unverified and rejected facts are excluded.
- Every source-specific statement has a ProductClaimReference with fact key, value, source dataset, source record ID, source field, source URI and verification status.
- The generation service validates every reference against the selected SKU's current source facts before export.
- If a requested angle has no eligible fact, the copy says that the public catalog record does not supply that information. It does not infer the property from the image, category or free-text description.
- MOQ, lead time, warranty, certification, load capacity, price, stock, shipping and commercial promises are never invented. B2B CTAs ask the supplier for confirmation.
- Source-reported is not factory-confirmed. Human review is required before publication.
- Candidate image IDs are references for the next production stage, not confirmed shot matches. Image animation must not be represented as live-action footage.

## Output files

Each run exports:
- creative-package.json — complete schema-validated structured output and provenance.
- script.md — English hook, timed voiceover, on-screen copy and caveats.
- storyboard.md — timed shots, purpose, visual direction, asset candidates and fact references.
- subtitles.srt — timed voiceover subtitle draft.
- caption.txt — TikTok caption and suggested hashtags.
- attribution.txt — dataset source, record, license and attribution.

The template version is recorded as fma-creative-en-us-v1.0.0. Identical inputs yield the same campaign identity and creative content.

## TikTok creative assumptions

The template uses a hook → body → close structure, vertical-first visual directions, captions and a clear CTA. This is consistent with TikTok for Business public creative guidance; it is a design reference, not a guarantee of campaign performance:
- https://ads.tiktok.com/business/en/guides/video-advertising-guide
- https://ads.tiktok.com/business/en/creative-codes

## Scope boundary

No LLM call, live market research, trend scrape, product image analysis, shot matching, rendering, TikTok publication or performance prediction occurs in this issue. Those functions remain separate stages in the full product roadmap.
