from fma.pipeline import MarketingVideoPipeline


def test_pipeline_starts_at_product_intake() -> None:
    result = MarketingVideoPipeline().start("campaign-001", "SOFA-BED-001")

    assert result.state.status == "product_intake"
    assert result.state.sku == "SOFA-BED-001"
    assert result.next_action == "collect_product_facts"


def test_human_approval_gates_are_explicit() -> None:
    assert MarketingVideoPipeline.APPROVAL_GATES == (
        "product_fact_review",
        "creative_review",
        "final_video_review",
    )
