import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fma.app import create_app
from fma.catalog import LocalProductCatalog
from fma.marketing import (
    CampaignCreativeService, ProductNotFoundError, build_creative_package,
    validate_claim_provenance,
)
from fma.models import (
    CampaignCreativeRequest, CampaignObjective, CatalogAssetReference,
    CatalogProduct, CatalogProductFact, CreativeAngle, FactVerificationStatus,
    MarketingAudience,
)

SOURCE = "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/listings/metadata/listings_0.json.gz"


def sample_product() -> CatalogProduct:
    return CatalogProduct(
        id="abo:SKU-101", sku="SKU-101", name="Contemporary Sofa",
        brand="Example Brand", category="SOFA", description="Catalog-supplied description only.",
        marketplace="amazon.com", source_dataset="amazon-berkeley-objects",
        source_record_id="SKU-101", source_uri=SOURCE,
        source_shard="listings/metadata/listings_0.json.gz", raw_record_sha256="a" * 64,
        facts=[
            CatalogProductFact(key="product_name", value="Contemporary Sofa", source_dataset="amazon-berkeley-objects", source_record_id="SKU-101", source_uri=SOURCE, source_field="item_name"),
            CatalogProductFact(key="material", value="wood", source_dataset="amazon-berkeley-objects", source_record_id="SKU-101", source_uri=SOURCE, source_field="material"),
            CatalogProductFact(key="dimension_width", value={"value": 80, "unit": "inches"}, source_dataset="amazon-berkeley-objects", source_record_id="SKU-101", source_uri=SOURCE, source_field="item_dimensions.width"),
            CatalogProductFact(key="color", value="blue", source_dataset="amazon-berkeley-objects", source_record_id="SKU-101", source_uri=SOURCE, source_field="color", verification_status=FactVerificationStatus.UNVERIFIED),
        ],
        assets=[
            CatalogAssetReference(asset_id="abo:image:001", role="main_image", media_type="image/jpeg", source_dataset="amazon-berkeley-objects", source_record_id="SKU-101", source_reference="001", source_uri="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/images/small/ab/001.jpg")
        ],
    )


def write_catalog(root: Path) -> None:
    processed = root / "processed"
    processed.mkdir(parents=True)
    (processed / "products.json").write_text(json.dumps([sample_product().model_dump(mode="json")]), encoding="utf-8")
    manifest = {"dataset": {"name": "Amazon Berkeley Objects (ABO)"}, "license": {"license_id": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "attribution": "Data and images: Amazon.com."}, "attribution": "Data and images: Amazon.com."}
    (processed / "dataset-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def request(**overrides) -> CampaignCreativeRequest:
    values = {"sku": "SKU-101", "audience": MarketingAudience.B2B, "objective": CampaignObjective.LEAD_GENERATION, "angle": CreativeAngle.MATERIAL_SPOTLIGHT, "duration_seconds": 30}
    values.update(overrides)
    return CampaignCreativeRequest(**values)


def test_creative_schema_and_timing_are_valid() -> None:
    product = sample_product()
    package = build_creative_package(product, request(), {})
    assert package.brief.duration_seconds == 30
    assert package.storyboard[0].start_seconds == 0
    assert package.storyboard[-1].end_seconds == 30
    assert all(shot.end_seconds > shot.start_seconds for shot in package.storyboard)
    assert package.template_version
    validate_claim_provenance(package, product)


def test_b2b_and_b2c_generate_audience_appropriate_cta() -> None:
    product = sample_product()
    b2b = build_creative_package(product, request(), {})
    b2c = build_creative_package(product, request(audience=MarketingAudience.B2C, objective=CampaignObjective.PRODUCT_CONSIDERATION), {})
    assert "MOQ" in b2b.brief.primary_cta
    assert "seller" in b2c.brief.primary_cta


def test_unverified_fact_is_not_used_as_a_product_claim() -> None:
    product = sample_product()
    package = build_creative_package(product, request(angle=CreativeAngle.COLOR_SPOTLIGHT), {})
    assert "blue" not in package.script.full_voiceover.lower()
    assert not any(ref.fact_key == "color" for ref in package.claim_reference_index)
    assert any("No eligible source-backed color fact" in item for item in package.caveats)


def test_unknown_attribute_is_caveated_not_invented() -> None:
    product = sample_product()
    package = build_creative_package(product, request(angle=CreativeAngle.STYLE_SPOTLIGHT), {})
    assert "does not supply style details" in package.script.full_voiceover
    assert "style" in " ".join(package.caveats).lower()


def test_claim_reference_must_match_source_fact() -> None:
    product = sample_product()
    package = build_creative_package(product, request(), {})
    package.claim_reference_index[0].source_uri = "https://example.com/fake"
    with pytest.raises(ValueError, match="does not match"):
        validate_claim_provenance(package, product)


def test_storyboard_uses_short_ascii_friendly_screen_copy():
    package = build_creative_package(sample_product(), request(), {})
    assert package.storyboard[0].on_screen_text == "FURNITURE SPOTLIGHT"
    assert package.storyboard[1].on_screen_text == "Contemporary Sofa"
    assert package.storyboard[3].on_screen_text == "CATALOG DETAILS. VERIFY WITH SUPPLIER."
    assert package.storyboard[4].on_screen_text == "Explore the details"


def test_deterministic_generation_exports_files(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    write_catalog(root)
    result = CampaignCreativeService(LocalProductCatalog(root), output_dir=tmp_path / "exports").generate(request())
    names = {item.name for item in result.exports}
    assert {"creative-package.json", "script.md", "storyboard.md", "caption.txt", "subtitles.srt", "attribution.txt"} <= names
    for artifact in result.exports:
        assert Path(artifact.path).is_file()
        assert artifact.size_bytes > 0
    package_path = tmp_path / "exports" / result.package.brief.campaign_id / "SKU-101" / "creative-package.json"
    assert json.loads(package_path.read_text())["generation_mode"] == "deterministic_template"


def test_creative_service_rejects_missing_sku(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    write_catalog(root)
    service = CampaignCreativeService(LocalProductCatalog(root), tmp_path / "exports")
    with pytest.raises(ProductNotFoundError):
        service.generate(request(sku="DOES-NOT-EXIST"))


def test_generate_creative_api(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    write_catalog(root)
    client = TestClient(create_app(root, tmp_path / "exports"))
    response = client.post("/api/creative/generate", json={"sku": "SKU-101", "audience": "B2B", "objective": "lead_generation", "angle": "material_spotlight", "duration_seconds": 30})
    assert response.status_code == 200
    payload = response.json()
    assert payload["package"]["brief"]["sku"] == "SKU-101"
    assert payload["package"]["template_version"]
    assert len(payload["exports"]) == 6


def test_generate_creative_api_returns_404_for_unknown_sku(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    write_catalog(root)
    response = TestClient(create_app(root, tmp_path / "exports")).post("/api/creative/generate", json={"sku": "MISSING", "audience": "B2C", "objective": "brand_awareness"})
    assert response.status_code == 404
