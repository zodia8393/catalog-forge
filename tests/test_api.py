from pathlib import Path

import httpx
import pytest

from catalog_forge.api import create_app
from catalog_forge.config import Settings


def app_for(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'catalog.sqlite'}",
        api_key="test-key",
        allowed_hosts=["fixture"],
        allow_private_hosts=True,
    )
    app = create_app(settings)
    app.state.store.init_schema()
    return app


@pytest.mark.asyncio
async def test_crawl_run_api_requires_key_and_reports_queue(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api") as client:
        payload = {
            "connector": "generic",
            "start_urls": ["http://fixture/products/1", "http://fixture/products/2"],
            "max_pages": 2,
            "render_mode": "http",
        }
        assert (await client.post("/api/v1/crawl-runs", json=payload)).status_code == 401
        created = await client.post(
            "/api/v1/crawl-runs",
            json=payload,
            headers={"X-API-Key": "test-key"},
        )

        assert created.status_code == 201
        body = created.json()
        assert body["queued"] == 2
        assert body["status"] == "queued"

        fetched = await client.get(f"/api/v1/crawl-runs/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["queued"] == 2


@pytest.mark.asyncio
async def test_health_metrics_and_empty_surfaces(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api") as client:
        assert (await client.get("/health/live")).json() == {"status": "ok"}
        assert (await client.get("/health/ready")).json() == {"status": "ready"}
        assert (await client.get("/api/v1/products")).json() == []
        assert (await client.get("/api/v1/review-items")).json() == []
        metrics = await client.get("/metrics")
        assert metrics.status_code == 200
        assert "catalog_forge_products 0" in metrics.text
