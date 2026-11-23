# Seedance 2.5 Furniture Scene Video Adapter

## Purpose

Add Seedance 2.5 as a second interchangeable video-generation provider for the furniture marketing demo. The first comparison keeps Runway Product Ad and Seedance 2.5 separate, while using the same SKU, source images, product information, scene preset, and creative direction.

## Official API

The adapter calls BytePlus ModelArk directly:

- Create task: `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`
- Retrieve task: `GET https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/{id}`
- Authentication: `Authorization: Bearer $BYTEPLUS_MODELARK_API_KEY`
- Default model: `dreamina-seedance-2-5-260628`
- Flash model: `dreamina-seedance-2-5-flash-261115`

Official documentation:

- [Create a video generation task](https://docs.byteplus.com/en/docs/modelark/create-video-generation-task-api)
- [Retrieve a video generation task](https://docs.byteplus.com/en/docs/modelark/get-video-generation-task-api)
- [Seedance 2.5 capabilities](https://docs.byteplus.com/en/docs/ModelArk/seedance-2-5)

## Supported configuration

| Capability | Seedance 2.5 | Seedance 2.5 Flash |
|---|---:|---:|
| Reference images | 1–30 | 1–10 |
| Duration | 4–30 seconds | 4–30 seconds |
| Resolution | 480p / 720p / 1080p / 4K | 480p / 720p |
| Aspect ratio | Includes 9:16 | Includes 9:16 |
| Native generated audio | Optional | Optional |

For the first Runway-vs-Seedance visual comparison, use `generate_audio=false`, 720p, 9:16, and the same duration. English voiceover, subtitles and licensed background music will be added in a separate post-production step. This avoids judging different models with different audio mixes.

## Configure and run

1. Import the public ABO catalog.
2. Verify dataset/image rights and confirm that the rights permit third-party AI processing.
3. Add the repository Actions secret `BYTEPLUS_MODELARK_API_KEY` or set it locally.
4. Activate Seedance 2.5 in the BytePlus ModelArk account. Model activation may require a qualifying balance or resource plan; check the console before running paid jobs.
5. Run:

~~~bash
export BYTEPLUS_MODELARK_API_KEY="..."
fma-seedance-ad \
  --sku YOUR_SKU \
  --data-dir data/public/abo \
  --output-dir data/ai-renders \
  --duration 10 \
  --scene-preset auto \
  --model dreamina-seedance-2-5-260628 \
  --resolution 720p \
  --ratio 9:16 \
  --confirm-external-processing-rights
~~~

Outputs:

- `data/ai-renders/{sku}/seedance/product-ad.mp4`
- `data/ai-renders/{sku}/seedance/seedance-plan.json`

The manifest records the exact prompt, reference image URIs, model ID, task ID, generated-video checksum, catalog provenance and a human-review checklist.

## Manual GitHub Actions

The `Seedance 2.5 Product Ad Demo` workflow is manual-only. It checks that the API secret exists and that the operator explicitly acknowledges external image processing rights. The workflow uploads the MP4 and manifest as an artifact. Ordinary CI does not call the paid API.

The generated video URL expires after 24 hours. The adapter downloads the MP4 as soon as the task succeeds.

## Product fidelity review

A model benchmark must score product fidelity before aesthetics. Review:

- silhouette and proportions
- color and finish
- hardware, panel, drawer and door count
- legs, feet and visible construction
- unsupported camera views and invented hidden surfaces
- scene scale, perspective, contact shadows and room fit
- unwanted accessories, props, text, logos and watermarks

Reject outputs that materially alter the product. Multiple reference images do not prove complete 360-degree coverage.

## Cost and safety boundaries

- This is a paid provider integration. A local CLI run or manual workflow dispatch may incur charges.
- Do not call the provider in unit tests or ordinary CI.
- Use only product images whose licenses and third-party processing rights have been verified.
- The acknowledgement flag is an operator attestation, not proof of legal permission.
- The API key is read from environment variables and must never be committed.
- The provider's temporary video URL is not a permanent archive; save the downloaded MP4 promptly.
- AI-generated scenes are illustrative and must not be described as factory-shot footage.
