from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import textwrap
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .catalog import CatalogDataError, LocalProductCatalog
from .marketing import CampaignCreativeService
from .models import (
    CampaignCreativeRequest,
    CatalogAssetReference,
    CatalogProduct,
    CreativeExportArtifact,
    EditDecisionList,
    EditDecisionShot,
    MatchedMediaAsset,
    VideoProductionResult,
    VideoRenderReport,
)

OFFICIAL_ABO_HOST = "amazon-berkeley-objects.s3.us-east-1.amazonaws.com"
MAX_IMAGE_BYTES = 30 * 1024 * 1024
RENDER_WIDTH = 1080
RENDER_HEIGHT = 1920
RENDER_FPS = 30


class ProductionError(RuntimeError):
    """Raised when media matching or video rendering cannot complete."""


def _safe_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    return slug[:80] or "item"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_official_url(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != OFFICIAL_ABO_HOST
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ProductionError(f"Refusing non-official ABO media URL: {url}")
    return parsed


def _candidate_urls(asset: CatalogAssetReference) -> list[tuple[str, str]]:
    if not asset.source_uri:
        return []
    parsed = _validated_official_url(asset.source_uri)
    candidates: list[tuple[str, str]] = []
    if parsed.path.startswith("/images/small/"):
        original_path = parsed.path.replace("/images/small/", "/images/original/", 1)
        candidates.append((urllib.parse.urlunsplit(parsed._replace(path=original_path)), "original"))
    candidates.append((asset.source_uri, "small" if "/images/small/" in parsed.path else "source"))
    seen: set[str] = set()
    return [(url, variant) for url, variant in candidates if not (url in seen or seen.add(url))]


def _read_image_response(url: str, timeout: int, max_bytes: int) -> tuple[bytes, str, str]:
    _validated_official_url(url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FurnitureMarketingAgent/0.1 (public demo media fetch)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            _validated_official_url(final_url)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            data = response.read(max_bytes + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProductionError(f"Unable to download media asset: {exc}") from exc
    if len(data) > max_bytes:
        raise ProductionError(f"Media asset exceeds the {max_bytes}-byte download limit.")
    if data.startswith(b"\xff\xd8\xff"):
        detected_type = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_type = "image/png"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        detected_type = "image/webp"
    else:
        raise ProductionError(f"Downloaded object is not a supported image (Content-Type: {content_type or 'unknown'}).")
    if content_type and not (content_type.startswith("image/") or content_type == "application/octet-stream"):
        raise ProductionError(f"Unexpected media Content-Type: {content_type}")
    return data, detected_type, final_url


def download_asset(
    asset: CatalogAssetReference,
    cache_dir: str | Path,
    license_id: str = "CC-BY-4.0",
    timeout: int = 45,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> MatchedMediaAsset:
    """Fetch one selected ABO still image; never download a dataset-wide archive."""
    candidates = _candidate_urls(asset)
    if not candidates:
        raise ProductionError(f"Asset {asset.asset_id} has no resolvable official image URL.")
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    asset_key = hashlib.sha256(asset.asset_id.encode("utf-8")).hexdigest()[:24]
    failures: list[str] = []
    for url, variant in candidates:
        try:
            data, media_type, final_url = _read_image_response(url, timeout, max_bytes)
            extension = mimetypes.guess_extension(media_type) or ".img"
            target = cache / f"{asset_key}-{variant}{extension}"
            temporary = target.with_suffix(target.suffix + ".part")
            temporary.write_bytes(data)
            temporary.replace(target)
            return MatchedMediaAsset(
                asset_id=asset.asset_id,
                role=asset.role,
                media_type=media_type,
                source_dataset=asset.source_dataset,
                source_record_id=asset.source_record_id,
                source_uri=asset.source_uri or url,
                downloaded_uri=final_url,
                local_path=str(target.resolve()),
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                source_variant=variant,
                license_id=license_id or asset.license_id,
                width=asset.width,
                height=asset.height,
            )
        except ProductionError as exc:
            failures.append(f"{variant}: {exc}")
    raise ProductionError("; ".join(failures))


def _asset_fallback_order(product: CatalogProduct, shot) -> list[str]:
    candidates = list(shot.candidate_asset_ids)
    image_assets = [
        asset.asset_id
        for asset in product.assets
        if asset.role in {"main_image", "other_image"}
    ]
    if shot.shot_number <= 3:
        candidates.extend(image_assets)
    seen: set[str] = set()
    return [item for item in candidates if not (item in seen or seen.add(item))]


def build_edit_decision_list(
    package,
    product: CatalogProduct,
    manifest: dict,
    asset_cache_dir: str | Path,
) -> EditDecisionList:
    """Resolve storyboard candidates to local assets or explicit missing-shot records."""
    asset_map = {asset.asset_id: asset for asset in product.assets}
    license_info = manifest.get("license", {})
    license_id = str(license_info.get("license_id") or "unknown")
    license_url = str(license_info.get("license_url") or "")
    attribution = str(manifest.get("attribution") or license_info.get("attribution") or "")
    registry_note = str(license_info.get("aws_registry_cached_rendered_page_observation") or "")
    rights_review_required = (
        "CC BY-NC" in registry_note
        or license_info.get("verification_status") != "verified_from_official_license_file"
    )
    warnings = [
        "Catalog still images are animated stills, not factory-shot live-action footage.",
        "Public catalog facts remain source-reported, not factory-confirmed.",
    ]
    if rights_review_required:
        warnings.append(
            "Public license metadata contains a conflicting or incomplete registry observation. "
            "Keep this output in the internal demo and resolve rights before external or commercial redistribution."
        )

    downloaded: dict[str, MatchedMediaAsset] = {}
    shots: list[EditDecisionShot] = []
    for shot in package.storyboard:
        matched = None
        failure_reason = None
        for asset_id in _asset_fallback_order(product, shot):
            asset = asset_map.get(asset_id)
            if asset is None or asset.role not in {"main_image", "other_image"}:
                continue
            if asset_id in downloaded:
                matched = downloaded[asset_id]
                break
            try:
                matched = download_asset(asset, asset_cache_dir, license_id=license_id)
                downloaded[asset_id] = matched
                break
            except ProductionError as exc:
                failure_reason = str(exc)

        if matched:
            shots.append(
                EditDecisionShot(
                    shot_number=shot.shot_number,
                    start_seconds=shot.start_seconds,
                    end_seconds=shot.end_seconds,
                    visual_type="catalog_still_image_animation",
                    match_status="matched",
                    asset_id=matched.asset_id,
                    local_asset_path=matched.local_path,
                    source_uri=matched.downloaded_uri,
                    source_fact_refs=shot.source_fact_refs,
                    on_screen_text=shot.on_screen_text,
                    voiceover=shot.voiceover,
                    transition="clean_cut",
                )
            )
            shot.asset_match_status = "matched"
            shot.production_note = "Matched to a downloaded official catalog still image; rendered with subtle pan/zoom."
        elif shot.shot_number >= 4:
            shots.append(
                EditDecisionShot(
                    shot_number=shot.shot_number,
                    start_seconds=shot.start_seconds,
                    end_seconds=shot.end_seconds,
                    visual_type="generated_title_card",
                    match_status="matched",
                    source_fact_refs=shot.source_fact_refs,
                    on_screen_text=shot.on_screen_text,
                    voiceover=shot.voiceover,
                    transition="clean_cut",
                )
            )
            shot.asset_match_status = "generated_card"
            shot.production_note = "Generated text card; no product footage is required for this storyboard beat."
        else:
            reason = failure_reason or "No downloadable source-backed product image was available for this shot."
            shots.append(
                EditDecisionShot(
                    shot_number=shot.shot_number,
                    start_seconds=shot.start_seconds,
                    end_seconds=shot.end_seconds,
                    visual_type="missing_footage_card",
                    match_status="missing",
                    source_fact_refs=shot.source_fact_refs,
                    on_screen_text=shot.on_screen_text,
                    voiceover=shot.voiceover,
                    transition="clean_cut",
                    reshoot_required=True,
                    reshoot_note=reason,
                )
            )
            shot.asset_match_status = "missing"
            shot.production_note = "No product image could be matched. A visible placeholder is rendered and a reshoot request is included."

    media_basis = "catalog_still_image_animation" if downloaded else "generated_cards_with_missing_product_shots"
    return EditDecisionList(
        campaign_id=package.brief.campaign_id,
        sku=product.sku,
        duration_seconds=package.brief.duration_seconds,
        width=RENDER_WIDTH,
        height=RENDER_HEIGHT,
        fps=RENDER_FPS,
        media_basis=media_basis,
        shots=shots,
        assets=list(downloaded.values()),
        source_dataset=product.source_dataset,
        source_record_id=product.source_record_id,
        attribution=attribution,
        license_id=license_id,
        license_url=license_url,
        rights_review_required=rights_review_required,
        warnings=warnings,
    )


def _find_binary(binary: str | None, name: str) -> str:
    candidate = binary or shutil.which(name)
    if not candidate:
        raise ProductionError(
            f"{name} was not found. Install FFmpeg (including ffprobe) and ensure it is on PATH. "
            "See https://ffmpeg.org/download.html."
        )
    resolved = shutil.which(candidate) or candidate
    if not Path(resolved).is_file() and shutil.which(resolved) is None:
        raise ProductionError(
            f"Configured {name} executable does not exist: {resolved}. "
            "Install FFmpeg (including ffprobe) and ensure it is on PATH. "
            "See https://ffmpeg.org/download.html."
        )
    return resolved


def _find_font() -> str:
    candidates = [
        os.environ.get("FMA_FONT_FILE", ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise ProductionError(
        "No supported TrueType font was found. Install DejaVu Sans or set FMA_FONT_FILE."
    )


def _escape_filter_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _safe_screen_text(value: str) -> str:
    """Normalize display copy to a conservative FFmpeg drawtext-safe ASCII subset."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("&", "and")
    ascii_text = re.sub(r"[^A-Za-z0-9 .,!?'-]", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def _wrapped_text(value: str, width: int = 30, max_lines: int = 3) -> str:
    safe = _safe_screen_text(value)
    lines: list[str] = []
    for paragraph in safe.splitlines() or [safe]:
        lines.extend(textwrap.wrap(paragraph, width=width) or [""])
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "..."
    return "\n".join(lines)


def _drawtext(text_file: str, font_file: str, y: str, fontsize: int = 54) -> str:
    return (
        "drawtext="
        f"fontfile='{_escape_filter_value(font_file)}':"
        f"textfile='{text_file}':"
        f"fontcolor=0x25231F:fontsize={fontsize}:line_spacing=10:"
        "box=1:boxcolor=0xFFFDF8@0.94:boxborderw=24:"
        f"x=(w-text_w)/2:y={y}"
    )


def _run(command: list[str], cwd: Path, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise ProductionError(f"FFmpeg command timed out after {timeout} seconds.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "No diagnostic output")[-4000:]
        raise ProductionError(f"Media command failed ({result.returncode}): {detail}")
    return result


def render_video(
    edl: EditDecisionList,
    output_path: str | Path,
    ffmpeg_bin: str | None = None,
    ffprobe_bin: str | None = None,
) -> VideoRenderReport:
    ffmpeg = _find_binary(ffmpeg_bin, "ffmpeg")
    ffprobe = _find_binary(ffprobe_bin, "ffprobe")
    font_file = _find_font()
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    filters = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        capture_output=True, text=True, timeout=30, check=False
    )
    if filters.returncode != 0 or "drawtext" not in (filters.stdout + filters.stderr):
        raise ProductionError("The installed FFmpeg build does not provide the drawtext filter.")

    with tempfile.TemporaryDirectory(prefix="fma-render-", dir=output.parent) as temporary:
        work = Path(temporary)
        clips: list[Path] = []
        for shot in edl.shots:
            duration = shot.end_seconds - shot.start_seconds
            if duration <= 0:
                raise ProductionError(f"Shot {shot.shot_number} has an invalid duration.")
            frames = duration * edl.fps
            text_file = f"shot-{shot.shot_number:02d}.txt"
            text = shot.on_screen_text
            if shot.match_status == "missing":
                text = "PRODUCT FOOTAGE NEEDED. " + (shot.reshoot_note or shot.on_screen_text)
            (work / text_file).write_text(_wrapped_text(text), encoding="utf-8")
            draw = _drawtext(text_file, font_file, y="h-330", fontsize=48)
            clip = work / f"clip-{shot.shot_number:02d}.mp4"

            if shot.visual_type == "catalog_still_image_animation":
                if not shot.local_asset_path or not Path(shot.local_asset_path).is_file():
                    raise ProductionError(f"Shot {shot.shot_number} references a missing local media file.")
                video_filter = (
                    "split=2[background][foreground];"
                    "[background]scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,gblur=sigma=32,eq=brightness=-0.08:saturation=0.72[bg];"
                    "[foreground]scale=900:1120:force_original_aspect_ratio=decrease,"
                    "pad=900:1120:(ow-iw)/2:(oh-ih)/2:color=0xFFFDF8,"
                    "setsar=1[product];"
                    "[bg][product]overlay=(W-w)/2:(H-h)/2-80,"
                    "drawbox=x=70:y=180:w=940:h=8:color=0xB58A55@0.95:t=fill,"
                    + draw + "[outv]"
                )
                command = [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-framerate", str(edl.fps),
                    "-i", shot.local_asset_path,
                    "-filter_complex", video_filter,
                    "-map", "[outv]",
                    "-frames:v", str(frames),
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(edl.fps),
                    "-movflags", "+faststart", str(clip),
                ]
            else:
                color = "0xF4E8E4" if shot.match_status == "missing" else "0xF3EFE7"
                source = f"color=c={color}:s={edl.width}x{edl.height}:r={edl.fps}:d={duration}"
                command = [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", source,
                    "-vf", draw,
                    "-frames:v", str(frames),
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(edl.fps),
                    "-movflags", "+faststart", str(clip),
                ]
            _run(command, work)
            clips.append(clip)

        concat_file = work / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{clip.name}'" for clip in clips) + "\n",
            encoding="utf-8",
        )
        _run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_file.name,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(edl.fps), "-fps_mode", "cfr",
                "-an", "-movflags", "+faststart", str(output),
            ],
            work,
        )

    probe = subprocess.run(
        [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of", "json", str(output),
        ],
        capture_output=True, text=True, timeout=30, check=False
    )
    if probe.returncode != 0:
        raise ProductionError(f"ffprobe could not inspect the rendered MP4: {probe.stderr[-2000:]}")
    try:
        metadata = json.loads(probe.stdout)
        video_stream = next(stream for stream in metadata["streams"] if stream.get("codec_type") == "video")
        duration_seconds = float(metadata["format"]["duration"])
        width = int(video_stream["width"])
        height = int(video_stream["height"])
        fps_num, fps_den = video_stream["r_frame_rate"].split("/", 1)
        fps = float(fps_num) / float(fps_den)
    except (KeyError, ValueError, StopIteration, TypeError) as exc:
        raise ProductionError(f"Rendered MP4 metadata is incomplete: {exc}") from exc

    if width != edl.width or height != edl.height:
        raise ProductionError(f"Rendered dimensions are {width}x{height}, expected {edl.width}x{edl.height}.")
    if video_stream.get("codec_name") != "h264":
        raise ProductionError(f"Rendered video codec is {video_stream.get('codec_name')}, expected h264.")
    if abs(duration_seconds - edl.duration_seconds) > 1.0:
        raise ProductionError(
            f"Rendered duration is {duration_seconds:.2f}s, expected {edl.duration_seconds}s."
        )

    version_result = subprocess.run(
        [ffmpeg, "-version"], capture_output=True, text=True, timeout=15, check=False
    )
    ffmpeg_version = (version_result.stdout.splitlines() or ["unknown"])[0]
    return VideoRenderReport(
        status="rendered",
        output_path=str(output),
        file_size_bytes=output.stat().st_size,
        sha256=_sha256_file(output),
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        fps=fps,
        video_codec=str(video_stream.get("codec_name") or "unknown"),
        audio_codec=None,
        ffmpeg_version=ffmpeg_version,
        rendered_at=datetime.now(timezone.utc).isoformat(),
    )


def _write_reshoot_checklist(edl: EditDecisionList, path: Path) -> None:
    missing = [shot for shot in edl.shots if shot.reshoot_required]
    lines = [
        "# Reshoot / Missing Footage Checklist",
        "",
        f"- SKU: {edl.sku}",
        f"- Campaign: {edl.campaign_id}",
        "",
    ]
    if not missing:
        lines.append("No product-footage reshoot is required for the current storyboard.")
    else:
        for shot in missing:
            lines.extend(
                [
                    f"## Shot {shot.shot_number:02d} · {shot.start_seconds}s–{shot.end_seconds}s",
                    "",
                    shot.reshoot_note or "No suitable public product image was available.",
                    "",
                    f"Storyboard purpose: {shot.on_screen_text}",
                    "",
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _artifact(path: Path) -> CreativeExportArtifact:
    return CreativeExportArtifact(name=path.name, path=str(path), size_bytes=path.stat().st_size)


class VideoProductionService:
    def __init__(
        self,
        catalog: LocalProductCatalog,
        output_dir: str | Path = "data/renders",
        creative_output_dir: str | Path = "data/outputs/creatives",
        ffmpeg_bin: str | None = None,
        ffprobe_bin: str | None = None,
    ) -> None:
        self.catalog = catalog
        self.output_dir = Path(output_dir)
        self.creative_output_dir = Path(creative_output_dir)
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def generate(self, request: CampaignCreativeRequest) -> VideoProductionResult:
        creative_result = CampaignCreativeService(
            self.catalog, output_dir=self.creative_output_dir
        ).generate(request)
        product = self.catalog.get_product(request.sku)
        if product is None:
            raise CatalogDataError(f"SKU disappeared during production: {request.sku}")
        manifest = self.catalog.load_manifest()
        campaign_id = creative_result.package.brief.campaign_id
        job_dir = self.output_dir / _safe_slug(campaign_id) / _safe_slug(product.sku)
        job_dir.mkdir(parents=True, exist_ok=True)

        edl = build_edit_decision_list(
            creative_result.package,
            product,
            manifest,
            asset_cache_dir=job_dir / "assets",
        )
        edl_path = job_dir / "edit-decision-list.json"
        edl_path.write_text(
            json.dumps(edl.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        video_path = job_dir / "video.mp4"
        report = render_video(
            edl, video_path,
            ffmpeg_bin=self.ffmpeg_bin,
            ffprobe_bin=self.ffprobe_bin,
        )
        report_path = job_dir / "render-report.json"
        report_path.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        reshoot_path = job_dir / "reshoot-checklist.md"
        _write_reshoot_checklist(edl, reshoot_path)
        rights_path = job_dir / "rights-review.md"
        rights_text = (
            "# Source Rights Review\n\n"
            f"- Dataset: {edl.source_dataset}\n"
            f"- License recorded in the local manifest: {edl.license_id}\n"
            f"- License URL: {edl.license_url or 'Not supplied'}\n"
            f"- Attribution: {edl.attribution or 'Not supplied'}\n\n"
            + "\n".join(f"- {warning}" for warning in edl.warnings)
            + "\n\n"
            + (
                "**Review required:** the repository manifest records a conflicting AWS Registry license observation. "
                "Keep the rendered file in the internal demo until the applicable rights are confirmed.\n"
                if edl.rights_review_required
                else "The local dataset manifest reports a verified official license file. Check third-party rights and attribution before external use.\n"
            )
        )
        rights_path.write_text(rights_text, encoding="utf-8")

        exports = list(creative_result.exports)
        exports.extend(_artifact(path) for path in (edl_path, video_path, report_path, reshoot_path, rights_path))
        return VideoProductionResult(
            package=creative_result.package,
            edl=edl,
            render_report=report,
            exports=exports,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Match public ABO catalog images and render a vertical furniture marketing MP4."
    )
    parser.add_argument("--sku", required=True)
    parser.add_argument("--data-dir", default="data/public/abo")
    parser.add_argument("--output-dir", default="data/renders")
    parser.add_argument("--creative-output-dir", default="data/outputs/creatives")
    parser.add_argument("--audience", choices=["B2B", "B2C"], default="B2C")
    parser.add_argument(
        "--objective",
        choices=["brand_awareness", "product_consideration", "lead_generation", "traffic"],
        default="product_consideration",
    )
    parser.add_argument(
        "--angle",
        choices=["product_overview", "color_spotlight", "material_spotlight", "dimension_spotlight", "brand_spotlight", "style_spotlight"],
        default="product_overview",
    )
    parser.add_argument("--target-market", default="United States")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--campaign-id")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    args = parser.parse_args(argv)

    request = CampaignCreativeRequest(
        sku=args.sku,
        audience=args.audience,
        objective=args.objective,
        angle=args.angle,
        target_market=args.target_market,
        duration_seconds=args.duration,
        campaign_id=args.campaign_id,
    )
    result = VideoProductionService(
        LocalProductCatalog(args.data_dir),
        output_dir=args.output_dir,
        creative_output_dir=args.creative_output_dir,
        ffmpeg_bin=args.ffmpeg,
        ffprobe_bin=args.ffprobe,
    ).generate(request)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
