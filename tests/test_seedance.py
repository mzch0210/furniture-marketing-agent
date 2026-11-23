from __future__ import annotations

import json
from pathlib import Path

import pytest

from fma.video_ai.seedance import SeedanceProviderError, SeedanceVideoClient


class FakeResponse:
    def __init__(self, body: bytes, url: str = "https://ark.ap-southeast.bytepluses.com/api/v3", content_type: str = "application/json"):
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


def test_seedance_submits_reference_images_polls_and_downloads_mp4(tmp_path: Path, monkeypatch):
    calls = []
    mp4 = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 64)

    def fake_urlopen(request, timeout=90):
        url = request.full_url if hasattr(request, "full_url") else request
        calls.append((url, request))
        if url.endswith("/contents/generations/tasks") and request.get_method() == "POST":
            payload = json.loads(request.data.decode("utf-8"))
            assert payload["model"] == SeedanceVideoClient.DEFAULT_MODEL
            assert payload["ratio"] == "9:16"
            assert payload["duration"] == 10
            assert payload["resolution"] == "720p"
            assert payload["generate_audio"] is False
            assert payload["omni_reference_task_type"] == "reference"
            assert payload["content"][0]["type"] == "text"
            refs = [item for item in payload["content"] if item["type"] == "image_url"]
            assert len(refs) == 2
            assert refs[0]["role"] == "reference_image"
            return FakeResponse(b'{"id":"cgt-demo-1"}')
        if url.endswith("/contents/generations/tasks/cgt-demo-1"):
            if len([call for call in calls if call[0].endswith("/contents/generations/tasks/cgt-demo-1")]) == 1:
                return FakeResponse(b'{"id":"cgt-demo-1","status":"running"}')
            return FakeResponse(
                b'{"id":"cgt-demo-1","status":"succeeded","content":{"video_url":"https://cdn.byteplus.test/video.mp4"},"ratio":"9:16","duration":10,"resolution":"720p"}'
            )
        if url == "https://cdn.byteplus.test/video.mp4":
            return FakeResponse(mp4, url=url, content_type="video/mp4")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("fma.video_ai.seedance.urllib.request.urlopen", fake_urlopen)
    client = SeedanceVideoClient(api_key="test-key", poll_interval_seconds=0, max_polls=3)
    output = tmp_path / "seedance.mp4"
    result = client.generate_video(
        product_images=[
            {"uri": "https://cdn.example.org/main.jpg"},
            {"uri": "https://cdn.example.org/side.jpg"},
        ],
        prompt="Place the exact dresser in a bright bedroom.",
        output_path=output,
        duration_seconds=10,
    )
    assert output.read_bytes() == mp4
    assert result["task_id"] == "cgt-demo-1"
    assert result["video"]["sha256"]
    assert len(calls) == 4
    assert calls[0][1].get_header("Authorization") == "Bearer test-key"
    assert calls[-1][1].get_header("Authorization") is None


def test_seedance_rejects_non_https_product_images():
    client = SeedanceVideoClient(api_key="test-key")
    with pytest.raises(SeedanceProviderError, match="HTTPS"):
        client.generate_video(
            product_images=[{"uri": "http://example.org/image.jpg"}],
            prompt="A furniture scene.",
            output_path="unused.mp4",
        )


def test_seedance_rejects_invalid_duration_and_resolution():
    client = SeedanceVideoClient(api_key="test-key", model_id=SeedanceVideoClient.FLASH_MODEL)
    with pytest.raises(SeedanceProviderError, match="between 4 and 30"):
        client.generate_video(
            product_images=[{"uri": "https://example.org/image.jpg"}],
            prompt="A furniture scene.",
            output_path="unused.mp4",
            duration_seconds=31,
        )
    with pytest.raises(SeedanceProviderError, match="not supported"):
        client.generate_video(
            product_images=[{"uri": "https://example.org/image.jpg"}],
            prompt="A furniture scene.",
            output_path="unused.mp4",
            resolution="1080p",
        )


def test_seedance_rejects_too_many_reference_images():
    client = SeedanceVideoClient(api_key="test-key", model_id=SeedanceVideoClient.FLASH_MODEL)
    images = [{"uri": f"https://example.org/{index}.jpg"} for index in range(11)]
    with pytest.raises(SeedanceProviderError, match="between 1 and 10"):
        client.generate_video(
            product_images=images,
            prompt="A furniture scene.",
            output_path="unused.mp4",
        )


def test_seedance_reports_provider_task_failure(monkeypatch):
    def fake_urlopen(request, timeout=90):
        url = request.full_url
        if url.endswith("/contents/generations/tasks") and request.get_method() == "POST":
            return FakeResponse(b'{"id":"cgt-failed"}')
        return FakeResponse(b'{"id":"cgt-failed","status":"failed","error":{"message":"Model activation required"}}')

    monkeypatch.setattr("fma.video_ai.seedance.urllib.request.urlopen", fake_urlopen)
    client = SeedanceVideoClient(api_key="test-key", poll_interval_seconds=0, max_polls=1)
    with pytest.raises(SeedanceProviderError, match="Model activation required"):
        client.generate_video(
            product_images=[{"uri": "https://example.org/image.jpg"}],
            prompt="A furniture scene.",
            output_path="unused.mp4",
        )
