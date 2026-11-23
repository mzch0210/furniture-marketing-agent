from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from ..catalog import LocalProductCatalog
from .scenes import (
    build_product_info,
    build_scene_concept,
    resolve_scene_preset,
    scene_preset_manifest,
    select_product_reference_images,
)
from .seedance import SeedanceProviderError, SeedanceVideoClient


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")[:80] or "item"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a furniture scene video with the official Volcano Ark Seedance 2.5 API."
    )
    parser.add_argument("--sku", required=True)
    parser.add_argument("--data-dir", default="data/public/abo")
    parser.add_argument("--output-dir", default="data/ai-renders")
    parser.add_argument("--duration", type=int, default=10, choices=range(4, 31))
    parser.add_argument(
        "--scene-preset",
        default="auto",
        choices=["auto", "bedroom", "living_room", "dining_room", "home_office", "entryway", "studio"],
    )
    parser.add_argument(
        "--model",
        default=os.getenv("SEEDANCE_MODEL_ID", SeedanceVideoClient.DEFAULT_MODEL),
        choices=[SeedanceVideoClient.DEFAULT_MODEL, SeedanceVideoClient.FLASH_MODEL],
    )
    parser.add_argument("--resolution", default="720p", choices=["480p", "720p", "1080p", "4k"])
    parser.add_argument("--ratio", default="9:16", choices=["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"])
    parser.add_argument(
        "--max-estimated-cost-rmb",
        type=float,
        default=20.0,
        help="Abort before the paid API call if the official-formula estimate exceeds this RMB cap (default: 20).",
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--generate-audio",
        action="store_true",
        help="Request native synchronized audio. Disabled by default for visual comparison and separate voiceover editing.",
    )
    parser.add_argument(
        "--no-watermark",
        action="store_true",
        help="Request an unwatermarked output only if the account/model entitlement permits it.",
    )
    parser.add_argument(
        "--confirm-external-processing-rights",
        action="store_true",
        help="Acknowledge that source-image rights and third-party AI processing permissions were reviewed.",
    )
    args = parser.parse_args(argv)

    if not args.confirm_external_processing_rights:
        parser.error(
            "External AI processing is disabled by default. Review the dataset/image rights and provider terms, "
            "then pass --confirm-external-processing-rights only if authorized."
        )
    if not (os.getenv("ARK_API_KEY") or os.getenv("VOLCENGINE_ARK_API_KEY")):
        parser.error("Set ARK_API_KEY before calling the paid Volcano Ark Seedance API.")
    if args.max_estimated_cost_rmb <= 0:
        parser.error("--max-estimated-cost-rmb must be greater than zero.")

    try:
        estimate = SeedanceVideoClient.estimate_cost(
            args.model, args.duration, ratio=args.ratio, resolution=args.resolution
        )
    except SeedanceProviderError as exc:
        parser.error(str(exc))
    if estimate["estimated_cost_rmb"] > args.max_estimated_cost_rmb:
        parser.error(
            f"Estimated cost is ¥{estimate['estimated_cost_rmb']:.2f}, above the "
            f"¥{args.max_estimated_cost_rmb:.2f} preflight cap. Reduce duration/resolution, "
            "choose Seedance 2.5 Flash, or explicitly raise --max-estimated-cost-rmb."
        )

    print(
        json.dumps(
            {"preflight_cost_estimate": estimate, "max_estimated_cost_rmb": args.max_estimated_cost_rmb},
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )

    catalog = LocalProductCatalog(args.data_dir)
    product = catalog.get_product(args.sku)
    if product is None:
        parser.error(f"SKU {args.sku!r} was not found in {args.data_dir!r}.")
    images = select_product_reference_images(
        product, limit=30 if args.model == SeedanceVideoClient.DEFAULT_MODEL else 10
    )
    if not images:
        parser.error("The selected SKU has no usable HTTPS main/other product images.")

    preset = resolve_scene_preset(product.category, args.scene_preset)
    product_info = build_product_info(product)
    concept = build_scene_concept(product, preset, args.duration)
    prompt = (
        product_info
        + "\n\n"
        + concept
        + "\n\n"
        + "Treat all supplied reference images as different views of the same single furniture item, "
        + "not as separate products. Use them only to preserve the identity and visible construction of "
        + "that item. Do not invent specifications, materials, functions, accessories, or hidden details."
    )

    output_dir = Path(args.output_dir) / _slug(product.sku) / "seedance"
    video_path = output_dir / "product-ad.mp4"
    try:
        client = SeedanceVideoClient(model_id=args.model)
        result = client.generate_video(
            product_images=images,
            prompt=prompt,
            output_path=video_path,
            duration_seconds=args.duration,
            ratio=args.ratio,
            resolution=args.resolution,
            generate_audio=args.generate_audio,
            watermark=not args.no_watermark,
            seed=args.seed,
        )
    except SeedanceProviderError as exc:
        parser.error(str(exc))

    catalog_manifest = catalog.load_manifest()
    license_info = catalog_manifest.get("license", {})
    manifest = {
        "sku": product.sku,
        "product_name": product.name,
        "category": product.category,
        "scene_preset": scene_preset_manifest(preset),
        "provider_result": result,
        "billing": result.get("billing", {}),
        "product_reference_images": images,
        "reference_image_count": len(images),
        "multi_view_coverage": (
            "limited_less_than_three_reference_images"
            if len(images) < 3
            else "multiple_reference_images_supplied_view_angles_not_independently_verified"
        ),
        "product_info_sent_to_provider": product_info,
        "creative_direction_sent_to_provider": concept,
        "prompt_sent_to_provider": prompt,
        "source_dataset": product.source_dataset,
        "source_record_id": product.source_record_id,
        "source_uri": product.source_uri,
        "license_id": license_info.get("license_id", "unknown"),
        "license_url": license_info.get("license_url", ""),
        "attribution": catalog_manifest.get("attribution", ""),
        "human_review_required": True,
        "review_checklist": [
            "Compare the generated product silhouette against every supplied reference image.",
            "Check color, finish, proportions, hardware, drawer/door count and visible construction.",
            "Reject invented or altered product components and unsupported camera views.",
            "Confirm the generated room does not imply unsupported product functions or included accessories.",
            "Confirm source-image rights and provider processing permissions before publication.",
        ],
        "audio_policy": (
            "seedance_native_audio_requested_human_review_required"
            if args.generate_audio
            else "provider_audio_disabled_external_voiceover_and_music_not_yet_composited"
        ),
        "limitations": [
            "A generated scene is not factory-shot footage.",
            "AI video may alter product geometry; human visual review is mandatory.",
            "Multiple reference images do not prove complete 360-degree coverage.",
            "This command generates one 4-30 second clip, not the final edited campaign.",
            "The provider's video URL is temporary; the CLI downloads the MP4 immediately.",
            "Estimated cost is a preflight estimate; the actual bill is calculated from usage.completion_tokens.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "seedance-plan.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"video": str(video_path.resolve()), "scene_plan": str(manifest_path.resolve()), "result": result},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
