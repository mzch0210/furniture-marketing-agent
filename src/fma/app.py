from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from .catalog import CatalogDataError, LocalProductCatalog
from .marketing import CampaignCreativeService, ProductNotFoundError
from .models import CampaignCreativeRequest

STATIC_PAGE = Path(__file__).parent / "static" / "catalog.html"


def create_app(
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Furniture Marketing Agent — Public Product Catalog",
        description="Local, read-only browser for source-traceable public furniture products.",
        version="0.1.0",
    )
    app.state.catalog = LocalProductCatalog(data_dir)
    app.state.creative_service = CampaignCreativeService(
        app.state.catalog,
        output_dir=output_dir or "data/outputs/creatives",
    )

    @app.get("/", include_in_schema=False)
    def catalog_home() -> FileResponse:
        if not STATIC_PAGE.is_file():
            raise HTTPException(status_code=500, detail="Catalog UI static page is missing.")
        return FileResponse(STATIC_PAGE, media_type="text/html")

    @app.get("/api/catalog/status")
    def catalog_status() -> dict:
        try:
            return app.state.catalog.status()
        except CatalogDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/catalog/products")
    def list_products(
        q: str = "",
        category: str | None = None,
        marketplace: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 24,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        try:
            return app.state.catalog.list_products(
                query=q,
                category=category,
                marketplace=marketplace,
                limit=limit,
                offset=offset,
            )
        except CatalogDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/catalog/products/{sku_or_id}")
    def get_product(sku_or_id: str) -> dict:
        try:
            product = app.state.catalog.get_product(sku_or_id)
            if product is None:
                raise HTTPException(status_code=404, detail="Product SKU not found.")
            return app.state.catalog.fact_sheet(product)
        except CatalogDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/creative/generate")
    def generate_creative(request: CampaignCreativeRequest) -> dict:
        try:
            result = app.state.creative_service.generate(request)
            return result.model_dump(mode="json")
        except ProductNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except CatalogDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/catalog/manifest")
    def get_manifest() -> dict:
        try:
            return app.state.catalog.load_manifest()
        except CatalogDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("fma.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    run()
