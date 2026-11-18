from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from ..catalog import LocalProductCatalog
from .runway import RunwayProductAdClient, RunwayProviderError
from .scenes import (
    build_product_info,
    build_scene_concept,
    resolve_scene_preset,
    scene_preset_manifest,
    select_product_reference_images,
)


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")[:80] or "item"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a short AI scene-based furniture product ad with Runway."
    )
    parser.add_argument("--sku", required=True)
    parser.add_argument("--data-dir", default="data/public/abo")
    parser.add_argument("--output-dir", default="data/ai-renders")
    parser.add_argument("--duration", type=int, default=10, choices=range(4, 16))
    parser.add_argument(
        "--scene-preset",
        default="auto",
        choices=["auto", "bedroom", "living_room", "dining_room", "home_office", "entryway", "studio"],
    )
    parser.add_argument("--style-image", action="append", default=[])
    parser.add_argument("--ratio", default="720:1280", choices=["720:1280", "1080:1920"])
    parser.add_argument(
        "--confirm-external-processing-rights",
        action="store_true",
        help="Acknowledge that you reviewed the rights and are authorized to send these images to a third-party AI provider.",
    )
    args = parser.parse_args(argv)

    if not args.confirm_external_processing_rights:
        parser.error(
            "External AI processing is disabled by default. Review the dataset/image license and third-party rights, "
            "then pass --confirm-external-processing-rights only if you are authorized."
        )
    if not os.getenv("RUNWAYML_API_SECRET"):
        parser.error("Set RUNWAYML_API_SECRET before calling the paid Runway API.")

    catalog = LocalProductCatalog(args.data_dir)
    product = catalog.get_product(args.sku)
    if product is None:
        parser.error(f"SKU {args.sku!r} was not found in {args.data_dir!r}.")
    images = select_product_reference_images(product)
    if not images:
        parser.error("The selected SKU has no usable HTTPS main/other product images.")

    preset = resolve_scene_preset(product.category, args.scene_preset)
    product_info = build_product_info(product)
    concept = build_scene_concept(product, preset, args.duration)
    output_dir = Path(args.output_dir) / _slug(product.sku)
    video_path = output_dir / "product-ad.mp4"

    try:
        result = RunwayProductAdClient().generate_product_ad(
            product_images=images,
            product_info=product_info,
            user_concept=concept,
            output_path=video_path,
            duration_seconds=args.duration,
            ratio=args.ratio,
            style_images=args.style_image,
            audio=False,
        )
    except RunwayProviderError as exc:
        parser.error(str(exc))

    catalog_manifest = catalog.load_manifest()
    license_info = catalog_manifest.get("license", {})
    manifest = {
        "sku": product.sku,
        "product_name": product.name,
        "category": product.category,
        "scene_preset": scene_preset_manifest(preset),
        "provider_result": result,
        "product_reference_images": images,
        "reference_image_count": len(images),
        "multi_view_coverage": (
            "limited_less_than_three_reference_images"
            if len(images) < 3
            else "multiple_reference_images_supplied_view_angles_not_independently_verified"
        ),
        "product_info_sent_to_provider": product_info,
        "creative_direction_sent_to_provider": concept,
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
        "audio_policy": "provider_audio_disabled_voiceover_not_yet_generated",
        "limitations": [
            "A generated scene is not factory-shot footage.",
            "AI video may alter product geometry; human visual review is mandatory.",
            "Multiple reference images do not prove complete 360-degree coverage.",
            "This command generates one 4-15 second clip, not the final 30-second campaign.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "scene-plan.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"video": str(video_path.resolve()), "scene_plan": str(manifest_path.resolve()), "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
