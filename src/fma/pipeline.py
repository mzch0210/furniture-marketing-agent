from __future__ import annotations

from dataclasses import dataclass

from .models import PipelineState


@dataclass
class PipelineResult:
    state: PipelineState
    next_action: str


class MarketingVideoPipeline:
    """Deterministic MVP orchestration shell.

    The production implementation will connect the Agent adapters, asset
    analysis, FFmpeg rendering, quality checks, and human approval gates.
    """

    APPROVAL_GATES = (
        "product_fact_review",
        "creative_review",
        "final_video_review",
    )

    def start(self, campaign_id: str, sku: str) -> PipelineResult:
        state = PipelineState(
            campaign_id=campaign_id,
            sku=sku,
            status="product_intake",
        )
        return PipelineResult(state=state, next_action="collect_product_facts")
