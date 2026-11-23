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

## AI scene-based furniture ad

The project supports Runway Product Ad as an optional comparison provider. For the current public-data demo, the default AI video route is the official Volcano Ark Seedance 2.5 API.

### Seedance 2.5 — official Volcano Ark

- Standard model: `doubao-seedance-2-5-260628`
- Lower-cost model: `doubao-seedance-2-5-flash-261115`
- API endpoint: `https://ark.cn-beijing.volces.com/api/v3`
- API key environment variable: `ARK_API_KEY`
- Default output: 10 seconds, 720p, 9:16.
- Default preflight budget cap: ¥20 per generated clip.

Official pricing is token-based. For 10 seconds at 720p/9:16 with image references only (no input video), the official formula estimates ¥15.12 for Seedance 2.5 and ¥9.936 for Flash. The actual bill is calculated from the returned `usage.completion_tokens`; the CLI stores both estimate and actual usage in the manifest.

Activate the model in Volcano Ark first. Official activation requires an available balance of at least ¥200, a qualifying savings plan, or an eligible resource pack. This is an account activation threshold, not the cost of a single clip.

```bash
export ARK_API_KEY="..."
fma-seedance-ad \
  --sku YOUR_SKU \
  --data-dir data/public/abo \
  --output-dir data/ai-renders \
  --duration 10 \
  --model doubao-seedance-2-5-260628 \
  --resolution 720p \
  --ratio 9:16 \
  --max-estimated-cost-rmb 20 \
  --scene-preset auto \
  --confirm-external-processing-rights
```

For a lower-cost render, choose `doubao-seedance-2-5-flash-261115`. Outputs are `product-ad.mp4` and `seedance-plan.json`. Generated scenes are not factory-shot footage. AI may alter product geometry; human review must compare silhouette, proportions, color, finish, hardware, drawer/door count, and visible construction against source images.

See [Seedance 2.5 / Volcano Ark](docs/14-seedance-video.md) and [Runway AI Scene Video](docs/13-ai-scene-video.md).

External AI processing is disabled unless the operator explicitly confirms review and authorization. Ordinary CI uses mocked provider responses and never spends paid credits.
