from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import mimetypes
import os
import re
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Mapping

from ...models import (
    CatalogAssetReference,
    CatalogProduct,
    CatalogProductFact,
    FactVerificationStatus,
)

DATASET_NAME = "Amazon Berkeley Objects (ABO)"
DATASET_ID = "amazon-berkeley-objects"
BASE_URL = "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com"
DATASET_PAGE = f"{BASE_URL}/index.html"
LISTINGS_ARCHIVE_URL = f"{BASE_URL}/archives/abo-listings.tar"
LICENSE_URL = f"{BASE_URL}/LICENSE-CC-BY-4.0.txt"
IMAGE_METADATA_URL = f"{BASE_URL}/images/metadata/images.csv.gz"
AWS_REGISTRY_PAGE = "https://registry.opendata.aws/amazon-berkeley-objects/"
AWS_REGISTRY_SOURCE = (
    "https://github.com/awslabs/open-data-registry/blob/main/"
    "datasets/amazon-berkeley-objects.yaml"
)
CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_ID = "CC-BY-4.0"
USER_AGENT = "FurnitureMarketingAgent/0.1 (public dataset adapter)"
ALLOWED_HOSTS = {"amazon-berkeley-objects.s3.us-east-1.amazonaws.com"}
LISTING_SHARD_RE = re.compile(r"listings_[0-9a-f]\.json\.gz$", re.IGNORECASE)

ATTRIBUTION_CREATORS = [
    "Matthieu Guillaumin",
    "Thomas Dideriksen",
    "Kenan Deng",
    "Himanshu Arora",
    "Arnab Dhua",
    "Xi (Brian) Zhang",
    "Tomas Yago-Vicente",
    "Jasmine Collins",
    "Shubham Goel",
    "Jitendra Malik",
]
ATTRIBUTION = (
    "Data, catalog images and 3D models: Amazon.com. "
    "Dataset creators: " + ", ".join(ATTRIBUTION_CREATORS) + "."
)
PAPER_CITATION = (
    "Collins, J., Goel, S., Deng, K., Luthra, A., Xu, L., Gundogdu, E., "
    "Zhang, X., Yago Vicente, T. F., Dideriksen, T., Arora, H., "
    "Guillaumin, M., & Malik, J. (2022). ABO: Dataset and Benchmarks "
    "for Real-World 3D Object Understanding. CVPR 2022."
)

FURNITURE_PRODUCT_TYPES = {
    "SOFA", "SOFA_BED", "LOVESEAT", "FUTON", "RECLINER", "CHAIR",
    "DINING_CHAIR", "OFFICE_CHAIR", "BAR_STOOL", "STOOL", "BENCH",
    "OTTOMAN", "TABLE", "DINING_TABLE", "COFFEE_TABLE", "END_TABLE",
    "CONSOLE_TABLE", "SIDE_TABLE", "NIGHTSTAND", "DESK", "BED",
    "BED_FRAME", "HEADBOARD", "MATTRESS", "DRESSER", "CHEST_OF_DRAWERS",
    "CABINET", "BOOKCASE", "BOOKSHELF", "SHELF", "SHELVING_UNIT",
    "WARDROBE", "CREDENZA", "TV_STAND", "VANITY", "FURNITURE",
}


class AboDataError(RuntimeError):
    """Raised when an ABO download, archive, or record cannot be verified."""


class AboCatalogAdapter:
    """Download and normalize a small, traceable sample from the official ABO source.

    Only the listings archive, official license text and compressed image metadata
    index are downloaded. Image, spin and 3D-model binary archives are not fetched.
    """

    def __init__(self, data_dir: str | Path = "data/public/abo") -> None:
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.archive_path = self.raw_dir / "abo-listings.tar"
        self.license_path = self.raw_dir / "LICENSE-CC-BY-4.0.txt"
        self.image_metadata_path = self.raw_dir / "images.csv.gz"

    def download(self, include_image_index: bool = True) -> dict[str, Path]:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        if not self.archive_path.exists():
            download_file(LISTINGS_ARCHIVE_URL, self.archive_path, max_bytes=256 * 1024 * 1024)
        if not self.license_path.exists():
            download_file(LICENSE_URL, self.license_path, max_bytes=256 * 1024)
        if include_image_index and not self.image_metadata_path.exists():
            download_file(IMAGE_METADATA_URL, self.image_metadata_path, max_bytes=128 * 1024 * 1024)
        return {
            "archive": self.archive_path,
            "license": self.license_path,
            **({"image_metadata": self.image_metadata_path} if self.image_metadata_path.exists() else {}),
        }

    def import_sample(
        self,
        limit: int = 30,
        marketplace: str | None = "amazon.com",
        offline: bool = False,
        include_image_index: bool = True,
    ) -> tuple[list[CatalogProduct], dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        if not offline:
            self.download(include_image_index=include_image_index)

        if not self.archive_path.is_file():
            raise AboDataError(
                f"Missing listings archive: {self.archive_path}. Run without --offline to download it."
            )
        if not self.license_path.is_file():
            raise AboDataError(
                f"Missing official license file: {self.license_path}. Run without --offline to download it."
            )

        license_report = verify_license_file(self.license_path)
        archive_report = inspect_listings_archive(self.archive_path)
        image_index: dict[str, dict[str, Any]] = {}
        image_index_report: dict[str, Any] = {
            "available": False,
            "url": IMAGE_METADATA_URL,
        }
        if self.image_metadata_path.is_file():
            image_index = load_image_index(self.image_metadata_path)
            image_index_report = {
                "available": True,
                "url": IMAGE_METADATA_URL,
                "path": str(self.image_metadata_path),
                "sha256": sha256_file(self.image_metadata_path),
                "records": len(image_index),
            }

        products = select_furniture_sample(
            iter_listing_records(self.archive_path),
            limit=limit,
            marketplace=marketplace,
            image_index=image_index,
        )
        if not products:
            market_label = marketplace or "all marketplaces"
            raise AboDataError(
                f"No furniture products found for {market_label}. "
                "Check the archive schema or broaden the marketplace filter."
            )

        products_path = self.processed_dir / "products.json"
        products_path.write_text(
            json.dumps(
                [product.model_dump(mode="json") for product in products],
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        manifest = build_dataset_manifest(
            archive_report=archive_report,
            license_report=license_report,
            image_index_report=image_index_report,
            products=products,
            requested_limit=limit,
            marketplace=marketplace,
        )
        manifest_path = self.processed_dir / "dataset-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["outputs"] = {
            "products": str(products_path),
            "manifest": str(manifest_path),
        }
        return products, manifest


def download_file(url: str, destination: str | Path, max_bytes: int) -> str:
    """Download one official ABO object atomically and return its SHA-256."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise AboDataError(f"Refusing non-official ABO download URL: {url}")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            final_host = urllib.parse.urlparse(response.geturl()).hostname
            if final_host not in ALLOWED_HOSTS:
                raise AboDataError(f"ABO download redirected to an untrusted host: {final_host}")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise AboDataError(
                    f"Download exceeds size limit ({content_length} > {max_bytes} bytes): {url}"
                )

            digest = hashlib.sha256()
            total = 0
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise AboDataError(f"Download exceeded size limit: {url}")
                    digest.update(chunk)
                    output.write(chunk)
        if total == 0:
            raise AboDataError(f"Downloaded an empty file: {url}")
        os.replace(temporary, destination)
        return digest.hexdigest()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        raise AboDataError(f"Failed to download {url}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_license_text(text: str) -> dict[str, Any]:
    """Verify that the downloaded official license object is the CC BY 4.0 text."""
    marker = "Creative Commons Attribution 4.0 International Public License"
    if marker not in text:
        raise AboDataError(
            "The downloaded license file does not identify itself as CC BY 4.0. "
            "Do not use this dataset until the license is reviewed."
        )
    if "Attribution-NonCommercial" in text or "NonCommercial" in text:
        raise AboDataError(
            "The downloaded license text contains a NonCommercial restriction; "
            "the expected CC BY 4.0 license was not verified."
        )
    return {
        "license_id": LICENSE_ID,
        "license_url": CC_BY_URL,
        "verification_status": "verified_from_official_license_file",
        "verification_method": "official license text marker and absence of NonCommercial clause",
    }


def verify_license_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    report = verify_license_text(text)
    report.update(
        {
            "file_name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "source_url": LICENSE_URL,
        }
    )
    return report


def _listing_shard_relative_path(member_name: str) -> str | None:
    parts = PurePosixPath(member_name).parts
    for index in range(len(parts) - 2):
        if parts[index] == "listings" and parts[index + 1] == "metadata":
            filename = parts[index + 2]
            if LISTING_SHARD_RE.fullmatch(filename):
                return "/".join(parts[index : index + 3])
    return None


def inspect_listings_archive(path: str | Path) -> dict[str, Any]:
    """Inspect tar structure without extracting files to disk."""
    path = Path(path)
    if not path.is_file():
        raise AboDataError(f"Listings archive does not exist: {path}")
    try:
        with tarfile.open(path, mode="r:*") as archive:
            members = archive.getmembers()
            shard_names = sorted(
                relative
                for member in members
                if member.isfile()
                for relative in [_listing_shard_relative_path(member.name)]
                if relative is not None
            )
            license_members = [
                member for member in members
                if member.isfile()
                and PurePosixPath(member.name).name == "LICENSE-CC-BY-4.0.txt"
            ]
            if not shard_names:
                raise AboDataError(
                    "The tar archive contains no listings/metadata/listings_<0-f>.json.gz "
                    "members. The archive layout differs from the expected official ABO layout."
                )
            embedded_license: dict[str, Any] | None = None
            if license_members:
                if license_members[0].size > 256 * 1024:
                    raise AboDataError("Embedded license file is unexpectedly large.")
                stream = archive.extractfile(license_members[0])
                if stream is None:
                    raise AboDataError("Could not read the embedded license file.")
                with stream:
                    embedded_text = stream.read().decode("utf-8")
                embedded_license = verify_license_text(embedded_text)
            return {
                "archive_name": path.name,
                "archive_bytes": path.stat().st_size,
                "archive_sha256": sha256_file(path),
                "tar_member_count": len(members),
                "listing_shards": shard_names,
                "listing_shard_count": len(shard_names),
                "embedded_license_present": bool(license_members),
                "embedded_license": embedded_license,
            }
    except tarfile.TarError as exc:
        raise AboDataError(f"Invalid ABO listings tar archive: {exc}") from exc


def iter_listing_records(archive_path: str | Path) -> Iterator[tuple[dict[str, Any], str]]:
    """Yield (record, shard path) from gzip-compressed NDJSON members."""
    try:
        with tarfile.open(archive_path, mode="r:*") as archive:
            members = sorted(
                (
                    member for member in archive.getmembers()
                    if member.isfile() and _listing_shard_relative_path(member.name)
                ),
                key=lambda member: member.name,
            )
            if not members:
                raise AboDataError("No ABO listing metadata shards were found in the tar archive.")

            for member in members:
                relative_path = _listing_shard_relative_path(member.name)
                if member.size > 100 * 1024 * 1024:
                    raise AboDataError(f"Unexpectedly large metadata shard: {member.name}")
                raw_stream = archive.extractfile(member)
                if raw_stream is None:
                    raise AboDataError(f"Unable to read metadata shard: {member.name}")
                with raw_stream:
                    try:
                        with gzip.GzipFile(fileobj=raw_stream, mode="rb") as records:
                            for line_number, line in enumerate(records, start=1):
                                if not line.strip():
                                    continue
                                try:
                                    payload = json.loads(line.decode("utf-8-sig"))
                                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                                    raise AboDataError(
                                        f"Invalid JSON in {member.name}:{line_number}: {exc}"
                                    ) from exc
                                if isinstance(payload, list):
                                    for record in payload:
                                        if isinstance(record, dict):
                                            yield record, relative_path or member.name
                                elif isinstance(payload, dict):
                                    yield payload, relative_path or member.name
                                else:
                                    raise AboDataError(
                                        f"Expected a JSON object in {member.name}:{line_number}"
                                    )
                    except OSError as exc:
                        raise AboDataError(f"Invalid gzip shard {member.name}: {exc}") from exc
    except tarfile.TarError as exc:
        raise AboDataError(f"Invalid ABO listings tar archive: {exc}") from exc


def load_image_index(path: str | Path) -> dict[str, dict[str, Any]]:
    """Read the image metadata index; image binaries are not downloaded."""
    index: dict[str, dict[str, Any]] = {}
    try:
        with gzip.open(path, mode="rt", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {"image_id", "path"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise AboDataError(
                    "ABO image metadata CSV must contain image_id and path columns."
                )
            for row in reader:
                image_id = (row.get("image_id") or "").strip()
                relative = (row.get("path") or "").strip()
                if not image_id or not _is_safe_relative_path(relative):
                    continue
                try:
                    width = int(row["width"]) if row.get("width") else None
                    height = int(row["height"]) if row.get("height") else None
                except (TypeError, ValueError):
                    width, height = None, None
                index[image_id] = {
                    "path": relative,
                    "width": width,
                    "height": height,
                }
    except (OSError, EOFError) as exc:
        raise AboDataError(f"Could not read ABO image metadata: {exc}") from exc
    return index


def _is_safe_relative_path(value: str) -> bool:
    if not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and all(path.parts)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _entry_value(entry: Any) -> Any:
    return entry.get("value") if isinstance(entry, dict) else entry


def _pick_localized(raw: Mapping[str, Any], field: str) -> tuple[Any, str | None, Any]:
    entries = _as_list(raw.get(field))
    if not entries:
        return None, None, None
    preferred = next(
        (
            entry for entry in entries
            if isinstance(entry, dict)
            and entry.get("language_tag") == "en_US"
            and entry.get("value") not in (None, "")
        ),
        None,
    )
    selected = preferred or next(
        (entry for entry in entries if _entry_value(entry) not in (None, "")),
        None,
    )
    if selected is None:
        return None, None, None
    language = selected.get("language_tag") if isinstance(selected, dict) else None
    return _entry_value(selected), language, selected


def _localized_entries(raw: Mapping[str, Any], field: str) -> list[tuple[Any, str | None, Any]]:
    entries = [entry for entry in _as_list(raw.get(field)) if _entry_value(entry) not in (None, "")]
    english = [
        entry for entry in entries
        if isinstance(entry, dict) and entry.get("language_tag") == "en_US"
    ]
    selected = english or entries
    return [
        (
            _entry_value(entry),
            entry.get("language_tag") if isinstance(entry, dict) else None,
            entry,
        )
        for entry in selected
    ]


def _pick_scalar(raw: Mapping[str, Any], field: str) -> tuple[Any, Any]:
    entries = _as_list(raw.get(field))
    if not entries:
        return None, None
    entry = next((item for item in entries if _entry_value(item) not in (None, "")), None)
    if entry is None:
        return None, None
    return _entry_value(entry), entry


def _product_type(raw: Mapping[str, Any]) -> str | None:
    value, _ = _pick_scalar(raw, "product_type")
    if value is None:
        return None
    return str(value).strip().upper().replace(" ", "_")


def _node_names(raw: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for node in _as_list(raw.get("node")):
        if isinstance(node, dict) and node.get("node_name"):
            names.append(str(node["node_name"]))
    return names


def is_furniture_listing(raw: Mapping[str, Any]) -> bool:
    product_type = _product_type(raw)
    if product_type in FURNITURE_PRODUCT_TYPES:
        return True
    return any("furniture" in node_name.casefold() for node_name in _node_names(raw))


def _source_shard_uri(shard_path: str) -> str:
    parts = PurePosixPath(shard_path).parts
    try:
        index = parts.index("listings")
    except ValueError:
        return DATASET_PAGE
    relative = "/".join(parts[index:])
    return f"{BASE_URL}/{relative}"


def normalize_listing(
    raw: Mapping[str, Any],
    shard_path: str,
    image_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> CatalogProduct:
    item_id = str(raw.get("item_id") or "").strip()
    if not item_id:
        raise AboDataError("ABO listing has no item_id.")
    name, name_language, _ = _pick_localized(raw, "item_name")
    if not name:
        raise AboDataError(f"ABO listing {item_id} has no usable item_name.")

    product_type = _product_type(raw)
    node_names = _node_names(raw)
    category = product_type or (
        node_names[-1].rstrip("/").split("/")[-1] if node_names else "UNKNOWN"
    )
    source_uri = _source_shard_uri(shard_path)
    facts: list[CatalogProductFact] = []

    def add_fact(
        key: str,
        source_field: str,
        value: Any,
        raw_value: Any = None,
        source_language: str | None = None,
        unit: str | None = None,
    ) -> None:
        if value is None or value == "":
            return
        facts.append(
            CatalogProductFact(
                key=key,
                value=value,
                raw_value=raw_value if raw_value is not None else value,
                source_dataset=DATASET_ID,
                source_record_id=item_id,
                source_uri=source_uri,
                source_field=source_field,
                source_language=source_language,
                unit=unit,
                verification_status=FactVerificationStatus.SOURCE_REPORTED,
            )
        )

    add_fact("product_name", "item_name", name, source_language=name_language)
    brand, brand_language, brand_raw = _pick_localized(raw, "brand")
    add_fact("brand", "brand", brand, raw_value=brand_raw, source_language=brand_language)
    type_value, type_raw = _pick_scalar(raw, "product_type")
    add_fact("product_type", "product_type", type_value, raw_value=type_raw)

    for field in ("color", "material", "fabric_type", "finish_type", "pattern", "style"):
        value, language, original = _pick_localized(raw, field)
        add_fact(field, field, value, raw_value=original, source_language=language)

    for index, (value, language, original) in enumerate(
        _localized_entries(raw, "bullet_point"), start=1
    ):
        add_fact(
            f"bullet_point_{index}",
            "bullet_point",
            value,
            raw_value=original,
            source_language=language,
        )

    dimensions = raw.get("item_dimensions")
    if isinstance(dimensions, dict):
        for dimension in ("width", "height", "length", "depth"):
            entry = dimensions.get(dimension)
            if not isinstance(entry, dict):
                continue
            normalized = entry.get("normalized_value")
            normalized = normalized if isinstance(normalized, dict) else {}
            value = normalized.get("value", entry.get("value"))
            unit = normalized.get("unit", entry.get("unit"))
            if value is not None:
                add_fact(
                    f"dimension_{dimension}",
                    f"item_dimensions.{dimension}",
                    {"value": value, "unit": unit},
                    raw_value=entry,
                    unit=str(unit) if unit else None,
                )

    for index, entry in enumerate(_as_list(raw.get("item_weight")), start=1):
        if not isinstance(entry, dict):
            continue
        normalized = entry.get("normalized_value")
        normalized = normalized if isinstance(normalized, dict) else {}
        value = normalized.get("value", entry.get("value"))
        unit = normalized.get("unit", entry.get("unit"))
        if value is not None:
            add_fact(
                f"item_weight_{index}",
                "item_weight",
                {"value": value, "unit": unit},
                raw_value=entry,
                unit=str(unit) if unit else None,
            )

    for field in ("model_number", "model_name", "model_year"):
        value, original = _pick_scalar(raw, field)
        add_fact(field, field, value, raw_value=original)

    bullet_points = [
        str(value)
        for value, _, _ in _localized_entries(raw, "bullet_point")
        if value
    ]
    description = "\n".join(bullet_points) or None

    image_index = image_index or {}
    assets: list[CatalogAssetReference] = []

    def add_image(image_id: Any, role: str) -> None:
        if not image_id:
            return
        image_id = str(image_id)
        metadata = image_index.get(image_id, {})
        relative_path = str(metadata.get("path") or "")
        source_path = f"images/small/{relative_path}" if relative_path else None
        source_uri = (
            f"{BASE_URL}/{source_path}"
            if source_path and _is_safe_relative_path(source_path)
            else None
        )
        mime_type = mimetypes.guess_type(relative_path)[0] if relative_path else None
        assets.append(
            CatalogAssetReference(
                asset_id=f"abo:image:{image_id}",
                role=role,
                media_type=mime_type or "image/unknown",
                source_dataset=DATASET_ID,
                source_record_id=item_id,
                source_reference=image_id,
                source_path=source_path,
                source_uri=source_uri,
                width=metadata.get("width"),
                height=metadata.get("height"),
            )
        )

    add_image(raw.get("main_image_id"), "main_image")
    for image_id in _as_list(raw.get("other_image_id")):
        add_image(image_id, "other_image")

    if raw.get("spin_id"):
        assets.append(
            CatalogAssetReference(
                asset_id=f"abo:spin:{raw['spin_id']}",
                role="turntable_360",
                media_type="image_sequence",
                source_dataset=DATASET_ID,
                source_record_id=item_id,
                source_reference=str(raw["spin_id"]),
            )
        )
    model_id = raw.get("3dmodel_id") or raw.get("model_3d_id")
    if model_id:
        assets.append(
            CatalogAssetReference(
                asset_id=f"abo:3dmodel:{model_id}",
                role="product_3d_model",
                media_type="model/gltf-binary",
                source_dataset=DATASET_ID,
                source_record_id=item_id,
                source_reference=str(model_id),
            )
        )

    raw_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return CatalogProduct(
        id=f"abo:{item_id}",
        sku=item_id,
        name=str(name),
        brand=str(brand) if brand else None,
        category=category,
        description=description,
        marketplace=str(raw.get("domain_name") or "") or None,
        source_dataset=DATASET_ID,
        source_record_id=item_id,
        source_uri=source_uri,
        source_shard=shard_path,
        raw_record_sha256=hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
        facts=facts,
        assets=assets,
    )


def select_furniture_sample(
    records: Iterable[tuple[dict[str, Any], str]],
    limit: int = 30,
    marketplace: str | None = "amazon.com",
    image_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[CatalogProduct]:
    """Select a deterministic, category-balanced sample without loading all records."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    buckets: dict[str, list[CatalogProduct]] = defaultdict(list)

    for raw, shard_path in records:
        if marketplace and raw.get("domain_name") != marketplace:
            continue
        if not is_furniture_listing(raw):
            continue
        try:
            product = normalize_listing(raw, shard_path, image_index=image_index)
        except AboDataError:
            continue
        bucket = product.category
        if len(buckets[bucket]) < limit:
            buckets[bucket].append(product)

    selected: list[CatalogProduct] = []
    positions = {category: 0 for category in sorted(buckets)}
    categories = sorted(buckets)
    while len(selected) < limit:
        added = False
        for category in categories:
            position = positions[category]
            if position < len(buckets[category]):
                selected.append(buckets[category][position])
                positions[category] += 1
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break
    return selected


def build_dataset_manifest(
    archive_report: Mapping[str, Any],
    license_report: Mapping[str, Any],
    image_index_report: Mapping[str, Any],
    products: list[CatalogProduct],
    requested_limit: int,
    marketplace: str | None,
) -> dict[str, Any]:
    categories: dict[str, int] = defaultdict(int)
    for product in products:
        categories[product.category] += 1
    return {
        "manifest_version": 1,
        "dataset": {
            "id": DATASET_ID,
            "name": DATASET_NAME,
            "official_page": DATASET_PAGE,
            "publisher": "Amazon.com",
            "source_archive_url": LISTINGS_ARCHIVE_URL,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
        "license": {
            **dict(license_report),
            "dataset_page_declared_license": LICENSE_ID,
            "aws_registry_current_source_yaml_license": LICENSE_ID,
            "aws_registry_cached_rendered_page_observation": (
                "A cached rendered Registry page snapshot was observed displaying "
                "CC BY-NC 4.0; the current Registry source YAML, official dataset "
                "page and downloaded official license text identify CC BY 4.0. "
                "Recheck source pages before external redistribution."
            ),
            "registry_page": AWS_REGISTRY_PAGE,
            "registry_source_yaml": AWS_REGISTRY_SOURCE,
            "attribution": ATTRIBUTION,
            "license_url": CC_BY_URL,
            "no_endorsement_notice": (
                "Amazon.com and UC Berkeley do not endorse this project or its "
                "generated marketing content."
            ),
            "third_party_rights_note": (
                "CC BY covers only rights the licensor can license; trademarks, "
                "privacy, publicity and other third-party rights may require "
                "separate review."
            ),
        },
        "archive": dict(archive_report),
        "image_metadata": dict(image_index_report),
        "sample": {
            "requested_limit": requested_limit,
            "selected_count": len(products),
            "marketplace_filter": marketplace,
            "category_counts": dict(sorted(categories.items())),
            "item_ids": [product.sku for product in products],
        },
        "data_quality": {
            "product_fact_verification_default": "source_reported",
            "unknown_attributes_policy": "Missing source fields remain absent/Unknown; no values are inferred.",
            "vendor_claim_warning": (
                "ABO product descriptions are source-reported catalog content and "
                "are not independently verified or factory-confirmed."
            ),
        },
        "attribution": ATTRIBUTION,
        "paper_citation": PAPER_CITATION,
        "modifications": [
            "Selected a category-balanced furniture subset.",
            "Normalized selected catalog fields into the Furniture Marketing Agent domain schema.",
            "Resolved image IDs to official small-image object URLs when image metadata was available.",
            "No image binaries, 360-degree archives or 3D model archives were downloaded by this adapter.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import a small, source-traceable furniture sample from the official ABO dataset."
    )
    parser.add_argument("--data-dir", default="data/public/abo", help="Local ABO data directory.")
    parser.add_argument("--limit", type=int, default=30, help="Maximum number of furniture SKUs.")
    parser.add_argument(
        "--marketplace",
        default="amazon.com",
        help="ABO domain_name to include (default: amazon.com). Use --all-marketplaces to disable.",
    )
    parser.add_argument(
        "--all-marketplaces",
        action="store_true",
        help="Include all marketplaces instead of filtering to amazon.com.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use already-downloaded files only; do not make network requests.",
    )
    parser.add_argument(
        "--skip-image-index",
        action="store_true",
        help="Do not download/use images.csv.gz; product image IDs are still retained.",
    )
    args = parser.parse_args(argv)

    adapter = AboCatalogAdapter(args.data_dir)
    products, manifest = adapter.import_sample(
        limit=args.limit,
        marketplace=None if args.all_marketplaces else args.marketplace,
        offline=args.offline,
        include_image_index=not args.skip_image_index,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "products_imported": len(products),
                "categories": manifest["sample"]["category_counts"],
                "license_status": manifest["license"]["verification_status"],
                "archive_shards": manifest["archive"]["listing_shard_count"],
                "products_file": str(adapter.processed_dir / "products.json"),
                "manifest_file": str(adapter.processed_dir / "dataset-manifest.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
