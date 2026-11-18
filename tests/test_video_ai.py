from __future__ import annotations

import json
from pathlib import Path

import pytest

from fma.models import CatalogAssetReference, CatalogProduct
from fma.video_ai.runway import RunwayProductAdClient, RunwayProviderError
from fma.video_ai.scenes import (
    build_scene_concept,
    resolve_scene_preset,
    select_product_reference_images,
)


def product(category: str = "DRESSER") -> CatalogProduct:
    return CatalogProduct(
        id="test:sku-1", sku="SKU-1", name="Ventura Dresser",
        category=category, source_dataset="test-dataset",
        source_record_id="SKU-1", source_uri="https://example.org/listing/1",
        source_shard="test.jsonl", raw_record_sha256="a" * 64,
        assets=[
            CatalogAssetReference(
                asset_id="image-main", role="main_image", media_type="image/jpeg",
                source_dataset="test-dataset", source_record_id="SKU-1",
                source_reference="main", source_uri="https://cdn.example.org/main.jpg",
            ),
            CatalogAssetReference(
                asset_id="image-side", role="other_image", media_type="image/jpeg",
                source_dataset="test-dataset", source_record_id="SKU-1",
                source_reference="side", source_uri="https://cdn.example.org/side.jpg",
            ),
            CatalogAssetReference(
                asset_id="image-duplicate", role="other_image", media_type="image/jpeg",
                source_dataset="test-dataset", source_record_id="SKU1",
                source_reference="duplicate", source_uri="https://cdn.example.org/main.jpg",
            ),
            CatalogAssetReference(
                asset_id="bad-image", role="other_image", media_type="image/jpeg",
                source_dataset="test-dataset", source_record_id="SKU-1",
                source_reference="bad", source_uri="http://cdn.example.org/not-https.jpg",
            ),
        ],
    )


def test_auto_scene_preset_maps_furniture_categories():
    assert resolve_scene_preset("DRESSER").key == "bedroom"
    assert resolve_scene_preset("SOFA").key == "living_room"
    assert resolve_scene_preset("DINING_TABLE").key == "dining_room"
    assert resolve_scene_preset("OFFICE_CHAIR").key == "home_office"
    assert resolve_scene_preset("UNKNOWN").key == "studio"


def test_explicit_scene_preset_overrides_category():
    assert resolve_scene_preset("DRESSER", "living_room").key == "living_room"
    with pytest.raises(ValueError, match="Unknown scene preset"):
        resolve_scene_preset("DRESSER", "garage")


def test_reference_images_are_https_deduplicated_and_main_first():
    selected = select_product_reference_images(product())
    assert selected == [
        {"uri": "https://cdn.example.org/main.jpg", "asset_id": "image-main", "role": "main_image"},
        {"uri": "https://cdn.example.org/side.jpg", "asset_id": "image-side", "role": "other_image"},
    ]


def test_scene_concept_preserves_product_and_avoids_unseen_views():
    item = product()
    preset = resolve_scene_preset(item.category)
    prompt = build_scene_concept(item, preset, 10)
    assert "calm, premium American bedroom" in prompt
    assert "Preserve the exact product silhouette" in prompt
    assert "Do not show unseen sides" in prompt
    assert "fake 360-degree orbit" in prompt


class FakeResponse:
    def __init__(self, body: bytes, url: str = "https://api.dev.runwayml.com", content_type: str = "application/json"):
        self.body = body
        self.headers = {"Content-Type": content_type}
        self._url = url

    def read(self, amount: int = -1) -> bytes:
        return self.body if amount < 0 else self.body[:amount]

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_runway_product_ad_submits_polls_and_downloads_mp4(tmp_path: Path, monkeypatch):
    calls = []
    mp4 = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 64)

    def fake_urlopen(request, timeout=60):
        url = request.full_url if hasattr(request, "full_url") else request
        calls.append((url, request))
        if url.endswith("/v1/recipes/product_ad"):
            body = json.loads(request.data.decode("utf-8"))
            assert body["ratio"] == "720:1280"
            return FakeResponse(b'"d":"task-123"}')
        if url.endswith("/v1/tasks/task-123"):
            return FakeResponse(b'{"id":"task-123","status":"SUCCEEDED","output":["https://cdn.runway.test/video.mp4"]}')
        if url == "https://cdn.runway.test/video.mp4":
            return FakeResponse(mp4, url=url, content_type="video/mp4")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("fma.video_ai.runway.urllib.request.urlopen", fake_urlopen)
    client = RunwayProductAdClient(api_key="test-key", poll_interval_seconds=0, max_polls=2)
    output = tmp_path / "product-ad.mp4"
    result = client.generate_product_ad(
        product_images=[{"uri": "https://cdn.example.org/main.jpg"}, {"uri": "https://cdn.example.org/side.jpg"}],
        product_info="Dresser", user_concept="Place in bedroom", output_path=output, duration_seconds=10,
    )
    assert output.read_bytes() == mp4
    assert result["task_id"] == "task-123"
    assert result["video"]["sha256"]
    assert len(calls) == 3
    assert calls[0][1].get_header("Authorization") == "Bearer test-key"
    assert calls[2][1].get_header("Authorization") is None


def test_runway_rejects_non_https_product_images():
    client = RunwayProductAdClient(api_key="test-key")
    with pytest.raises(RunwayProviderError, match="HTTPS"):
        client.generate_product_ad(
            product_images=[{"uri": "http://example.org/image.jpg"}],
            product_info="Item", user_concept="Scene", output_path="unused.mp4",
        )


def test_runway_rejects_duration_outside_recipe_limits():
    client = RunwayProductAdClient(api_key="test-key")
    with pytest.raises(RunwayProviderError, match="between 4 and 15"):
        client.generate_product_ad(
            product_images=[{"uri": "https://example.org/image.jpg"}],
            product_info="Item", user_concept="Scene", output_path="unused.mp4", duration_seconds=30,
        )
