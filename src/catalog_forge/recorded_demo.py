from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from .config import Settings
from .fetcher import HttpFetcher
from .fixture_app import _attempts, app
from .models import CrawlRunCreate, CrawlRunSummary
from .public_demo import BooksDemoExecution, execute_books_demo
from .queueing import InMemoryQueue, OutboxPublisher
from .rehearsal import RehearsalExecution, execute_rehearsal
from .service import TargetProcessor
from .storage import Store


GENERATOR_MODULE = "catalog_forge.recorded_demo"
REQUIRED_FIELDS = ("title", "price_amount", "currency", "availability")


@dataclass(slots=True)
class DriftDemoExecution:
    report: dict[str, Any]
    run: CrawlRunSummary
    products: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    sample_response: dict[str, Any] = field(default_factory=dict)


async def execute_drift_demo() -> DriftDemoExecution:
    _attempts.clear()
    settings = Settings(
        database_url="sqlite:///:memory:",
        allowed_hosts=["fixture"],
        private_host_allowlist=["fixture"],
        min_host_interval_ms=0,
        max_concurrency_per_host=1,
        max_attempts=3,
    )
    store = Store(settings.database_url)
    store.init_schema()
    urls = [
        "http://fixture/products/90",
        "http://fixture/products/91?variant=drift",
    ]
    run = store.create_run(
        CrawlRunCreate(
            connector="fixture_drift",
            start_urls=urls,
            max_pages=len(urls),
            render_mode="http",
        ),
        max_attempts=settings.max_attempts,
    )
    queue = InMemoryQueue()
    publisher = OutboxPublisher(store, queue)
    while await publisher.publish_due():
        pass

    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture")
    fetcher = HttpFetcher(
        client=client,
        allowed_hosts=["fixture"],
        private_host_allowlist=["fixture"],
        max_concurrency_per_host=1,
        min_host_interval_seconds=0,
        enforce_robots=True,
    )
    processor = TargetProcessor(store, fetcher, settings)
    started = time.perf_counter()
    try:
        for _ in urls:
            batch = await queue.read("drift-demo", count=1, block_ms=10)
            if len(batch) != 1:
                raise RuntimeError("drift demo queue ended before both targets were processed")
            result = await processor.process(batch[0].payload)
            await queue.ack(batch[0].message_id)
            if result != "succeeded":
                raise RuntimeError(f"unexpected drift demo result: {result}")

        summary = store.get_run(run.id)
        if summary is None:
            raise RuntimeError("drift demo run disappeared")
        products = store.list_products(source="fixture_drift", limit=2)
        drift_product = next(
            (row for row in products if row["title"] == "Reliable Product 91"),
            None,
        )
        if drift_product is None:
            raise RuntimeError("drift product could not be found")
        reviews = store.list_review_items(limit=10)
        review = next(
            (row for row in reviews if row["product_id"] == drift_product["id"]),
            None,
        )
        if review is None or review["reason"] != "schema_drift":
            raise RuntimeError("schema drift review was not created")
        attempts = store.list_fetch_attempts(
            target_id=UUID(drift_product["target_id"]),
            limit=settings.max_attempts,
        )
        response = await client.get("/products/91?variant=drift")
        response.raise_for_status()
        metrics = store.metrics()
        report = {
            "run_id": str(run.id),
            "targets": len(urls),
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "blocked": summary.blocked,
            "fetch_attempts": metrics["attempts"],
            "product_snapshots": metrics["products"],
            "reviews_pending": metrics["reviews_pending"],
            "review_reason": review["reason"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        return DriftDemoExecution(
            report=report,
            run=summary,
            products=products,
            attempts=attempts,
            reviews=reviews,
            sample_response={
                "url": str(response.url),
                "status_code": response.status_code,
                "html": response.text,
                "bytes_received": len(response.content),
            },
        )
    finally:
        await client.aclose()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _html_excerpt(html: str, selectors: tuple[str, ...]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    fragments: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            rendered = str(node)
            if rendered not in fragments:
                fragments.append(rendered)
    return "\n".join(fragments)


def _evidence(product: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = product["field_evidence"]
    return [
        {
            "field": field,
            "value": str(evidence[field]["value"]),
            "method": evidence[field]["source"],
            "selector": evidence[field].get("selector"),
            "confidence": evidence[field]["confidence"],
        }
        for field in REQUIRED_FIELDS
    ]


def _product_output(
    product: dict[str, Any],
    *,
    attempts: list[dict[str, Any]],
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = dict(product)
    output.update(
        required_field_coverage=(
            sum(output.get(field) not in (None, "") for field in REQUIRED_FIELDS)
            / len(REQUIRED_FIELDS)
        ),
        fetch_attempts=len(attempts),
        review_required=review is not None,
    )
    if review is not None:
        output["review_id"] = review["id"]
        output["review_reason"] = review["reason"]
        output["review_status"] = review["status"]
    return output


def _run(run: CrawlRunSummary) -> dict[str, Any]:
    return run.model_dump(mode="json")


def _execution(
    *,
    run: CrawlRunSummary,
    environment: str,
    attempts: list[dict[str, Any]],
    response: dict[str, Any],
) -> dict[str, Any]:
    return {
        "actual_run": True,
        "run_id": str(run.id),
        "run_created_at": run.created_at.isoformat(),
        "environment": environment,
        "request_statuses": [attempt["status_code"] for attempt in attempts],
        "attempt_ids": [attempt["id"] for attempt in attempts],
        "response_status": response["status_code"],
        "response_bytes": response["bytes_received"],
        "response_sha256": _sha256(response["html"]),
    }


def build_recorded_dataset(
    *,
    recovery: RehearsalExecution,
    public: BooksDemoExecution,
    drift: DriftDemoExecution,
    command: str,
) -> dict[str, Any]:
    normal_product, recovered_product = recovery.products
    public_product = public.products[0]
    drift_product = next(product for product in drift.products if product["target_id"] == drift.attempts[0]["target_id"])
    drift_review = next(review for review in drift.reviews if review["product_id"] == drift_product["id"])

    normal_attempts = recovery.attempts["normal"]
    recovered_attempts = recovery.attempts["recovered"]
    public_attempts = public.attempts
    generated_at = datetime.now(timezone.utc).isoformat()
    all_runs = [recovery.run, public.run, drift.run]
    selected_products = [
        _product_output(normal_product, attempts=normal_attempts),
        _product_output(public_product, attempts=public_attempts),
        _product_output(drift_product, attempts=drift.attempts, review=drift_review),
        _product_output(recovered_product, attempts=recovered_attempts),
    ]
    required_present = sum(
        product.get(field) not in (None, "")
        for product in selected_products
        for field in REQUIRED_FIELDS
    )
    total_targets = sum(
        run.queued + run.running + run.retrying + run.succeeded + run.failed + run.blocked
        for run in all_runs
    )
    total_succeeded = sum(run.succeeded for run in all_runs)
    total_attempts = (
        recovery.report["fetch_attempts"]
        + public.report["fetch_attempts"]
        + drift.report["fetch_attempts"]
    )

    public_html = public.sample_response["html"]
    public_excerpt = _html_excerpt(
        public_html,
        (
            ".product_main",
            "table.table-striped tr:nth-of-type(1)",
            "table.table-striped tr:nth-of-type(2)",
            "table.table-striped tr:nth-of-type(4)",
            "table.table-striped tr:nth-of-type(6)",
        ),
    )
    recovered_html = recovery.html_samples["recovered"]["html"]
    recovered_flow = json.dumps(
        [
            {
                "attempt": attempt["attempt"],
                "status_code": attempt["status_code"],
                "error_code": attempt["error_code"],
                "retry_after_seconds": attempt["retry_after_seconds"],
                "created_at": attempt["created_at"],
            }
            for attempt in recovered_attempts
        ],
        ensure_ascii=False,
        indent=2,
    )
    recovered_excerpt = _html_excerpt(
        recovered_html,
        ('link[rel="canonical"]', 'script[type="application/ld+json"]'),
    )
    drift_html = drift.sample_response["html"]
    drift_excerpt = _html_excerpt(
        drift_html,
        ('meta[property="og:title"]', 'link[rel="canonical"]', "main.redesigned-card"),
    )

    sources = [
        {
            "source": "fixture_chaos",
            "label": "장애 복구 테스트",
            "description": "실제 ASGI 요청에 429와 작업자 중단을 주입",
            "run_id": str(recovery.run.id),
            "targets": recovery.report["targets"],
            "succeeded": recovery.report["succeeded"],
            "reviews_pending": 0,
        },
        {
            "source": "books_to_scrape",
            "label": "Books to Scrape",
            "description": "robots.txt를 준수한 공개 sandbox 실제 HTTP 수집",
            "run_id": str(public.run.id),
            "targets": public.report["discovered_product_urls"],
            "succeeded": public.report["succeeded"],
            "reviews_pending": 0,
        },
        {
            "source": "fixture_drift",
            "label": "구조 변경 테스트",
            "description": "baseline 다음에 변경 HTML을 실제 처리",
            "run_id": str(drift.run.id),
            "targets": drift.report["targets"],
            "succeeded": drift.report["succeeded"],
            "reviews_pending": drift.report["reviews_pending"],
        },
    ]

    cases = [
        {
            "id": "public-selector",
            "label": "공개 사이트 실제 수집",
            "short_description": "공개 HTML을 요청하고 site selector로 구조화",
            "description": "Books to Scrape에 실제 HTTP 요청을 보내 발견한 상품 20개 중 첫 상품의 수집·파싱·저장 기록입니다.",
            "kind": "외부 네트워크 실제 실행",
            "tone": "good",
            "execution": _execution(
                run=public.run,
                environment="external_network",
                attempts=public_attempts,
                response=public.sample_response,
            ),
            "input": {
                "source_label": "Books to Scrape · 실제 응답 일부",
                "url": public.sample_response["url"],
                "format": "HTTP 200 HTML excerpt",
                "raw": public_excerpt,
            },
            "steps": [
                {"title": "목록 실제 요청", "detail": f"목록 {public.report['listing_pages']}페이지에서 상품 URL {public.report['discovered_product_urls']}개 발견"},
                {"title": "상품 실제 요청", "detail": f"pipeline attempt가 HTTP {public_attempts[0]['status_code']}으로 완료"},
                {"title": "필드 추출", "detail": "사이트 selector로 제목·가격·통화·재고를 구조화"},
                {"title": "멱등 저장", "detail": f"실제 product ID {public_product['id']}로 snapshot 저장"},
            ],
            "decision": {
                "status": "stored",
                "label": "실제 저장 완료",
                "reason": "필수 필드 4개가 모두 있고 신뢰도 기준을 통과했습니다.",
            },
            "output": _product_output(public_product, attempts=public_attempts),
            "evidence": _evidence(public_product),
        },
        {
            "id": "retry-recovery",
            "label": "429 오류 실제 복구",
            "short_description": "429를 받은 실제 attempt를 재시도해 한 번만 저장",
            "description": "로컬 ASGI fixture가 첫 요청에 429를 반환하고 두 번째 요청에 200을 반환하도록 실행한 1,000건 장애 복구 run의 실제 기록입니다.",
            "kind": "로컬 장애 주입 실제 실행",
            "tone": "warn",
            "execution": _execution(
                run=recovery.run,
                environment="local_asgi_fault_injection",
                attempts=recovered_attempts,
                response=recovery.html_samples["recovered"],
            ),
            "input": {
                "source_label": "CatalogForge unstable fixture · 실제 attempt",
                "url": recovery.html_samples["recovered"]["url"],
                "format": "DB attempt 기록 + 실제 HTTP 200 HTML",
                "raw": recovered_flow + "\n\n[successful response excerpt]\n" + recovered_excerpt,
            },
            "steps": [
                {"title": "첫 요청 실패", "detail": f"실제 attempt {recovered_attempts[0]['attempt']}에 HTTP {recovered_attempts[0]['status_code']} 기록"},
                {"title": "재시도 발행", "detail": "Retry-After와 backoff 정책으로 outbox message 재발행"},
                {"title": "두 번째 요청 성공", "detail": f"실제 attempt {recovered_attempts[-1]['attempt']}에 HTTP {recovered_attempts[-1]['status_code']} 기록"},
                {"title": "멱등 저장", "detail": f"target ID {recovered_product['target_id']}에 snapshot 1건 저장"},
            ],
            "decision": {
                "status": "stored",
                "label": "복구 후 실제 저장",
                "reason": "429 이후 재시도에 성공했고 동일 target의 snapshot이 한 건입니다.",
            },
            "output": _product_output(recovered_product, attempts=recovered_attempts),
            "evidence": _evidence(recovered_product),
        },
        {
            "id": "schema-drift",
            "label": "구조 변경 실제 감지",
            "short_description": "baseline과 다른 HTML을 처리해 review 생성",
            "description": "같은 source에서 baseline 문서를 먼저 저장한 뒤 변경된 HTML을 실제 처리하여 schema_drift 검수 항목을 만든 기록입니다.",
            "kind": "로컬 drift 주입 실제 실행",
            "tone": "review",
            "execution": _execution(
                run=drift.run,
                environment="local_asgi_drift_injection",
                attempts=drift.attempts,
                response=drift.sample_response,
            ),
            "input": {
                "source_label": "CatalogForge drift fixture · 실제 응답 일부",
                "url": drift.sample_response["url"],
                "format": "HTTP 200 changed HTML excerpt",
                "raw": drift_excerpt,
            },
            "steps": [
                {"title": "baseline 저장", "detail": "JSON-LD 문서를 먼저 처리해 source fingerprint 기준 생성"},
                {"title": "변경 문서 요청", "detail": f"실제 changed HTML 요청이 HTTP {drift.attempts[0]['status_code']}으로 완료"},
                {"title": "fallback 추출", "detail": "Open Graph와 semantic metadata로 필수 필드 4개 복구"},
                {"title": "검수 항목 생성", "detail": f"실제 review ID {drift_review['id']}를 schema_drift로 저장"},
            ],
            "decision": {
                "status": "review",
                "label": "사람 검수 대기",
                "reason": "문서 fingerprint가 바뀌고 confidence가 기준보다 낮아 자동 승인하지 않았습니다.",
            },
            "output": _product_output(drift_product, attempts=drift.attempts, review=drift_review),
            "evidence": _evidence(drift_product),
        },
    ]

    return {
        "dataset": "CatalogForge 실제 실행 snapshot",
        "version": "2.0",
        "generated_at": generated_at,
        "generator_command": command,
        "execution_mode": "recorded_actual_runs",
        "notice": "외부 sandbox 수집 1회와 로컬 장애·구조 변경 주입 run을 실제 실행해 생성한 읽기 전용 기록입니다.",
        "metrics": {
            "targets": total_targets,
            "succeeded": total_succeeded,
            "success_rate": round(total_succeeded / total_targets, 4),
            "fetch_attempts": total_attempts,
            "transient_failures": recovery.report["injected_transient_failures"],
            "transient_failures_recovered": recovery.report["transient_failures_recovered"],
            "stale_messages_reclaimed": recovery.report["stale_messages_reclaimed"],
            "lost_snapshots": recovery.report["lost_snapshots"],
            "duplicate_snapshots": recovery.report["duplicate_snapshots"],
            "reviews_pending": drift.report["reviews_pending"],
            "required_fields_present": required_present,
            "required_fields_expected": len(selected_products) * len(REQUIRED_FIELDS),
        },
        "sources": sources,
        "runs": [_run(run) for run in all_runs],
        "products": selected_products,
        "timeline": [
            {"time": "1단계", "event": "장애 복구 run 생성", "detail": f"실제 run {recovery.run.id} · 대상 {recovery.report['targets']}개"},
            {"time": "2단계", "event": "429 응답과 재시도", "detail": f"실제 429 {recovery.report['injected_transient_failures']}건을 모두 복구"},
            {"time": "3단계", "event": "중단 메시지 회수", "detail": f"pending message {recovery.report['stale_messages_reclaimed']}건을 다른 worker로 회수"},
            {"time": "4단계", "event": "공개 sandbox 수집", "detail": f"실제 run {public.run.id} · {public.report['succeeded']}건 저장"},
            {"time": "5단계", "event": "구조 변경 검수 분리", "detail": f"실제 review {drift_review['id']} · 유실 0 · 중복 0"},
        ],
        "cases": cases,
    }


async def generate_recorded_dataset(
    *,
    public_products: int,
    recovery_targets: int,
    command: str,
) -> dict[str, Any]:
    if public_products < 1:
        raise ValueError("public_products must be at least 1")
    if recovery_targets < 120:
        raise ValueError("recovery_targets must be at least 120 so the recorded retry sample is stable")
    recovery = await execute_rehearsal(recovery_targets, capture=True)
    public = await execute_books_demo(public_products, capture=True)
    drift = await execute_drift_demo()
    return build_recorded_dataset(
        recovery=recovery,
        public=public,
        drift=drift,
        command=command,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the live demo dataset from actual pipeline runs")
    parser.add_argument("--public-products", type=int, default=20)
    parser.add_argument("--recovery-targets", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("web/public/sample-products.json"))
    args = parser.parse_args()
    command = (
        f"PYTHONPATH=src python3 -m {GENERATOR_MODULE} "
        f"--public-products {args.public_products} "
        f"--recovery-targets {args.recovery_targets} "
        f"--output {args.output.as_posix()}"
    )
    dataset = asyncio.run(
        generate_recorded_dataset(
            public_products=args.public_products,
            recovery_targets=args.recovery_targets,
            command=command,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "generated_at": dataset["generated_at"],
                "run_ids": [run["id"] for run in dataset["runs"]],
                "metrics": dataset["metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
