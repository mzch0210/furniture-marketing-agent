from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .catalog import CatalogDataError, LocalProductCatalog
from .models import (
    CampaignCreativeRequest,
    CampaignObjective,
    CreativeAngle,
    CreativeBrief,
    CreativeExportArtifact,
    CreativeGenerationResult,
    CreativePackage,
    CreativeScript,
    CreativeScriptSegment,
    FactVerificationStatus,
    ProductClaimReference,
    StoryboardShot,
)

TEMPLATE_VERSION = "fma-creative-en-us-v1.0.0"

ANGLE_FACT_KEYS: dict[CreativeAngle, tuple[str, ...]] = {
    CreativeAngle.PRODUCT_OVERVIEW: ("product_type",),
    CreativeAngle.COLOR_SPOTLIGHT: ("color",),
    CreativeAngle.MATERIAL_SPOTLIGHT: ("material", "fabric_type", "finish_type"),
    CreativeAngle.DIMENSION_SPOTLIGHT: (
        "dimension_width",
        "dimension_height",
        "dimension_length",
        "dimension_depth",
    ),
    CreativeAngle.BRAND_SPOTLIGHT: ("brand",),
    CreativeAngle.STYLE_SPOTLIGHT: ("style", "pattern"),
}

ANGLE_LABELS = {
    CreativeAngle.PRODUCT_OVERVIEW: "product type",
    CreativeAngle.COLOR_SPOTLIGHT: "color",
    CreativeAngle.MATERIAL_SPOTLIGHT: "material",
    CreativeAngle.DIMENSION_SPOTLIGHT: "dimensions",
    CreativeAngle.BRAND_SPOTLIGHT: "brand",
    CreativeAngle.STYLE_SPOTLIGHT: "style",
}


class ProductNotFoundError(LookupError):
    """Raised when a requested SKU is absent from the local catalog."""


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    return slug[:80] or "item"


def _campaign_id(request: CampaignCreativeRequest) -> str:
    if request.campaign_id and request.campaign_id.strip():
        return _safe_slug(request.campaign_id.strip())
    identity = "|".join(
        [
            request.sku,
            request.audience.value,
            request.objective.value,
            request.angle.value,
            request.target_market,
            str(request.duration_seconds),
        ]
    )
    return "cmp-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]


def _accepted_fact(fact: Any) -> bool:
    return fact.verification_status in {
        FactVerificationStatus.SOURCE_REPORTED,
        FactVerificationStatus.FACTORY_VERIFIED,
    }


def _fact_map(product: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for fact in product.facts:
        if _accepted_fact(fact) and fact.key not in result:
            result[fact.key] = fact
    return result


def _format_fact_value(fact: Any) -> str:
    value = fact.value
    if isinstance(value, dict):
        raw_value = value.get("value")
        unit = value.get("unit") or fact.unit
        if raw_value is not None:
            return f"{raw_value} {unit}".strip() if unit else str(raw_value)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _claim_reference(fact: Any) -> ProductClaimReference:
    return ProductClaimReference(
        fact_key=fact.key,
        value=fact.value,
        source_dataset=fact.source_dataset,
        source_record_id=fact.source_record_id,
        source_uri=fact.source_uri,
        source_field=fact.source_field,
        verification_status=fact.verification_status,
    )


def _unique_refs(refs: list[ProductClaimReference]) -> list[ProductClaimReference]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ProductClaimReference] = []
    for ref in refs:
        key = (ref.fact_key, ref.source_record_id, ref.source_field)
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


def _cta(request: CampaignCreativeRequest) -> str:
    if request.objective == CampaignObjective.BRAND_AWARENESS:
        return "Follow for more furniture product spotlights."
    if request.objective == CampaignObjective.PRODUCT_CONSIDERATION:
        if request.audience.value == "B2B":
            return "Save this listing and request factory-confirmed specifications before shortlisting."
        return "Save this product and confirm the specifications with the seller before purchase."
    if request.objective == CampaignObjective.LEAD_GENERATION:
        if request.audience.value == "B2B":
            return "Contact the supplier to request factory-confirmed specifications, MOQ, lead time and a quotation."
        return "Send a message to ask the seller about availability and factory-confirmed product details."
    return "Ask the seller for the official product page and current product details."


def _segment_durations(total_seconds: int) -> list[int]:
    hook = min(6, max(3, round(total_seconds * 0.15)))
    remaining = total_seconds - hook
    second = max(1, round(remaining * 0.25))
    third = max(1, round(remaining * 0.30))
    fourth = max(1, round(remaining * 0.20))
    fifth = remaining - second - third - fourth
    if fifth < 1:
        fifth = 1
        fourth = remaining - second - third - fifth
    return [hook, second, third, fourth, fifth]


def build_creative_package(
    product: Any,
    request: CampaignCreativeRequest,
    manifest: dict[str, Any],
) -> CreativePackage:
    facts = _fact_map(product)
    name_fact = facts.get("product_name")
    name_ref = _claim_reference(name_fact) if name_fact else None
    product_name = str(name_fact.value) if name_fact else product.name

    selected_facts = [
        facts[key]
        for key in ANGLE_FACT_KEYS[request.angle]
        if key in facts
    ]
    selected_refs = [_claim_reference(fact) for fact in selected_facts]
    angle_label = ANGLE_LABELS[request.angle]

    if request.angle == CreativeAngle.PRODUCT_OVERVIEW:
        hook = (
            f"A closer look at {product_name}."
            if name_ref
            else "A closer look at this furniture listing."
        )
        hook_refs = [name_ref] if name_ref else []
    elif selected_facts:
        hook = f"What does the public listing say about its {angle_label}?"
        hook_refs = []
    else:
        hook = "Before you shortlist it, check what the public listing actually tells you."
        hook_refs = []

    if request.audience.value == "B2B":
        introduction = (
            f"For your next furniture sourcing review, take a look at {product_name}."
            if name_ref
            else "For your next furniture sourcing review, start with the catalog record."
        )
        intro_refs = [name_ref] if name_ref else []
    else:
        introduction = (
            f"Here is a closer look at {product_name}."
            if name_ref
            else "Here is a closer look at this furniture catalog listing."
        )
        intro_refs = [name_ref] if name_ref else []

    if selected_facts:
        feature_parts: list[str] = []
        for fact in selected_facts[:3]:
            label = fact.key.replace("_", " ")
            feature_parts.append(f"{label}: {_format_fact_value(fact)}")
        if len(feature_parts) == 1:
            feature_voiceover = f"The public listing reports {feature_parts[0]}."
            feature_text = f"Catalog-listed {feature_parts[0]}"
        else:
            feature_voiceover = "The public listing reports " + "; ".join(feature_parts) + "."
            feature_text = "Catalog-listed: " + " · ".join(feature_parts)
        feature_refs = selected_refs[:3]
    else:
        feature_voiceover = (
            f"No source-reported {angle_label} detail is available in this catalog record. "
            "Do not fill the gap with a visual guess."
        )
        feature_text = f"{angle_label.title()} details: not supplied in this catalog record"
        feature_refs = []

    verification_note = (
        "Public catalog information is source-reported, not automatically factory-confirmed. "
        "Confirm specifications and commercial terms with the supplier before publication."
    )
    cta = _cta(request)

    duration_list = _segment_durations(request.duration_seconds)
    roles = ["hook", "introduction", "product_detail", "verification", "close"]
    voiceovers = [hook, introduction, feature_voiceover, verification_note, cta]
    screen_texts = [
        "Furniture product spotlight",
        product_name if name_ref else "Public catalog product",
        feature_text,
        "Source-reported ≠ factory-confirmed",
        cta,
    ]
    segment_refs = [
        _unique_refs(hook_refs),
        _unique_refs(intro_refs),
        _unique_refs(feature_refs),
        [],
        [],
    ]

    segments: list[CreativeScriptSegment] = []
    cursor = 0
    for index, (role, length, voiceover, on_screen, refs) in enumerate(
        zip(roles, duration_list, voiceovers, screen_texts, segment_refs),
        start=1,
    ):
        end = cursor + length
        segments.append(
            CreativeScriptSegment(
                segment_id=f"seg-{index:02d}",
                role=role,
                start_seconds=cursor,
                end_seconds=end,
                voiceover=voiceover,
                on_screen_text=on_screen,
                fact_refs=refs,
            )
        )
        cursor = end

    assets = list(product.assets)
    main_assets = [asset.asset_id for asset in assets if asset.role == "main_image"]
    other_assets = [asset.asset_id for asset in assets if asset.role == "other_image"]
    spin_assets = [asset.asset_id for asset in assets if asset.role == "turntable_360"]
    image_candidates = main_assets + other_assets
    all_candidate_assets = image_candidates + spin_assets

    shot_purposes = [
        "Hook: establish the product subject immediately",
        "Introduction: show the catalog item clearly",
        "Detail: support only the selected source-backed attribute",
        "Trust: make the source-reported status visible",
        "Close: show a clear next step",
    ]
    visual_directions = [
        "Open on an available catalog image or 360-degree asset. Use a fast, clean reveal; do not create a lifestyle scene that implies unprovided use conditions.",
        "Show the product using an available catalog image. Keep the complete item visible and avoid adding accessories or components not present in the source asset.",
        "Use a source image crop or available 360-degree view only as a visual reference. On-screen product details must match the referenced source facts exactly.",
        "Use a simple text card explaining that public listing details are source-reported and require supplier confirmation.",
        "Use a clean closing card with the requested CTA. Do not add an unverified URL, price, discount or commercial promise.",
    ]
    shot_assets = [
        image_candidates[:1],
        image_candidates[1:2] or image_candidates[:1],
        (spin_assets[:1] or image_candidates[:2]),
        [],
        [],
    ]
    storyboard: list[StoryboardShot] = []
    for index, (segment, purpose, visual, candidate_ids) in enumerate(
        zip(segments, shot_purposes, visual_directions, shot_assets),
        start=1,
    ):
        if index == 3:
            refs = segment.fact_refs
        elif index in (1, 2):
            refs = segment.fact_refs
        else:
            refs = []
        storyboard.append(
            StoryboardShot(
                shot_number=index,
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                purpose=purpose,
                visual_direction=visual,
                candidate_asset_ids=candidate_ids,
                asset_match_status="candidate_only" if candidate_ids else "not_required_or_unavailable",
                source_fact_refs=refs,
                on_screen_text=segment.on_screen_text,
                voiceover=segment.voiceover,
                transition="clean cut; keep text inside TikTok safe zones",
                production_note=(
                    "These are source asset candidates only; actual shot matching and EDL creation belong to the production stage."
                    if candidate_ids
                    else "No product media is assigned to this card. Do not fabricate footage."
                ),
            )
        )

    caption_text = (
        f"A closer look at {product_name}. "
        "Public catalog details are source-reported; confirm specifications with the supplier before purchase or sourcing."
        if name_ref
        else "A closer look at a public furniture catalog listing. "
        "Confirm specifications with the supplier before purchase or sourcing."
    )
    hashtags = (
        ["#FurnitureSourcing", "#WholesaleFurniture", "#FurnitureSupplier", "#ProductSpotlight"]
        if request.audience.value == "B2B"
        else ["#FurnitureDesign", "#HomeInspiration", "#FurnitureFinds", "#ProductSpotlight"]
    )
    caption_refs = [name_ref] if name_ref else []
    claim_index = _unique_refs(
        [ref for segment in segments for ref in segment.fact_refs]
        + caption_refs
        + [ref for shot in storyboard for ref in shot.source_fact_refs]
    )

    caveats = [
        "All product-specific statements in this creative are linked to source facts in the ABO catalog record.",
        "source_reported means present in the public listing; it does not mean factory-verified.",
        "Unknown product attributes are omitted. No material, dimensions, functions, load capacity, certifications, accessories, MOQ, lead time, warranty, price or stock status are inferred.",
        "The selected public image/360 assets are candidate references, not confirmed shot matches. Do not present image animation as live-action footage.",
        "The default template assumes a generic US-English audience and does not claim live market or trend research.",
    ]
    if not selected_facts and request.angle != CreativeAngle.PRODUCT_OVERVIEW:
        caveats.append(
            f"No eligible source-backed {angle_label} fact was found. The requested angle is handled with an explicit data-gap note rather than an invented claim."
        )
    if any(
        fact.verification_status == FactVerificationStatus.SOURCE_REPORTED
        for fact in selected_facts
    ):
        caveats.append(
            "At least one featured fact is source-reported only and requires human/factory confirmation before it is used as a verified sales claim."
        )

    dataset = manifest.get("dataset", {})
    license_info = manifest.get("license", {})
    attribution = manifest.get("attribution") or license_info.get("attribution", "")

    brief = CreativeBrief(
        campaign_id=_campaign_id(request),
        sku=product.sku,
        product_name=product_name,
        audience=request.audience,
        objective=request.objective,
        angle=request.angle,
        target_market=request.target_market,
        platform=request.platform,
        language=request.language,
        duration_seconds=request.duration_seconds,
        message_strategy=(
            "Hook → source-backed product introduction/detail → provenance reminder → audience-specific CTA. "
            "No unsupported product features or commercial terms are added."
        ),
        primary_cta=cta,
        research_note=(
            "Deterministic template output only. No live market research, audience analytics or trend validation was performed."
        ),
        approval_required=True,
    )
    script = CreativeScript(
        hook=hook,
        segments=segments,
        full_voiceover="\n".join(segment.voiceover for segment in segments),
        on_screen_copy=[segment.on_screen_text for segment in segments],
    )
    return CreativePackage(
        template_version=TEMPLATE_VERSION,
        generation_mode="deterministic_template",
        publication_status="requires_human_review",
        brief=brief,
        script=script,
        storyboard=storyboard,
        caption=caption_text,
        hashtags=hashtags,
        claim_reference_index=claim_index,
        caveats=caveats,
        source_dataset=product.source_dataset,
        source_record_id=product.source_record_id,
        source_uri=product.source_uri,
        dataset_name=dataset.get("name", product.source_dataset),
        attribution=attribution,
        license_id=license_info.get("license_id", "unknown"),
        license_url=license_info.get("license_url", ""),
        candidate_asset_ids=all_candidate_assets,
    )


def validate_claim_provenance(package: CreativePackage, product: Any) -> None:
    facts = {
        (fact.key, fact.source_record_id, fact.source_field): fact
        for fact in product.facts
        if _accepted_fact(fact)
    }
    references = list(package.claim_reference_index)
    references.extend(ref for segment in package.script.segments for ref in segment.fact_refs)
    references.extend(ref for shot in package.storyboard for ref in shot.source_fact_refs)
    references.extend(package.caption_fact_refs)
    for ref in references:
        key = (ref.fact_key, ref.source_record_id, ref.source_field)
        fact = facts.get(key)
        if fact is None:
            raise ValueError(f"Creative contains a claim without an eligible source fact: {key}")
        if (
            fact.source_uri != ref.source_uri
            or fact.source_dataset != ref.source_dataset
            or fact.value != ref.value
            or fact.verification_status != ref.verification_status
        ):
            raise ValueError(f"Creative claim provenance does not match the product fact: {key}")


def _srt_timestamp(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remainder = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remainder:02d},000"


def _render_script_markdown(package: CreativePackage) -> str:
    lines = [
        "# English Marketing Script",
        "",
        f"- SKU: {package.brief.sku}",
        f"- Audience: {package.brief.audience.value}",
        f"- Objective: {package.brief.objective.value}",
        f"- Angle: {package.brief.angle.value}",
        f"- Duration: {package.brief.duration_seconds} seconds",
        f"- Template: {package.template_version}",
        "",
        "## Hook",
        "",
        package.script.hook,
        "",
        "## Timed voiceover and on-screen copy",
        "",
    ]
    for segment in package.script.segments:
        lines.extend(
            [
                f"### {segment.start_seconds:02d}s–{segment.end_seconds:02d}s · {segment.role}",
                "",
                f"**Voiceover:** {segment.voiceover}",
                "",
                f"**On-screen:** {segment.on_screen_text}",
                "",
                "**Fact references:** "
                + (
                    ", ".join(ref.fact_key for ref in segment.fact_refs)
                    if segment.fact_refs
                    else "None (generic or provenance guidance)"
                ),
                "",
            ]
        )
    lines.extend(["## Publication caveats", ""])
    lines.extend(f"- {item}" for item in package.caveats)
    return "\n".join(lines) + "\n"


def _render_storyboard_markdown(package: CreativePackage) -> str:
    lines = [
        "# Timed Storyboard",
        "",
        f"- SKU: {package.brief.sku}",
        f"- Format: {package.brief.platform}, {package.brief.duration_seconds}s, 9:16",
        f"- Template version: {package.template_version}",
        "",
    ]
    for shot in package.storyboard:
        lines.extend(
            [
                f"## Shot {shot.shot_number:02d} · {shot.start_seconds:02d}s–{shot.end_seconds:02d}s",
                "",
                f"**Purpose:** {shot.purpose}",
                "",
                f"**Visual direction:** {shot.visual_direction}",
                "",
                f"**On-screen text:** {shot.on_screen_text}",
                "",
                f"**Voiceover:** {shot.voiceover}",
                "",
                f"**Candidate asset IDs:** {', '.join(shot.candidate_asset_ids) if shot.candidate_asset_ids else 'None'}",
                "",
                f"**Asset status:** {shot.asset_match_status}",
                "",
                f"**Fact references:** {', '.join(ref.fact_key for ref in shot.source_fact_refs) if shot.source_fact_refs else 'None'}",
                "",
                f"**Production note:** {shot.production_note}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def export_creative_package(
    package: CreativePackage,
    output_dir: str | Path = "data/outputs/creatives",
) -> list[CreativeExportArtifact]:
    target = (
        Path(output_dir)
        / _safe_slug(package.brief.campaign_id)
        / _safe_slug(package.brief.sku)
    )
    target.mkdir(parents=True, exist_ok=True)

    srt_blocks = []
    for index, segment in enumerate(package.script.segments, start=1):
        srt_blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_srt_timestamp(segment.start_seconds)} --> {_srt_timestamp(segment.end_seconds)}",
                    segment.voiceover,
                ]
            )
        )
    files: dict[str, str] = {
        "creative-package.json": json.dumps(
            package.model_dump(mode="json"), ensure_ascii=False, indent=2
        ) + "\n",
        "script.md": _render_script_markdown(package),
        "storyboard.md": _render_storyboard_markdown(package),
        "caption.txt": package.caption + "\n\n" + " ".join(package.hashtags) + "\n",
        "subtitles.srt": "\n\n".join(srt_blocks) + "\n",
        "attribution.txt": (
            f"Dataset: {package.dataset_name}\n"
            f"Dataset ID: {package.source_dataset}\n"
            f"Source record: {package.source_record_id}\n"
            f"Source record URL: {package.source_uri}\n"
            f"License: {package.license_id}\n"
            f"License URL: {package.license_url}\n"
            f"Attribution: {package.attribution}\n"
            "Product facts are source-reported unless explicitly marked factory_verified.\n"
        ),
    }
    exports: list[CreativeExportArtifact] = []
    for name, content in files.items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        exports.append(
            CreativeExportArtifact(
                name=name,
                path=str(path),
                size_bytes=path.stat().st_size,
            )
        )
    return exports


class CampaignCreativeService:
    def __init__(
        self,
        catalog: LocalProductCatalog,
        output_dir: str | Path = "data/outputs/creatives",
    ) -> None:
        self.catalog = catalog
        self.output_dir = Path(output_dir)

    def generate(self, request: CampaignCreativeRequest) -> CreativeGenerationResult:
        product = self.catalog.get_product(request.sku)
        if product is None:
            raise ProductNotFoundError(f"SKU not found in local catalog: {request.sku}")
        manifest = self.catalog.load_manifest()
        package = build_creative_package(product, request, manifest)
        validate_claim_provenance(package, product)
        exports = export_creative_package(package, self.output_dir)
        return CreativeGenerationResult(package=package, exports=exports)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic English furniture marketing creative from a local public catalog."
    )
    parser.add_argument("--sku", required=True, help="SKU from the local ABO catalog")
    parser.add_argument("--data-dir", default="data/public/abo")
    parser.add_argument("--output-dir", default="data/outputs/creatives")
    parser.add_argument("--audience", choices=["B2B", "B2C"], default="B2C")
    parser.add_argument(
        "--objective",
        choices=[item.value for item in CampaignObjective],
        default=CampaignObjective.PRODUCT_CONSIDERATION.value,
    )
    parser.add_argument(
        "--angle",
        choices=[item.value for item in CreativeAngle],
        default=CreativeAngle.PRODUCT_OVERVIEW.value,
    )
    parser.add_argument("--target-market", default="United States")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--campaign-id")
    args = parser.parse_args()

    request = CampaignCreativeRequest(
        sku=args.sku,
        audience=args.audience,
        objective=args.objective,
        angle=args.angle,
        target_market=args.target_market,
        duration_seconds=args.duration,
        campaign_id=args.campaign_id,
    )
    result = CampaignCreativeService(
        LocalProductCatalog(args.data_dir),
        output_dir=args.output_dir,
    ).generate(request)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
