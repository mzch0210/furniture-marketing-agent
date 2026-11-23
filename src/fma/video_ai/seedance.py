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


class SeedanceProviderError(RuntimeError):
    """Raised when BytePlus ModelArk cannot produce a Seedance video."""


class SeedanceVideoClient:
    """Stdlib-only client for the official BytePlus ModelArk video-generation API."""

    API_PATH = "/contents/generations/tasks"
    DEFAULT_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
    DEFAULT_MODEL = "dreamina-seedance-2-5-260628"
    FLASH_MODEL = "dreamina-seedance-2-5-flash-261115"
    MODEL_IMAGE_LIMITS = {
        DEFAULT_MODEL: 30,
        FLASH_MODEL: 10,
    }
    MODEL_RESOLUTIONS = {
        DEFAULT_MODEL: {"480p", "720p", "1080p", "4k"},
        FLASH_MODEL: {"480p", "720p"},
    }
    RATIOS = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"}

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 90,
        poll_interval_seconds: float = 10.0,
        max_polls: int = 180,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("BYTEPLUS_MODELARK_API_KEY")
            or os.getenv("ARK_API_KEY")
            or ""
        )
        self.model_id = model_id or os.getenv("SEEDANCE_MODEL_ID") or self.DEFAULT_MODEL
        self.base_url = (
            base_url
            or os.getenv("BYTEPLUS_MODELARK_BASE_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        if not self.api_key:
            raise SeedanceProviderError(
                "BYTEPLUS_MODELARK_API_KEY (or ARK_API_KEY) is not configured."
            )
        if self.model_id not in self.MODEL_IMAGE_LIMITS:
            raise SeedanceProviderError(
                f"Unsupported Seedance model ID: {self.model_id}. "
                "Use the Seedance 2.5 or Seedance 2.5 Flash model ID."
            )
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise SeedanceProviderError("BytePlus ModelArk base URL must use HTTPS.")

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "FurnitureMarketingAgent/0.3",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1600]
            raise SeedanceProviderError(
                f"BytePlus ModelArk returned HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SeedanceProviderError(f"Unable to reach BytePlus ModelArk: {exc}") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SeedanceProviderError(
                "BytePlus ModelArk returned a non-JSON response."
            ) from exc
        if not isinstance(data, dict):
            raise SeedanceProviderError("BytePlus ModelArk returned an unexpected response shape.")
        return data

    def _wait_for_task(self, task_id: str) -> dict[str, Any]:
        task_path = f"{self.API_PATH}/{urllib.parse.quote(task_id, safe='')}"
        for _ in range(self.max_polls):
            task = self._request_json("GET", task_path)
            status = str(task.get("status") or "").lower()
            if status == "succeeded":
                return task
            if status in {"failed", "cancelled", "expired"}:
                error = task.get("error") or {}
                detail = error.get("message") if isinstance(error, dict) else error
                raise SeedanceProviderError(
                    f"Seedance task {status}: {detail or 'provider returned no error detail'}"
                )
            if status not in {"queued", "running"}:
                raise SeedanceProviderError(
                    f"Seedance task returned an unknown status: {status or 'missing'}"
                )
            time.sleep(self.poll_interval_seconds)
        raise SeedanceProviderError(
            f"Seedance task did not finish after {self.max_polls} status checks."
        )

    @staticmethod
    def _video_url(task: dict[str, Any]) -> str:
        content = task.get("content")
        candidate = content.get("video_url") if isinstance(content, dict) else None
        parsed = urllib.parse.urlsplit(candidate or "")
        if (
            not isinstance(candidate, str)
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise SeedanceProviderError(
                "Seedance task succeeded but returned no valid HTTPS video URL."
            )
        return candidate

    def _download_video(
        self,
        url: str,
        output_path: str | Path,
        max_bytes: int = 250 * 1024 * 1024,
    ) -> dict[str, Any]:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise SeedanceProviderError("Refusing to download a non-HTTPS Seedance video URL.")
        request = urllib.request.Request(url, headers={"User-Agent": "FurnitureMarketingAgent/0.3"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                final_url = response.geturl()
                final = urllib.parse.urlsplit(final_url)
                if final.scheme != "https" or not final.hostname:
                    raise SeedanceProviderError("Seedance download redirected to a non-HTTPS URL.")
                data = response.read(max_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise SeedanceProviderError(
                f"Seedance video download returned HTTP {exc.code}."
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SeedanceProviderError(f"Unable to download generated Seedance video: {exc}") from exc
        if len(data) > max_bytes:
            raise SeedanceProviderError(f"Generated video exceeds the {max_bytes}-byte download limit.")
        if len(data) < 12 or b"ftyp" not in data[:32]:
            raise SeedanceProviderError("Seedance output is not a recognizable MP4 file.")
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

    def generate_video(
        self,
        product_images: list[dict[str, str]],
        prompt: str,
        output_path: str | Path,
        duration_seconds: int = 10,
        ratio: str = "9:16",
        resolution: str = "720p",
        generate_audio: bool = False,
        watermark: bool = True,
        seed: int | None = None,
    ) -> dict[str, Any]:
        max_images = self.MODEL_IMAGE_LIMITS[self.model_id]
        if not 1 <= len(product_images) <= max_images:
            raise SeedanceProviderError(
                f"{self.model_id} accepts between 1 and {max_images} reference images."
            )
        if not 4 <= duration_seconds <= 30:
            raise SeedanceProviderError("Seedance 2.5 duration must be between 4 and 30 seconds.")
        if ratio not in self.RATIOS:
            raise SeedanceProviderError(f"Unsupported Seedance aspect ratio: {ratio}")
        if resolution not in self.MODEL_RESOLUTIONS[self.model_id]:
            supported = ", ".join(sorted(self.MODEL_RESOLUTIONS[self.model_id]))
            raise SeedanceProviderError(
                f"Resolution {resolution} is not supported by {self.model_id}; choose {supported}."
            )
        if not prompt.strip() or len(prompt.split()) > 1000:
            raise SeedanceProviderError("Prompt must be non-empty and no longer than 1,000 English words.")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt.strip()}]
        for image in product_images:
            uri = image.get("uri", "")
            parsed = urllib.parse.urlsplit(uri)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise SeedanceProviderError("Every Seedance product reference image must be an HTTPS URL.")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": uri},
                    "role": "reference_image",
                }
            )

        payload: dict[str, Any] = {
            "model": self.model_id,
            "content": content,
            "omni_reference_task_type": "reference",
            "resolution": resolution,
            "ratio": ratio,
            "duration": duration_seconds,
            "generate_audio": generate_audio,
            "watermark": watermark,
        }
        if seed is not None:
            if not 0 <= seed <= 2_147_483_647:
                raise SeedanceProviderError("Seed must be between 0 and 2147483647.")
            payload["seed"] = seed

        created = self._request_json("POST", self.API_PATH, payload)
        task_id = created.get("id") or created.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise SeedanceProviderError("BytePlus ModelArk did not return a video task ID.")
        task = self._wait_for_task(task_id)
        video_url = self._video_url(task)
        downloaded = self._download_video(video_url, output_path)
        return {
            "provider": "byteplus_modelark",
            "model_id": self.model_id,
            "task_id": task_id,
            "status": "succeeded",
            "video_url": video_url,
            "video": downloaded,
            "duration_seconds_requested": duration_seconds,
            "ratio_requested": ratio,
            "resolution_requested": resolution,
            "generate_audio_requested": generate_audio,
            "watermark_requested": watermark,
            "provider_task": {
                key: task.get(key)
                for key in ("resolution", "ratio", "duration", "seed", "usage")
                if task.get(key) is not None
            },
        }
