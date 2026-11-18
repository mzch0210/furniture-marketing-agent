import gzip
import io
import json
import tarfile
from pathlib import Path

import pytest

from fma.data_sources.abo import (
    AboDataError, inspect_listings_archive, is_furniture_listing,
    load_image_index, normalize_listing, select_furniture_sample,
    verify_license_text,
)

LICENSE = "Creative Commons Attribution 4.0 International Public License"


def listing(item_id, kind, name, domain="amazon.com"):
    return {
        "item_id": item_id,
        "domain_name": domain,
        "item_name": [{"language_tag": "en_US", "value": name}],
        "brand": [{"language_tag": "en_US", "value": "Example"}],
        "product_type": [{"value": kind}],
        "bullet_point": [{"language_tag": "en_US", "value": "Source-reported detail"}],
        "item_dimensions": {"width": {"value": 42, "unit": "inches"}},
        "main_image_id": "image001",
    }


def write_tar(path, rows):
    payload = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb") as out:
        out.write(payload)
    data = compressed.getvalue()
    with tarfile.open(path, "w") as archive:
        info = tarfile.TarInfo("listings/metadata/listings_0.json.gz")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))


def test_cc_by_license_is_verified():
    assert verify_license_text(LICENSE)["license_id"] == "CC-BY-4.0"


def test_noncommercial_license_is_rejected():
    with pytest.raises(AboDataError):
        verify_license_text("Creative Commons Attribution-NonCommercial 4.0")


def test_furniture_filter_supports_product_type_and_node_path():
    assert is_furniture_listing(listing("A1", "SOFA", "Sofa"))
    assert is_furniture_listing({"node": [{"path": "/Categories/Furniture/Sofas"}]})
    assert not is_furniture_listing(listing("A2", "LAPTOP", "Laptop"))


def test_furniture_filter_rejects_accessories_and_broad_parent_nodes():
    accessory = listing("A3", "ABIS_HOME_IMPROVEMENT", "Furniture bumper pads")
    accessory["node"] = [{
        "path": "/Categories/Home Improvement/Furniture Accessories/Furniture Pads"
    }]
    assert not is_furniture_listing(accessory)

    broad_parent = {"node": [{"path": "/Categories/Furniture"}]}
    assert not is_furniture_listing(broad_parent)


def test_furniture_filter_accepts_specific_furniture_leaf_even_if_type_is_generic():
    sofa = listing("A4", "ABIS_HOME_IMPROVEMENT", "Sofa")
    sofa["node"] = [{
        "path": "/Categories/Furniture/Living Room Furniture/Sofas & Couches"
    }]
    assert is_furniture_listing(sofa)
    product = normalize_listing(sofa, "listings/metadata/listings_0.json.gz")
    assert product.category == "Sofas & Couches"


def test_sample_excludes_furniture_accessories():
    sofa = listing("A5", "SOFA", "Sofa")
    accessory = listing("A6", "ABIS_HOME_IMPROVEMENT", "Adhesive bumper pads")
    accessory["node"] = [{
        "path": "/Categories/Home Improvement/Furniture Accessories/Furniture Pads"
    }]
    selected = select_furniture_sample([
        (sofa, "listings/metadata/listings_0.json.gz"),
        (accessory, "listings/metadata/listings_0.json.gz"),
    ], limit=10)
    assert [item.sku for item in selected] == ["A5"]


def test_normalization_preserves_provenance_and_image_reference():
    product = normalize_listing(
        listing("B0001", "SOFA", "Sofa"),
        "listings/metadata/listings_0.json.gz",
        {"image001": {"path": "ab/file.jpg", "width": 256, "height": 200}},
    )
    assert product.sku == "B0001"
    assert product.facts[0].verification_status.value == "source_reported"
    assert product.assets[0].source_uri.endswith("/images/small/ab/file.jpg")
    assert product.raw_record_sha256


def test_missing_product_attributes_are_not_invented():
    row = {"item_id": "B0002", "item_name": [{"language_tag": "en_US", "value": "Chair"}],
           "product_type": [{"value": "CHAIR"}]}
    product = normalize_listing(row, "listings/metadata/listings_0.json.gz")
    keys = {fact.key for fact in product.facts}
    assert "material" not in keys
    assert "dimension_width" not in keys
    assert product.brand is None


def test_sample_filters_marketplace_and_balances_categories():
    rows = [
        (listing("1", "SOFA", "Sofa 1"), "listings/metadata/listings_0.json.gz"),
        (listing("2", "SOFA", "Sofa 2"), "listings/metadata/listings_0.json.gz"),
        (listing("3", "CHAIR", "Chair"), "listings/metadata/listings_0.json.gz"),
        (listing("4", "TABLE", "UK table", "amazon.co.uk"), "listings/metadata/listings_0.json.gz"),
    ]
    selected = select_furniture_sample(rows, limit=3)
    assert len(selected) == 3
    assert {p.category for p in selected} == {"SOFA", "CHAIR"}


def test_archive_inspection_reads_real_tar_members(tmp_path: Path):
    path = tmp_path / "abo.tar"
    write_tar(path, [listing("B0001", "SOFA", "Sofa")])
    report = inspect_listings_archive(path)
    assert report["listing_shard_count"] == 1
    assert report["archive_sha256"]


def test_archive_with_wrong_layout_is_rejected(tmp_path: Path):
    path = tmp_path / "wrong.tar"
    with tarfile.open(path, "w"):
        pass
    with pytest.raises(AboDataError):
        inspect_listings_archive(path)


def test_image_index_rejects_path_traversal(tmp_path: Path):
    path = tmp_path / "images.csv.gz"
    with gzip.open(path, "wt", newline="") as out:
        out.write("image_id,height,width,path\n")
        out.write("ok,100,100,ab/image.jpg\n")
        out.write("bad,100,100,../../secret.jpg\n")
    index = load_image_index(path)
    assert "ok" in index and "bad" not in index
