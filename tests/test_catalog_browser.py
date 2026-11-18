import json
from pathlib import Path

from fastapi.testclient import TestClient

from fma.app import create_app
from fma.models import CatalogProduct, CatalogProductFact, CatalogAssetReference


def make_product(sku: str, name: str, category: str = "SOFA") -> dict:
    product = CatalogProduct(
        id="abo:" + sku,
        sku=sku,
        name=name,
        brand="Example Brand",
        category=category,
        description="Source-reported catalog bullet point.",
        marketplace="amazon.com",
        source_dataset="amazon-berkeley-objects",
        source_record_id=sku,
        source_uri="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/listings/metadata/listings_0.json.gz",
        source_shard="listings/metadata/listings_0.json.gz",
        raw_record_sha256="a" * 64,
        facts=[
            CatalogProductFact(
                key="brand",
                value="Example Brand",
                source_dataset="amazon-berkeley-objects",
                source_record_id=sku,
                source_uri="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/listings/metadata/listings_0.json.gz",
                source_field="brand",
            ),
            CatalogProductFact(
                key="dimension_width",
                value={"value": 87, "unit": "inches"},
                source_dataset="amazon-berkeley-objects",
                source_record_id=sku,
                source_uri="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/listings/metadata/listings_0.json.gz",
                source_field="item_dimensions.width",
            ),
        ],
        assets=[
            CatalogAssetReference(
                asset_id="abo:image:image001",
                role="main_image",
                media_type="image/jpeg",
                source_dataset="amazon-berkeley-objects",
                source_record_id=sku,
                source_reference="image001",
                source_uri="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/images/small/ab/image001.jpg",
                width=256,
                height=200,
            )
        ],
    )
    return product.model_dump(mode="json")


def write_catalog(root: Path, products: list[dict] | None = None) -> None:
    processed = root / "processed"
    processed.mkdir(parents=True)
    sample = products if products is not None else [
        make_product("SKU-1", "Modern Sofa"),
        make_product("SKU-2", "Dining Chair", "CHAIR"),
    ]
    (processed / "products.json").write_text(json.dumps(sample), encoding="utf-8")
    manifest = {
        "dataset": {
            "id": "amazon-berkeley-objects",
            "name": "Amazon Berkeley Objects (ABO)",
            "official_page": "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html",
        },
        "license": {
            "license_id": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "verification_status": "verified_from_official_license_file",
            "attribution": "Data and images: Amazon.com.",
            "third_party_rights_note": "Third-party rights may require separate review.",
        },
        "attribution": "Data and images: Amazon.com.",
        "paper_citation": "Collins et al. (2022), CVPR.",
    }
    (processed / "dataset-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_catalog_home_serves_browser_ui(tmp_path: Path) -> None:
    write_catalog(tmp_path)
    response = TestClient(create_app(tmp_path)).get("/")
    assert response.status_code == 200
    assert "Public Product Catalog" in response.text
    assert "Unknown attributes" in response.text


def test_product_search_and_category_filter(tmp_path: Path) -> None:
    write_catalog(tmp_path)
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/catalog/products", params={"q": "modern", "category": "SOFA"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["sku"] == "SKU-1"
    assert "CHAIR" in payload["categories"]


def test_fact_sheet_shows_source_facts_and_unknowns(tmp_path: Path) -> None:
    write_catalog(tmp_path)
    response = TestClient(create_app(tmp_path)).get("/api/catalog/products/SKU-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"]["facts"][0]["verification_status"] == "source_reported"
    assert payload["product"]["source_record_id"] == "SKU-1"
    unknown_keys = {item["key"] for item in payload["unknown_attributes"]}
    assert "material" in unknown_keys
    assert "dimension_height" in unknown_keys
    assert "dimension_width" not in unknown_keys


def test_manifest_endpoint_exposes_license_and_attribution(tmp_path: Path) -> None:
    write_catalog(tmp_path)
    response = TestClient(create_app(tmp_path)).get("/api/catalog/manifest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["license"]["license_id"] == "CC-BY-4.0"
    assert payload["attribution"] == "Data and images: Amazon.com."


def test_status_reports_local_sample_count(tmp_path: Path) -> None:
    write_catalog(tmp_path)
    response = TestClient(create_app(tmp_path)).get("/api/catalog/status")
    assert response.status_code == 200
    assert response.json()["product_count"] == 2


def test_missing_catalog_returns_actionable_service_error(tmp_path: Path) -> None:
    response = TestClient(create_app(tmp_path)).get("/api/catalog/products")
    assert response.status_code == 503
    assert "Import the ABO sample first" in response.json()["detail"]
