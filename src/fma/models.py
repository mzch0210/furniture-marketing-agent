from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProductFact(BaseModel):
    key: str
    value: Any
    source: str
    verified: bool = False


class ProductBrief(BaseModel):
    sku: str
    product_name: str
    audience: list[str] = Field(default_factory=list)
    facts: list[ProductFact] = Field(default_factory=list)
    approved: bool = False


class VideoBrief(BaseModel):
    objective: str
    audience: str
    angle: str
    hook: str
    cta: str
    duration_seconds: int = Field(default=26, ge=20, le=60)
    aspect_ratio: str = "9:16"


class PipelineState(BaseModel):
    campaign_id: str
    sku: str
    status: str
    product_brief: ProductBrief | None = None
    video_brief: VideoBrief | None = None
    artifacts: list[str] = Field(default_factory=list)


class FactVerificationStatus(str, Enum):
    SOURCE_REPORTED = "source_reported"
    UNVERIFIED = "unverified"
    FACTORY_VERIFIED = "factory_verified"
    REJECTED = "rejected"


class CatalogProductFact(BaseModel):
    """A source-backed product attribute; source-reported is not factory-verified."""

    key: str
    value: Any
    source_dataset: str
    source_record_id: str
    source_uri: str
    source_field: str
    source_language: str | None = None
    unit: str | None = None
    raw_value: Any = None
    verification_status: FactVerificationStatus = FactVerificationStatus.SOURCE_REPORTED


class CatalogAssetReference(BaseModel):
    asset_id: str
    role: str
    media_type: str
    source_dataset: str
    source_record_id: str
    source_reference: str
    source_path: str | None = None
    source_uri: str | None = None
    license_id: str = "CC-BY-4.0"
    width: int | None = None
    height: int | None = None


class CatalogProduct(BaseModel):
    """Normalized catalog product shared by public and future enterprise adapters."""

    id: str
    sku: str
    name: str
    brand: str | None = None
    category: str
    description: str | None = None
    marketplace: str | None = None
    source_dataset: str
    source_record_id: str
    source_uri: str
    source_shard: str
    raw_record_sha256: str
    facts: list[CatalogProductFact] = Field(default_factory=list)
    assets: list[CatalogAssetReference] = Field(default_factory=list)
