from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class RunwayProviderError(RuntimeError):
    """Raised when the Runway Product Ad API cannot produce a video."""


class RunwayProductAdClient:
    """Small stdlib-only client for Runway's Product Ad Recipe."""

    API_VERSION = "2024-11-06"
    WORKFLOW_VERSION = "2026-07"
    DEFAULT_BASE_URL = "https://api.dev.runwayml.com"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
        poll_interval_seconds: float = 5.0,
        max_polls: int = 180,
    ) -> None:
        self.api_key = api_key or os.getenv("RUNWAYML_API_SECRET", "")
        self.base_url = (base_url or os.getenv("RUNWAY_API_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        if not self.api_key:
            raise RunwayProviderError(
                "RUNWAYML_API_SECRET is not configured. Add it as an environment variable or GitHub Actions secret."
            )
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise RunwayProviderError("Runway API base URL must use HTTPS.")

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Runway-Version": self.API_VERSION,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "FurnitureMarketingAgent/0.2",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RunwayProviderError(f"Runway API returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RunwayProviderError(f"Unable to reach Runway API: {exc}") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunwayProviderError("Runway API returned a non-JSON response.") from exc
        if not isinstance(data, dict):
            raise RunwayProviderError("Runway API returned an unexpected response shape.")
        return data

    @staticmethod
    def _output_url(task: dict[str, Any]) -> str:
        output = task.get("output")
        candidate: Any = None
        if isinstance(output, list) and output:
            candidate = output[0]
        elif isinstance(output, dict):
            candidate = output.get("url") or output.get("video") or output.get("uri")
        if isinstance(candidate, dict):
            candidate = candidate.get("url") or candidate.get("uri")
        if not isinstance(candidate, str) or not candidate:
            raise RunwayProviderError("Runway task succeeded but returned no video URL.")
        parsed = urllib.parse.urlsplit(candidate)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise RunwayProviderError("Runway returned an invalid video URL; refusing to download it.")
        return candidate

    def _wait_for_task(self, task_id: str) -> dict[str, Any]:
        escaped_id = urllib.parse.quote(task_id, safe="")
        for _ in range(self.max_polls):
            task = self._request_json("GET", f"/v1/tasks/{escaped_id}")
            status = str(task.get("status") or "").upper()
            if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
                return task
            if status in {"FAILED", "CANCELED", "CANCELLED"}:
                failure = task.get("failure") or task.get("error") or task.get("failureCode") or "unspecified provider failure"
                raise RunwayProviderError(f"Runway video task {status.lower()}: {failure}")
            time.sleep(self.poll_interval_seconds)
        raise RunwayProviderError(
            f"Runway video task did not finish after {self.max_polls} status checks."
        )

    def _download_video(self, url: str, output_path: str | Path, max_bytes: int = 250 * 1024 * 1024) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": "FurnitureMarketingAgent/0.2"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                final_url = response.geturl()
                parsed = urllib.parse.urlsplit(final_url)
                if parsed.scheme != "https" or not parsed.hostname:
                    raise RunwayProviderError("Video download redirected to a non-HTTPS URL.")
                data = response.read(max_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise RunwayProviderError(f"Runway video download returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RunwayProviderError(f"Unable to download generated Runway video: {exc}") from exc
        if len(data) > max_bytes:
            raise RunwayProviderError(f"Generated video exceeds the {max_bytes}-byte download limit.")
        if len(data) < 12 or b"ftyp" not in data[:32]:
            raise RunwayProviderError("Runway output is not a recognizable MP4 file.")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".part")
        temporary.write_bytes(data)
        temporary.replace(output)
        return {
            "path": str(output.resolve()),
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def generate_product_ad(
        self,
        product_images: list[dict[str, str]],
        product_info: str,
        user_concept: str,
        output_path: str | Path,
        duration_seconds: int = 10,
        ratio: str = "720:1280",
        style_images: list[str] | None = None,
        audio: bool = False,
    ) -> dict[str, Any]:
        if not 1 <= len(product_images) <= 10:
            raise RunwayProviderError("Provide between 1 and 10 product reference images.")
        if not 4 <= duration_seconds <= 15:
            raise RunwayProviderError("Runway Product Ad duration must be between 4 and 15 seconds.")
        if ratio not in {"720:1280", "1080:1920", "1280:720", "1920:1080", "960:960", "1440:1440"}:
            raise RunwayProviderError(f"Unsupported Product Ad ratio: {ratio}")
        if len(product_info) > 2500 or len(user_concept) > 3500:
            raise RunwayProviderError("Product info or creative direction exceeds Runway's documented character limit.")
        if style_images and len(style_images) > 4:
            raise RunwayProviderError("Runway Product Ad accepts at most four style reference images.")

        image_payload: list[dict[str, str]] = []
        for item in product_images:
            uri = item.get("uri", "")
            parsed = urllib.parse.urlsplit(uri)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise RunwayProviderError("Every product reference image must be an HTTPS URL.")
            image_payload.append({"uri": uri})
        style_payload = []
        for uri in style_images or []:
            parsed = urllib.parse.urlsplit(uri)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise RunwayProviderError("Every style reference image must be an HTTPS URL.")
            style_payload.append({"uri": uri})

        payload: dict[str, Any] = {
            "version": self.WORKFLOW_VERSION,
            "productImages": image_payload,
            "productInfo": product_info,
            "userConcept": user_concept,
            "ratio": ratio,
            "duration": duration_seconds,
            "audio": audio,
        }
        if style_payload:
            payload["styleImages"] = style_payload

        created = self._request_json("POST", "/v1/recipes/product_ad", payload)
        task_id = created.get("id") or created.get("taskId")
        if not isinstance(task_id, str) or not task_id:
            raise RunwayProviderError("Runway Product Ad API did not return a task ID.")
        task = self._wait_for_task(task_id)
        video_url = self._output_url(task)
        downloaded = self._download_video(video_url, output_path)
        return {
            "provider": "runway",
            "recipe": "product_ad",
            "workflow_version": self.WORKFLOW_VERSION,
            "api_version": self.API_VERSION,
            "task_id": task_id,
            "status": "succeeded",
            "video_url": video_url,
            "video": downloaded,
            "duration_seconds_requested": duration_seconds,
            "ratio_requested": ratio,
            "audio_requested": audio,
        }
