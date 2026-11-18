from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import CatalogProduct

DATASET_PAGE = "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html"

EXPECTED_ATTRIBUTES: tuple[tuple[str, str], ...] = (
    ("brand", "Brand"),
    ("product_type", "Product type"),
    ("color", "Color"),
    ("material", "Material"),
    ("fabric_type", "Fabric type"),
    ("finish_type", "Finish type"),
    ("pattern", "Pattern"),
    ("style", "Style"),
    ("dimension_width", "Width"),
    ("dimension_height", "Height"),
    ("dimension_length", "Length"),
    ("dimension_depth", "Depth"),
    ("item_weight", "Item weight"),
    ("model_number", "Model number"),
    ("model_name", "Model name"),
    ("model_year", "Model year"),
)


class CatalogDataError(RuntimeError):
    """Raised when the local public catalog is missing or malformed."""


class LocalProductCatalog:
    """Read-only browser over the normalized ABO sample and its provenance manifest."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        configured = data_dir or os.environ.get("FMA_ABO_DATA_DIR", "data/public/abo")
        self.data_dir = Path(configured)
        self.processed_dir = self.data_dir / "processed"
        self.products_path = self.processed_dir / "products.json"
        self.manifest_path = self.processed_dir / "dataset-manifest.json"

    def load_products(self) -> list[CatalogProduct]:
        if not self.products_path.is_file():
            raise CatalogDataError(
                f"Product catalog not found at {self.products_path}. "
                "Import the ABO sample first with: python -m fma.data_sources.abo"
            )
        try:
            payload = json.loads(self.products_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise CatalogDataError("products.json must contain a JSON array.")
            return [CatalogProduct.model_validate(item) for item in payload]
        except (OSError, json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise CatalogDataError(f"Unable to read the normalized product catalog: {exc}") from exc

    def load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            raise CatalogDataError(
                f"Dataset manifest not found at {self.manifest_path}. "
                "Re-import the ABO sample to generate dataset-manifest.json."
            )
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogDataError(f"Unable to read the dataset manifest: {exc}") from exc
        if not isinstance(payload, dict):
            raise CatalogDataError("dataset-manifest.json must contain a JSON object.")
        return payload

    def list_products(
        self,
        query: str = "",
        category: str | None = None,
        marketplace: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> dict[str, Any]:
        products = self.load_products()
        categories = sorted({product.category for product in products})
        marketplaces = sorted(
            {product.marketplace for product in products if product.marketplace}
        )

        filtered = products
        if category:
            filtered = [
                product for product in filtered
                if product.category.casefold() == category.casefold()
            ]
        if marketplace:
            filtered = [
                product for product in filtered
                if (product.marketplace or "").casefold() == marketplace.casefold()
            ]
        if query.strip():
            needle = query.strip().casefold()
            filtered = [
                product for product in filtered
                if needle in " ".join(
                    [
                        product.sku,
                        product.name,
                        product.brand or "",
                        product.category,
                        product.description or "",
                        product.marketplace or "",
                        " ".join(str(fact.value) for fact in product.facts),
                    ]
                ).casefold()
            ]

        filtered.sort(key=lambda product: (product.name.casefold(), product.sku.casefold()))
        total = len(filtered)
        page = filtered[offset : offset + limit]
        return {
            "items": [product.model_dump(mode="json") for product in page],
            "total": total,
            "limit": limit,
            "offset": offset,
            "categories": categories,
            "marketplaces": marketplaces,
        }

    def get_product(self, sku_or_id: str) -> CatalogProduct | None:
        for product in self.load_products():
            if product.sku == sku_or_id or product.id == sku_or_id:
                return product
        return None

    def fact_sheet(self, product: CatalogProduct) -> dict[str, Any]:
        manifest = self.load_manifest()
        present_keys = {fact.key for fact in product.facts}
        if product.brand:
            present_keys.add("brand")
        if any(key.startswith("item_weight_") for key in present_keys):
            present_keys.add("item_weight")

        unknown_attributes = [
            {"key": key, "label": label, "value": None, "status": "unknown"}
            for key, label in EXPECTED_ATTRIBUTES
            if key not in present_keys
        ]
        return {
            "product": product.model_dump(mode="json"),
            "unknown_attributes": unknown_attributes,
            "dataset": manifest.get("dataset", {}),
            "license": manifest.get("license", {}),
            "attribution": manifest.get("attribution")
            or manifest.get("license", {}).get("attribution", ""),
            "paper_citation": manifest.get("paper_citation", ""),
        }

    def status(self) -> dict[str, Any]:
        products = self.load_products()
        manifest = self.load_manifest()
        return {
            "ready": True,
            "product_count": len(products),
            "dataset_name": manifest.get("dataset", {}).get("name", "Unknown dataset"),
            "license_id": manifest.get("license", {}).get("license_id", "Unknown"),
            "license_verification_status": manifest.get("license", {}).get(
                "verification_status", "unknown"
            ),
        }
