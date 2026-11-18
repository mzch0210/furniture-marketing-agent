# AI Scene-Based Furniture Video — First Provider Integration

## Goal

Add an optional, paid AI-video path without replacing the deterministic local renderer. The local ABO MP4 remains a technical fallback. This integration creates one short scene-based product-ad clip from selected catalog product images.

## Provider choice

The first provider adapter targets Runway's Product Ad Recipe:

- API endpoint: `POST https://api.dev.runwayml.com/v1/recipes/product_ad`
- API header: `X-Runway-Version: 2024-11-06`
- Recipe workflow version pinned to `2026-07`
- 1–10 product reference images; up to four optional style references
- 4–15 seconds; vertical ratio supported, including `720:1280` and `1080:1920`
- Product Ad task is asynchronous; poll `GET /v1/tasks/{id}` until success/failure
- This integration sets `audio=false`; dedicated English voiceover/TTS and licensed music are a separate next step

Official documentation: https://docs.dev.runwayml.com/recipes/product-ad/ and https://docs.dev.runwayml.com/guides/using-the-api/.

## Category-aware scene presets

The adapter maps common furniture categories to a scene preset:

| Product category | Default scene |
|---|---|
| Bed, headboard, dresser, nightstand, wardrobe | Bedroom |
| Sofa, recliner, coffee table, TV stand, bookcase | Living room |
| Dining table, dining chair, bar stool | Dining room |
| Desk, office chair | Home office |
| Console table, bench | Entryway |
| Unknown / unmapped | Neutral studio |

An operator can override the automatic preset. The prompt treats supplied product images as the only source of truth for product geometry and visible details. It explicitly prohibits invented hidden sides and fake 360-degree orbits.

## Run locally

1. Import the public catalog.
2. Review the dataset/image rights and third-party processing permission.
3. Configure `RUNWAYML_API_SECRET`.
4. Run:

~~~bash
fma-runway-ad --sku YOUR_SKU --data-dir data/public/abo --output-dir data/ai-renders --duration 10 --scene-preset auto --confirm-external-processing-rights
~~~

Outputs:

- `data/ai-renders/{sku}/product-ad.mp4`
- `data/ai-renders/{sku}/scene-plan.json`

The manifest records product image references, preset, creative direction, provider task ID, output checksum, rights/attribution metadata, and a human-review checklist.

## Manual GitHub Actions run

The `Runway Product Ad Demo` workflow is manual-only. Configure the repository secret `RUNWAYML_API_SECRET`, import the selected catalog SKU, and explicitly set `confirm_external_processing_rights=true` only after checking the relevant image rights and third-party provider terms. The workflow uploads the MP4 and scene plan as an artifact.

Ordinary CI never calls the paid provider. Provider tests use mocked HTTP responses.

## Product fidelity and review

Runway's own guidance recommends multiple product angles, high-resolution isolated images, and clear product references. One or two catalog images do not establish a verified 360-degree view. The generated output must be reviewed for:

- silhouette and proportions
- color and finish
- hardware, panel, drawer and door count
- visible legs and construction
- camera views not supported by input images
- unwanted accessories, props, text or logos
- plausible placement and scale in the room

Reject the output if the product changes materially. AI-generated room context is illustrative and must not imply unsupported product features.

## Known limitations

- The first integration produces one 4–15 second AI-generated clip, not a finished 30-second campaign.
- The generated video may hallucinate product geometry despite reference images.
- The adapter does not currently generate a separate storyboard/keyframe contact sheet.
- Audio is disabled. The next audio phase will add an English TTS adapter, timed subtitles and licensed background-music mixing.
- A generated scene ad is not factory-shot footage.
- The provider is paid; use manual runs and short durations to control cost.
- External processing must be authorized. The CLI requires an explicit acknowledgement flag; that flag does not itself establish legal rights.

## Engineering boundary

Keep the provider behind an adapter so Runway can be replaced or supplemented later. Do not call the provider from ordinary CI or the default `fma-render` command. The default renderer remains deterministic and offline-capable.
