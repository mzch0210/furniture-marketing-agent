# Seedance 2.5 Furniture Scene Video Adapter — Volcano Ark

## Provider and official API

This project uses the **official Volcano Ark (火山方舟)** API in the China Beijing region, not BytePlus ModelArk:

- Base URL: `https://ark.cn-beijing.volces.com/api/v3`
- Create task: `POST /contents/generations/tasks`
- Retrieve task: `GET /contents/generations/tasks/{id}`
- Authentication: `Authorization: Bearer $ARK_API_KEY`
- Standard model: `doubao-seedance-2-5-260628`
- Flash model: `doubao-seedance-2-5-flash-261115`

Official documentation:

- [Seedance 2.5 overview and task guidance](https://www.volcengine.com/docs/82379/ or https://docs.volcengine.com/docs/ark/seedance-2-5?lang=zh)
- [Create video generation task API](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)
- [Retrieve video generation task API](https://docs.volcengine.com/docs/ark/get-video-generation-task-api?lang=zh)
- [Model pricing](https://docs.volcengine.com/docs/ark/model-pricing?lang=zh)
- [Model activation, usage and resource-pack rules](https://docs.volcengine.com/docs/ark/seedance-model-activation-usage-and-refund?lang=zh)

## Models and supported inputs

| Capability | Seedance 2.5 | Seedance 2.5 Flash |
|---|---:|---:|
| Reference images | 1–30 | 1–10 |
| Duration | 4–30 seconds | 4–30 seconds |
| Resolution | 480p / 720p / 1080p / 4K | 480p / 720p |
| Aspect ratio | Includes 9:16 | Includes 9:16 |
| Native synchronized audio | Optional | Optional |

For this furniture image-to-video workflow, every catalog image is sent as a `reference_image`, and the request explicitly sets `omni_reference_task_type=reference`. This tells Ark that the task is to generate a new video based on reference images, not to edit or extend an input video.

## Verified cost and budget guard

Official pricing is token-based. For requests **without reference-video input**, the published online inference rates are:

| Model | 480p / 720p | 1080p | 4K |
|---|---:|---:|---:|
| Seedance 2.5 | ¥70 / million tokens | ¥77 / million tokens | ¥31 / million tokens |
| Seedance 2.5 Flash | ¥46 / million tokens | Not supported | Not supported |

The official estimate is:

`estimated tokens = output seconds × output width × output height × 24 FPS ÷ 1024`

For a 10-second, 720p, 9:16 output (720 × 1280, 24 FPS), using images but no input video:

| Model | Estimated tokens | Estimated cost |
|---|---:|---:|
| Seedance 2.5 | 216,000 | ¥15.12 |
| Seedance 2.5 Flash | 216,000 | ¥9.936 |

These are estimates, not fixed-price guarantees. The authoritative billable usage is returned as `usage.completion_tokens`; the adapter records that value and calculates the actual RMB cost using the official model/resolution rate. Failed moderation/provider tasks are not billed according to the official pricing page.

The CLI defaults to the full Seedance 2.5 model, 10 seconds, 720p, 9:16 and a ¥20 preflight budget cap. This keeps the expected generation cost within the user's approximate US$1–3 target. The cap is checked before the paid API call. To change the cap intentionally, pass `--max-estimated-cost-rmb`.

Do not use Draft mode in this MVP: Draft is a two-step workflow and both tasks are separately billed. This adapter does not submit reference video, so the published no-input-video rate applies.

## Account activation

The official activation documentation lists one of these requirements:

- Available account balance of at least ¥200; or
- A qualifying dedicated savings plan of at least ¥200 with remaining balance; or
- An eligible Seedance 2.5/2.0 resource pack of at least ¥200 with remaining quota.

This is an account/model activation threshold, not the cost of one 10-second video. Charges after activation are based on actual completion-token usage.

## Configure and run

1. Sign in to Volcano Engine and activate Seedance 2.5 or Seedance 2.5 Flash in ModelArk.
2. Create an Ark API key.
3. Set the key locally or add it as the GitHub Actions secret `ARK_API_KEY`.
4. Verify that the product-image license permits third-party AI processing.
5. Import the ABO public catalog and run:

~~~bash
export ARK_API_KEY="..."

# Recommended: full Seedance 2.5, 10 seconds, 720p, 9:16.
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

# Lower-cost alternative.
fma-seedance-ad \
  --sku YOUR_SKU \
  --data-dir data/public/abo \
  --output-dir data/ai-renders \
  --duration 10 \
  --model doubao-seedance-2-5-flash-261115 \
  --resolution 720p \
  --ratio 9:16 \
  --max-estimated-cost-rmb 20 \
  --scene-preset auto \
  --confirm-external-processing-rights
~~~

Outputs:

- `data/ai-renders/{sku}/seedance/product-ad.mp4`
- `data/ai-renders/{sku}/seedance/seedance-plan.json`

The manifest stores the exact model ID, prompt, source image references, task ID, output checksum, estimated token/cost, actual `usage.completion_tokens`, actual RMB cost, catalog provenance and a human-review checklist.

## Manual GitHub Actions

The `Seedance 2.5 Product Ad Demo` workflow is manual-only. It reads the repository Actions secret `ARK_API_KEY`, requires an explicit external-image-processing acknowledgement, and uploads the MP4 and manifest as an artifact. Ordinary CI uses mocked provider responses and never calls the paid API.

The generated video URL expires after 24 hours and has a download limit. The CLI downloads the MP4 immediately after task success.

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

- This is a paid official API integration. A local CLI run or manual workflow dispatch may incur charges.
- Do not call the provider in unit tests or ordinary CI.
- Use only product images whose licenses and third-party processing rights have been verified.
- The acknowledgement flag is an operator attestation, not proof of legal permission.
- The API key is read from environment variables and must never be committed.
- The provider's temporary video URL is not a permanent archive; save the downloaded MP4 promptly.
- AI-generated scenes are illustrative and must not be described as factory-shot footage.
