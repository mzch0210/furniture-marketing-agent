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
