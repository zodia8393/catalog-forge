from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .models import CrawlRunCreate, CrawlRunSummary, ReviewResolution
from .storage import Store


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    store = Store(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.init_schema()
        yield

    app = FastAPI(
        title="CatalogForge API",
        version="0.1.0",
        description="Resilient commerce crawl control plane.",
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    async def require_api_key(x_api_key: str = Header(default="")) -> None:
        if x_api_key != app_settings.api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        store.metrics()
        return {"status": "ready"}

    @app.post("/api/v1/crawl-runs", response_model=CrawlRunSummary, status_code=201, dependencies=[Depends(require_api_key)])
    async def create_crawl_run(request: CrawlRunCreate) -> CrawlRunSummary:
        return store.create_run(request, max_attempts=app_settings.max_attempts)

    @app.get("/api/v1/crawl-runs", response_model=list[CrawlRunSummary])
    async def list_crawl_runs(limit: int = Query(default=50, ge=1, le=200)) -> list[CrawlRunSummary]:
        return store.list_runs(limit)

    @app.get("/api/v1/crawl-runs/{run_id}", response_model=CrawlRunSummary)
    async def get_crawl_run(run_id: UUID) -> CrawlRunSummary:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="crawl run not found")
        return run

    @app.get("/api/v1/products")
    async def list_products(
        source: str | None = None,
        min_confidence: float = Query(default=0.0, ge=0, le=1),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, object]]:
        return store.list_products(source=source, min_confidence=min_confidence, limit=limit)

    @app.get("/api/v1/sources")
    async def list_sources() -> list[dict[str, object]]:
        return store.source_health()

    @app.get("/api/v1/review-items")
    async def list_reviews(review_status: str = Query(default="pending", alias="status")) -> list[dict[str, object]]:
        return store.list_review_items(review_status)

    @app.post("/api/v1/review-items/{item_id}/resolve", dependencies=[Depends(require_api_key)])
    async def resolve_review(item_id: UUID, resolution: ReviewResolution) -> dict[str, bool]:
        if not store.resolve_review(item_id, resolution):
            raise HTTPException(status_code=404, detail="pending review item not found")
        return {"resolved": True}

    @app.get("/metrics", response_class=Response)
    async def metrics() -> Response:
        values = store.metrics()
        lines = ["# TYPE catalog_forge_targets gauge"]
        for key, value in sorted(values.items()):
            metric = (
                "catalog_forge_products"
                if key == "products"
                else "catalog_forge_fetch_attempts"
                if key == "attempts"
                else "catalog_forge_review_items"
                if key == "reviews_pending"
                else "catalog_forge_targets"
            )
            label = "" if key in {"products", "attempts", "reviews_pending"} else f'{{status="{key}"}}'
            lines.append(f"{metric}{label} {value}")
        return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("catalog_forge.api:app", host="0.0.0.0", port=8100, reload=False)


if __name__ == "__main__":
    main()
