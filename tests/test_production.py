import shutil
import subprocess
from pathlib import Path

import pytest

from fma.marketing import build_creative_package
from fma.models import (
    CampaignCreativeRequest, CampaignObjective, CatalogAssetReference,
    CatalogProduct, CatalogProductFact, CreativeAngle, EditDecisionList,
    EditDecisionShot, FactVerificationStatus, MatchedMediaAsset, MarketingAudience,
)
from fma.production import (
    ProductionError, _candidate_urls, build_edit_decision_list, render_video,
)

SOURCE = "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/listings/metadata/listings_0.json.gz"


def sample_product(with_image=True):
    assets = []
    if with_image:
        assets = [CatalogAssetReference(
            asset_id="abo:image:001", role="main_image", media_type="image/jpeg",
            source_dataset="amazon-berkeley-objects", source_record_id="SKU-101",
            source_reference="001", source_path="images/small/ab/001.jpg",
            source_uri="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/images/small/ab/001.jpg",
            width=256, height=256,
        )]
    return CatalogProduct(
        id="abo:SKU-101", sku="SKU-101", name="Contemporary Sofa",
        brand="Example Brand", category="SOFA", description="Public catalog description.",
        marketplace="amazon.com", source_dataset="amazon-berkeley-objects",
        source_record_id="SKU-101", source_uri=SOURCE,
        source_shard="listings/metadata/listings_0.json.gz", raw_record_sha256="a" * 64,
        facts=[
            CatalogProductFact(
                key="product_name", value="Contemporary Sofa",
                source_dataset="amazon-berkeley-objects", source_record_id="SKU-101",
                source_uri=SOURCE, source_field="item_name",
                verification_status=FactVerificationStatus.SOURCE_REPORTED,
            ),
            CatalogProductFact(
                key="product_type", value="SOFA",
                source_dataset="amazon-berkeley-objects", source_record_id="SKU-101",
                source_uri=SOURCE, source_field="product_type",
                verification_status=FactVerificationStatus.SOURCE_REPORTED,
            ),
        ], assets=assets,
    )


def creative_request():
    return CampaignCreativeRequest(
        sku="SKU-101", audience=MarketingAudience.B2C,
        objective=CampaignObjective.PRODUCT_CONSIDERATION,
        angle=CreativeAngle.PRODUCT_OVERVIEW, duration_seconds=30,
    )


def manifest():
    return {
        "dataset": {"name": "Amazon Berkeley Objects (ABO)"},
        "license": {
            "license_id": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "verification_status": "verified_from_official_license_file",
            "attribution": "Data and images: Amazon.com.",
        },
        "attribution": "Data and images: Amazon.com.",
    }


def test_asset_url_allowlist_rejects_non_abo_hosts():
    asset = CatalogAssetReference(
        asset_id="bad", role="main_image", media_type="image/jpeg",
        source_dataset="test", source_record_id="1", source_reference="1",
        source_uri="https://example.com/image.jpg",
    )
    with pytest.raises(ProductionError, match="non-official"):
        _candidate_urls(asset)


def test_asset_url_prefers_original_and_falls_back_to_small():
    asset = sample_product().assets[0]
    candidates = _candidate_urls(asset)
    assert candidates[0][1] == "original"
    assert "/images/original/ab/001.jpg" in candidates[0][0]
    assert candidates[1] == (asset.source_uri, "small")


def test_edl_matches_image_and_generates_title_cards(tmp_path, monkeypatch):
    product = sample_product()
    package = build_creative_package(product, creative_request(), manifest())
    local_image = tmp_path / "cached.jpg"
    local_image.write_bytes(b"test-image-bytes")

    def fake_download(asset, cache_dir, license_id="CC-BY-4.0", **kwargs):
        return MatchedMediaAsset(
            asset_id=asset.asset_id, role=asset.role, media_type="image/jpeg",
            source_dataset=asset.source_dataset, source_record_id=asset.source_record_id,
            source_uri=asset.source_uri, downloaded_uri=asset.source_uri,
            local_path=str(local_image), sha256="b" * 64,
            size_bytes=local_image.stat().st_size, source_variant="small",
            license_id=license_id, width=256, height=256,
        )

    monkeypatch.setattr("fma.production.download_asset", fake_download)
    edl = build_edit_decision_list(package, product, manifest(), tmp_path / "assets")
    assert edl.media_basis == "catalog_still_image_animation"
    assert edl.shots[0].match_status == "matched"
    assert edl.shots[0].local_asset_path == str(local_image)
    assert all(shot.match_status == "matched" for shot in edl.shots)
    assert edl.shots[-1].visual_type == "generated_title_card"
    assert len(edl.assets) == 1


def test_edl_marks_missing_product_shots_and_reshoot_notes(tmp_path):
    product = sample_product(with_image=False)
    package = build_creative_package(product, creative_request(), manifest())
    edl = build_edit_decision_list(package, product, manifest(), tmp_path / "assets")
    missing = [shot for shot in edl.shots if shot.match_status == "missing"]
    assert len(missing) == 3
    assert all(shot.reshoot_required and shot.reshoot_note for shot in missing)
    assert edl.shots[-1].visual_type == "generated_title_card"


def test_render_video_creates_valid_vertical_h264_mp4(tmp_path):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("FFmpeg/ffprobe are not installed.")
    filters = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True)
    if "drawtext" not in (filters.stdout + filters.stderr):
        pytest.skip("FFmpeg drawtext filter is unavailable.")

    source = tmp_path / "source.png"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=c=0x9CA3AF:s=320x320:d=1",
         "-frames:v", "1", str(source)],
        check=True, capture_output=True,
    )
    edl = EditDecisionList(
        campaign_id="test-campaign", sku="SKU-101", duration_seconds=4, media_basis="catalog_still_image_animation",
        shots=[
            EditDecisionShot(
                shot_number=1, start_seconds=0, end_seconds=2,
                visual_type="catalog_still_image_animation", match_status="matched",
                asset_id="abo:image:001", local_asset_path=str(source),
                source_uri="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/images/small/ab/001.jpg",
                on_screen_text="Furniture product spotlight",
                voiceover="A closer look at this sofa.",
            ),
            EditDecisionShot(
                shot_number=2, start_seconds=2, end_seconds=4,
                visual_type="generated_title_card", match_status="matched",
                on_screen_text="Explore the product",
                voiceover="Ask the seller for details.",
            ),
        ],
        source_dataset="amazon-berkeley-objects", source_record_id="SKU-101",
        attribution="Data and images: Amazon.com.", license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
    )
    output = tmp_path / "video.mp4"
    report = render_video(edl, output)
    assert output.is_file() and output.stat().st_size > 0
    assert report.status == "rendered"
    assert (report.width, report.height) == (1080, 1920)
    assert report.video_codec == "h264"
    assert report.duration_seconds == pytest.approx(4, abs=0.5)
    assert len(report.sha256) == 64


def test_renderer_reports_missing_ffmpeg_clearly(tmp_path):
    edl = EditDecisionList(
        campaign_id="test", sku="SKU-101", duration_seconds=1, media_basis="generated_cards_with_missing_product_shots",
        shots=[EditDecisionShot(
            shot_number=1, start_seconds=0, end_seconds=1,
            visual_type="generated_title_card", match_status="matched",
            on_screen_text="Test", voiceover="Test",
        )],
        source_dataset="test", source_record_id="1", attribution="",
        license_id="unknown", license_url="",
    )
    with pytest.raises(ProductionError, match="Install FFmpeg"):
        render_video(edl, tmp_path / "missing.mp4", ffmpeg_bin="fma-no-such-ffmpeg")
