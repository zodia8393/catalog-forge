from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    case,
    create_engine,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine, RowMapping

from .models import (
    CrawlRunCreate,
    CrawlRunSummary,
    CrawlStatus,
    FetchAttemptRecord,
    ProductRecord,
    ReviewResolution,
    TargetMessage,
    utc_now,
)


metadata = MetaData()

crawl_runs = Table(
    "crawl_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("connector", String(80), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("render_mode", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

crawl_targets = Table(
    "crawl_targets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("run_id", String(36), ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("url", Text, nullable=False),
    Column("normalized_url", Text, nullable=False),
    Column("connector", String(80), nullable=False),
    Column("render_mode", String(20), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("max_attempts", Integer, nullable=False),
    Column("error_code", String(80)),
    Column("next_attempt_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("run_id", "normalized_url", name="uq_target_run_url"),
)

fetch_attempts = Table(
    "fetch_attempts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("target_id", String(36), ForeignKey("crawl_targets.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("attempt", Integer, nullable=False),
    Column("status_code", Integer),
    Column("latency_ms", Float, nullable=False),
    Column("bytes_received", Integer, nullable=False),
    Column("error_code", String(80)),
    Column("retry_after_seconds", Float),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("target_id", "attempt", name="uq_attempt_target_number"),
)

products = Table(
    "products",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("run_id", String(36), ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("target_id", String(36), ForeignKey("crawl_targets.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("source", String(80), nullable=False, index=True),
    Column("external_id", Text, nullable=False),
    Column("canonical_url", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("price_amount", String(40)),
    Column("currency", String(8)),
    Column("availability", String(120)),
    Column("brand", String(200)),
    Column("category", String(200)),
    Column("image_url", Text),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("dom_fingerprint", String(32), nullable=False),
    Column("field_evidence", JSON, nullable=False),
    UniqueConstraint("source", "external_id", "captured_at", name="uq_product_snapshot"),
)

review_items = Table(
    "review_items",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("product_id", String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("status", String(20), nullable=False, index=True),
    Column("reason", String(120), nullable=False),
    Column("note", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("resolved_at", DateTime(timezone=True)),
)

source_profiles = Table(
    "source_profiles",
    metadata,
    Column("source", String(80), primary_key=True),
    Column("dom_fingerprint", String(32), nullable=False),
    Column("baseline_coverage", Float, nullable=False),
    Column("observed_count", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

drift_events = Table(
    "drift_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("source", String(80), nullable=False, index=True),
    Column("target_id", String(36), ForeignKey("crawl_targets.id", ondelete="CASCADE"), nullable=False),
    Column("previous_fingerprint", String(32), nullable=False),
    Column("new_fingerprint", String(32), nullable=False),
    Column("coverage", Float, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("detected_at", DateTime(timezone=True), nullable=False),
)

outbox = Table(
    "outbox",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("target_id", String(36), ForeignKey("crawl_targets.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("payload", JSON, nullable=False),
    Column("available_at", DateTime(timezone=True), nullable=False, index=True),
    Column("published_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _utc() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, database_url: str):
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    def init_schema(self) -> None:
        metadata.create_all(self.engine)

    def create_run(self, request: CrawlRunCreate, *, max_attempts: int) -> CrawlRunSummary:
        run_id = uuid4()
        now = _utc()
        with self.engine.begin() as connection:
            connection.execute(
                insert(crawl_runs).values(
                    id=str(run_id),
                    connector=request.connector,
                    status=CrawlStatus.QUEUED,
                    render_mode=request.render_mode,
                    created_at=now,
                    updated_at=now,
                )
            )
            for raw_url in request.start_urls[: request.max_pages]:
                url = str(raw_url)
                target_id = uuid4()
                message = TargetMessage(
                    target_id=target_id,
                    run_id=run_id,
                    url=url,
                    connector=request.connector,
                    render_mode=request.render_mode,
                )
                connection.execute(
                    insert(crawl_targets).values(
                        id=str(target_id),
                        run_id=str(run_id),
                        url=url,
                        normalized_url=_normalize_url(url),
                        connector=request.connector,
                        render_mode=request.render_mode,
                        status=CrawlStatus.QUEUED,
                        attempts=0,
                        max_attempts=max_attempts,
                        created_at=now,
                        updated_at=now,
                    )
                )
                self._insert_outbox(connection, message, available_at=now)
        summary = self.get_run(run_id)
        if summary is None:
            raise RuntimeError("created run could not be read")
        return summary

    def list_runs(self, limit: int = 50) -> list[CrawlRunSummary]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(crawl_runs.c.id).order_by(crawl_runs.c.created_at.desc()).limit(limit)
            ).scalars()
            return [summary for value in rows if (summary := self.get_run(UUID(value))) is not None]

    def get_run(self, run_id: UUID) -> CrawlRunSummary | None:
        with self.engine.connect() as connection:
            run = connection.execute(
                select(crawl_runs).where(crawl_runs.c.id == str(run_id))
            ).mappings().first()
            if run is None:
                return None
            counts = dict(
                connection.execute(
                    select(crawl_targets.c.status, func.count())
                    .where(crawl_targets.c.run_id == str(run_id))
                    .group_by(crawl_targets.c.status)
                ).all()
            )
        return CrawlRunSummary(
            id=UUID(run["id"]),
            connector=run["connector"],
            status=CrawlStatus(run["status"]),
            created_at=_aware(run["created_at"]),
            updated_at=_aware(run["updated_at"]),
            **{status.value: int(counts.get(status.value, 0)) for status in CrawlStatus},
        )

    def get_target(self, target_id: UUID) -> TargetMessage | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(crawl_targets).where(crawl_targets.c.id == str(target_id))
            ).mappings().first()
        if row is None:
            return None
        return TargetMessage(
            target_id=UUID(row["id"]),
            run_id=UUID(row["run_id"]),
            url=row["url"],
            connector=row["connector"],
            render_mode=row["render_mode"],
            attempt=row["attempts"],
        )

    def mark_started(self, target_id: UUID) -> int | None:
        now = _utc()
        with self.engine.begin() as connection:
            row = connection.execute(
                select(crawl_targets).where(crawl_targets.c.id == str(target_id))
            ).mappings().first()
            if row is None or row["status"] in {CrawlStatus.SUCCEEDED, CrawlStatus.BLOCKED}:
                return None
            attempt = int(row["attempts"]) + 1
            connection.execute(
                update(crawl_targets)
                .where(crawl_targets.c.id == str(target_id))
                .values(status=CrawlStatus.RUNNING, attempts=attempt, updated_at=now, error_code=None)
            )
            connection.execute(
                update(crawl_runs)
                .where(crawl_runs.c.id == row["run_id"])
                .values(status=CrawlStatus.RUNNING, updated_at=now)
            )
            return attempt

    def record_attempt(self, attempt: FetchAttemptRecord) -> None:
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(fetch_attempts.c.id).where(
                    and_(
                        fetch_attempts.c.target_id == str(attempt.target_id),
                        fetch_attempts.c.attempt == attempt.attempt,
                    )
                )
            ).scalar_one_or_none()
            values = attempt.model_dump(mode="json")
            values["id"] = str(uuid4())
            values["target_id"] = str(attempt.target_id)
            values["created_at"] = attempt.created_at
            if existing is None:
                connection.execute(insert(fetch_attempts).values(**values))

    def complete_target(
        self,
        product: ProductRecord,
        *,
        coverage: float,
        confidence_threshold: float,
    ) -> None:
        now = _utc()
        product_values = product.model_dump(mode="json")
        product_values.update(
            id=str(product.id),
            run_id=str(product.run_id),
            target_id=str(product.target_id),
            price_amount=str(product.price_amount) if product.price_amount is not None else None,
            captured_at=product.captured_at,
            field_evidence={key: value.model_dump(mode="json") for key, value in product.field_evidence.items()},
        )
        with self.engine.begin() as connection:
            profile = connection.execute(
                select(source_profiles).where(source_profiles.c.source == product.source)
            ).mappings().first()
            drift_detected = bool(
                profile
                and profile["dom_fingerprint"] != product.dom_fingerprint
                and (
                    coverage < float(profile["baseline_coverage"])
                    or product.confidence < confidence_threshold
                )
            )
            if profile is None:
                connection.execute(
                    insert(source_profiles).values(
                        source=product.source,
                        dom_fingerprint=product.dom_fingerprint,
                        baseline_coverage=coverage,
                        observed_count=1,
                        updated_at=now,
                    )
                )
            else:
                connection.execute(
                    update(source_profiles)
                    .where(source_profiles.c.source == product.source)
                    .values(
                        dom_fingerprint=(profile["dom_fingerprint"] if drift_detected else product.dom_fingerprint),
                        baseline_coverage=max(float(profile["baseline_coverage"]), coverage),
                        observed_count=int(profile["observed_count"]) + 1,
                        updated_at=now,
                    )
                )
            if drift_detected:
                connection.execute(
                    insert(drift_events).values(
                        id=str(uuid4()),
                        source=product.source,
                        target_id=str(product.target_id),
                        previous_fingerprint=profile["dom_fingerprint"],
                        new_fingerprint=product.dom_fingerprint,
                        coverage=coverage,
                        confidence=product.confidence,
                        detected_at=now,
                    )
                )
            existing_id = connection.execute(
                select(products.c.id).where(products.c.target_id == str(product.target_id))
            ).scalar_one_or_none()
            if existing_id is None:
                connection.execute(insert(products).values(**product_values))
                product_id = str(product.id)
            else:
                product_id = str(existing_id)
                product_values.pop("id", None)
                connection.execute(update(products).where(products.c.id == product_id).values(**product_values))
            if drift_detected or product.confidence < confidence_threshold or coverage < 1.0:
                exists = connection.execute(
                    select(review_items.c.id).where(review_items.c.product_id == product_id)
                ).scalar_one_or_none()
                if exists is None:
                    reason = (
                        "schema_drift"
                        if drift_detected
                        else "low_confidence"
                        if product.confidence < confidence_threshold
                        else "incomplete_required_fields"
                    )
                    connection.execute(
                        insert(review_items).values(
                            id=str(uuid4()),
                            product_id=product_id,
                            status="pending",
                            reason=reason,
                            created_at=now,
                        )
                    )
            connection.execute(
                update(crawl_targets)
                .where(crawl_targets.c.id == str(product.target_id))
                .values(status=CrawlStatus.SUCCEEDED, updated_at=now, error_code=None)
            )
        self._refresh_run(product.run_id)

    def fail_target(
        self,
        target_id: UUID,
        *,
        error_code: str,
        transient: bool,
        retry_delay_seconds: float,
    ) -> CrawlStatus:
        now = _utc()
        with self.engine.begin() as connection:
            row = connection.execute(
                select(crawl_targets).where(crawl_targets.c.id == str(target_id))
            ).mappings().one()
            can_retry = transient and int(row["attempts"]) < int(row["max_attempts"])
            status = CrawlStatus.RETRYING if can_retry else (CrawlStatus.BLOCKED if not transient else CrawlStatus.FAILED)
            next_attempt_at = now + timedelta(seconds=retry_delay_seconds) if can_retry else None
            connection.execute(
                update(crawl_targets)
                .where(crawl_targets.c.id == str(target_id))
                .values(
                    status=status,
                    error_code=error_code,
                    next_attempt_at=next_attempt_at,
                    updated_at=now,
                )
            )
            if can_retry:
                message = TargetMessage(
                    target_id=UUID(row["id"]),
                    run_id=UUID(row["run_id"]),
                    url=row["url"],
                    connector=row["connector"],
                    render_mode=row["render_mode"],
                    attempt=row["attempts"],
                )
                self._insert_outbox(connection, message, available_at=next_attempt_at or now)
            run_id = UUID(row["run_id"])
        self._refresh_run(run_id)
        return status

    def pending_outbox(self, limit: int = 100) -> list[dict[str, Any]]:
        now = _utc()
        with self.engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    select(outbox)
                    .where(and_(outbox.c.published_at.is_(None), outbox.c.available_at <= now))
                    .order_by(outbox.c.created_at)
                    .limit(limit)
                ).mappings()
            ]

    def mark_outbox_published(self, outbox_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(outbox).where(outbox.c.id == outbox_id).values(published_at=_utc())
            )

    def list_products(self, *, source: str | None = None, min_confidence: float = 0.0, limit: int = 100) -> list[dict[str, Any]]:
        statement = select(products).where(products.c.confidence >= min_confidence)
        if source:
            statement = statement.where(products.c.source == source)
        with self.engine.connect() as connection:
            rows = connection.execute(statement.order_by(products.c.captured_at.desc()).limit(limit)).mappings()
            return [_json_row(row) for row in rows]

    def list_fetch_attempts(
        self,
        *,
        run_id: UUID | None = None,
        target_id: UUID | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        statement = select(
            fetch_attempts,
            crawl_targets.c.url,
            crawl_targets.c.run_id,
        ).join(crawl_targets, fetch_attempts.c.target_id == crawl_targets.c.id)
        if run_id is not None:
            statement = statement.where(crawl_targets.c.run_id == str(run_id))
        if target_id is not None:
            statement = statement.where(fetch_attempts.c.target_id == str(target_id))
        with self.engine.connect() as connection:
            rows = connection.execute(
                statement.order_by(fetch_attempts.c.created_at, fetch_attempts.c.attempt).limit(limit)
            ).mappings()
            return [_json_row(row) for row in rows]

    def list_review_items(self, status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
        statement = (
            select(
                review_items,
                products.c.title,
                products.c.canonical_url,
                products.c.confidence,
            )
            .join(products, review_items.c.product_id == products.c.id)
            .where(review_items.c.status == status)
            .order_by(review_items.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as connection:
            return [_json_row(row) for row in connection.execute(statement).mappings()]

    def resolve_review(self, item_id: UUID, resolution: ReviewResolution) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(review_items)
                .where(and_(review_items.c.id == str(item_id), review_items.c.status == "pending"))
                .values(status=resolution.action, note=resolution.note, resolved_at=_utc())
            )
            return bool(result.rowcount)

    def source_health(self) -> list[dict[str, Any]]:
        statement = (
            select(
                crawl_targets.c.connector.label("source"),
                func.count().label("targets"),
                func.sum(case((crawl_targets.c.status == CrawlStatus.SUCCEEDED, 1), else_=0)).label("succeeded"),
                func.max(crawl_targets.c.updated_at).label("last_seen_at"),
            )
            .group_by(crawl_targets.c.connector)
        )
        with self.engine.connect() as connection:
            rows = [_json_row(row) for row in connection.execute(statement).mappings()]
            for row in rows:
                average_latency = connection.execute(
                    select(func.avg(fetch_attempts.c.latency_ms))
                    .select_from(fetch_attempts.join(crawl_targets, fetch_attempts.c.target_id == crawl_targets.c.id))
                    .where(crawl_targets.c.connector == row["source"])
                ).scalar_one_or_none()
                latest_drift = connection.execute(
                    select(drift_events.c.detected_at)
                    .where(drift_events.c.source == row["source"])
                    .order_by(drift_events.c.detected_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                row["avg_latency_ms"] = round(float(average_latency), 2) if average_latency is not None else None
                row["last_drift_at"] = _aware(latest_drift).isoformat() if latest_drift else None
        return rows

    def metrics(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            result = dict(
                connection.execute(
                    select(crawl_targets.c.status, func.count()).group_by(crawl_targets.c.status)
                ).all()
            )
            result["products"] = int(connection.execute(select(func.count()).select_from(products)).scalar_one())
            result["attempts"] = int(connection.execute(select(func.count()).select_from(fetch_attempts)).scalar_one())
            result["reviews_pending"] = int(
                connection.execute(
                    select(func.count()).select_from(review_items).where(review_items.c.status == "pending")
                ).scalar_one()
            )
        return {str(key): int(value) for key, value in result.items()}

    def _insert_outbox(self, connection: Any, message: TargetMessage, *, available_at: datetime) -> None:
        connection.execute(
            insert(outbox).values(
                id=str(uuid4()),
                target_id=str(message.target_id),
                payload=message.model_dump(mode="json"),
                available_at=available_at,
                created_at=_utc(),
            )
        )

    def _refresh_run(self, run_id: UUID) -> None:
        with self.engine.begin() as connection:
            states = list(
                connection.execute(
                    select(crawl_targets.c.status).where(crawl_targets.c.run_id == str(run_id))
                ).scalars()
            )
            if states and all(state == CrawlStatus.SUCCEEDED for state in states):
                run_status = CrawlStatus.SUCCEEDED
            elif states and all(state in {CrawlStatus.SUCCEEDED, CrawlStatus.FAILED, CrawlStatus.BLOCKED} for state in states):
                run_status = CrawlStatus.FAILED if any(state == CrawlStatus.FAILED for state in states) else CrawlStatus.BLOCKED
            elif any(state == CrawlStatus.RUNNING for state in states):
                run_status = CrawlStatus.RUNNING
            else:
                run_status = CrawlStatus.QUEUED
            connection.execute(
                update(crawl_runs)
                .where(crawl_runs.c.id == str(run_id))
                .values(status=run_status, updated_at=_utc())
            )


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _json_row(row: RowMapping) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            result[key] = _aware(value).isoformat()
        else:
            result[key] = value
    return result
