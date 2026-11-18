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


class MarketingAudience(str, Enum):
    B2B = "B2B"
    B2C = "B2C"


class CampaignObjective(str, Enum):
    BRAND_AWARENESS = "brand_awareness"
    PRODUCT_CONSIDERATION = "product_consideration"
    LEAD_GENERATION = "lead_generation"
    TRAFFIC = "traffic"


class CreativeAngle(str, Enum):
    PRODUCT_OVERVIEW = "product_overview"
    COLOR_SPOTLIGHT = "color_spotlight"
    MATERIAL_SPOTLIGHT = "material_spotlight"
    DIMENSION_SPOTLIGHT = "dimension_spotlight"
    BRAND_SPOTLIGHT = "brand_spotlight"
    STYLE_SPOTLIGHT = "style_spotlight"


class CampaignCreativeRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=256)
    audience: MarketingAudience
    objective: CampaignObjective
    angle: CreativeAngle = CreativeAngle.PRODUCT_OVERVIEW
    target_market: str = Field(default="United States", min_length=2, max_length=100)
    platform: str = Field(default="TikTok", min_length=2, max_length=40)
    language: str = Field(default="en-US", min_length=2, max_length=20)
    duration_seconds: int = Field(default=30, ge=15, le=60)
    campaign_id: str | None = Field(default=None, max_length=120)


class ProductClaimReference(BaseModel):
    fact_key: str
    value: Any
    source_dataset: str
    source_record_id: str
    source_uri: str
    source_field: str
    verification_status: FactVerificationStatus


class CreativeBrief(BaseModel):
    campaign_id: str
    sku: str
    product_name: str
    audience: MarketingAudience
    objective: CampaignObjective
    angle: CreativeAngle
    target_market: str
    platform: str
    language: str
    duration_seconds: int = Field(ge=15, le=60)
    message_strategy: str
    primary_cta: str
    research_note: str
    approval_required: bool = True


class CreativeScriptSegment(BaseModel):
    segment_id: str
    role: str
    start_seconds: int = Field(ge=0)
    end_seconds: int = Field(gt=0)
    voiceover: str
    on_screen_text: str
    fact_refs: list[ProductClaimReference] = Field(default_factory=list)


class CreativeScript(BaseModel):
    hook: str
    segments: list[CreativeScriptSegment]
    full_voiceover: str
    on_screen_copy: list[str] = Field(default_factory=list)


class StoryboardShot(BaseModel):
    shot_number: int = Field(ge=1)
    start_seconds: int = Field(ge=0)
    end_seconds: int = Field(gt=0)
    purpose: str
    visual_direction: str
    candidate_asset_ids: list[str] = Field(default_factory=list)
    asset_match_status: str
    source_fact_refs: list[ProductClaimReference] = Field(default_factory=list)
    on_screen_text: str
    voiceover: str
    transition: str
    production_note: str


class CreativePackage(BaseModel):
    template_version: str
    generation_mode: str
    publication_status: str
    brief: CreativeBrief
    script: CreativeScript
    storyboard: list[StoryboardShot]
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    claim_reference_index: list[ProductClaimReference] = Field(default_factory=list)
    caption_fact_refs: list[ProductClaimReference] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    source_dataset: str
    source_record_id: str
    source_uri: str
    dataset_name: str
    attribution: str
    license_id: str
    license_url: str
    candidate_asset_ids: list[str] = Field(default_factory=list)


class CreativeExportArtifact(BaseModel):
    name: str
    path: str
    size_bytes: int = Field(ge=0)


class CreativeGenerationResult(BaseModel):
    package: CreativePackage
    exports: list[CreativeExportArtifact] = Field(default_factory=list)


class MatchedMediaAsset(BaseModel):
    asset_id: str
    role: str
    media_type: str
    source_dataset: str
    source_record_id: str
    source_uri: str
    downloaded_uri: str
    local_path: str
    sha256: str
    size_bytes: int = Field(ge=0)
    source_variant: str
    license_id: str
    width: int | None = None
    height: int | None = None


class EditDecisionShot(BaseModel):
    shot_number: int = Field(ge=1)
    start_seconds: int = Field(ge=0)
    end_seconds: int = Field(gt=0)
    visual_type: str
    match_status: str
    asset_id: str | None = None
    local_asset_path: str | None = None
    source_uri: str | None = None
    source_fact_refs: list[ProductClaimReference] = Field(default_factory=list)
    on_screen_text: str
    voiceover: str
    transition: str = "clean_cut"
    reshoot_required: bool = False
    reshoot_note: str | None = None


class EditDecisionList(BaseModel):
    edl_version: str = "fma-edl-v1.0.0"
    campaign_id: str
    sku: str
    duration_seconds: int = Field(ge=1)
    width: int = Field(default=1080, gt=0)
    height: int = Field(default=1920, gt=0)
    fps: int = Field(default=30, gt=0)
    container: str = "mp4"
    video_codec: str = "h264"
    audio_policy: str = "silent_no_unlicensed_music"
    media_basis: str
    shots: list[EditDecisionShot]
    assets: list[MatchedMediaAsset] = Field(default_factory=list)
    source_dataset: str
    source_record_id: str
    attribution: str
    license_id: str
    license_url: str
    rights_review_required: bool = False
    warnings: list[str] = Field(default_factory=list)


class VideoRenderReport(BaseModel):
    status: str
    output_path: str
    file_size_bytes: int = Field(ge=0)
    sha256: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None = None
    ffmpeg_version: str
    rendered_at: str


class VideoProductionResult(BaseModel):
    package: CreativePackage
    edl: EditDecisionList
    render_report: VideoRenderReport
    exports: list[CreativeExportArtifact] = Field(default_factory=list)
