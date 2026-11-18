# Furniture Marketing Agent

家具行业端到端营销视频 Agent。This repository is the complete product; the Public Data Demo is the first runnable vertical slice, not a throwaway prototype.

The product serves furniture factories selling B2B and B2C, prioritizing the English-language TikTok market. The long-term workflow covers product facts, asset management, marketing strategy, scripts/storyboards, video production, quality review, publishing, and performance feedback.

## Delivery strategy

| Phase | Goal |
|---|---|
| Phase 0 | Product design and engineering foundation |
| Phase 1 — Current | Public-data Demo using ABO and other public data |
| Phase 2 | Internal factory pilot using authorized SKUs and footage |
| Phase 3 | Complete internal product |
| Phase 4 | SaaS productization |

The intended production principle remains real footage first, AI scene enhancement second. AI-generated scenes must not be represented as factory-shot footage.

## Public Data Demo

Public product data → source-backed product facts → B2B/B2C brief → English script/storyboard → media matching → EDL → vertical MP4 → QC → human review → content pack.

ABO is the current public-data test source. Review the exact dataset/image rights before redistribution or third-party AI processing. Do not send catalog or factory images to an external AI provider unless the relevant rights and provider terms have been checked.

## Import and browse the public catalog

```bash
pip install -e ".[dev]"
python -m fma.data_sources.abo --data-dir data/public/abo --limit 30
fma-catalog
```

Open http://127.0.0.1:8000 to inspect products, source-backed facts, and media references. Missing attributes remain Unknown; facts are source-reported unless separately verified.

## Generate a deterministic creative and local MP4

```bash
fma-creative --sku YOUR_SKU --audience B2C --objective product_consideration --angle product_overview --duration 30
fma-render --sku YOUR_SKU --audience B2C --objective product_consideration --angle product_overview --duration 30
```

The local renderer is an offline fallback. It creates an animated catalog-still video, not a scene-generated advertisement or factory footage.

## Optional AI scene-based furniture ad

The first paid provider adapter targets Runway's Product Ad Recipe. It accepts 1–10 product images, product information, a creative concept, a vertical ratio, and a 4–15 second duration. Furniture categories map to bedroom, living-room, dining-room, home-office, entryway, or studio presets.

```bash
export RUNWAYML_API_SECRET="..."
fma-runway-ad --sku YOUR_SKU --data-dir data/public/abo --output-dir data/ai-renders --duration 10 --scene-preset auto --confirm-external-processing-rights
```

Outputs: `product-ad.mp4` and `scene-plan.json`. This is a generated scene ad, not factory-shot footage. AI may alter product geometry; human review must compare silhouette, proportions, color, finish, hardware, drawer/door count, and visible construction against source images. Fewer than three images do not establish full multi-view or 360-degree coverage.

The acknowledgement flag does not establish legal rights. External processing is disabled unless the operator explicitly confirms review and authorization. Ordinary CI uses mocked provider responses and never spends paid credits.

See [AI Scene Video](docs/13-ai-scene-video.md).
