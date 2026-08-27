# CatalogForge

[![CI](https://github.com/zodia8393/catalog-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/zodia8393/catalog-forge/actions/workflows/ci.yml)
[![Pages](https://github.com/zodia8393/catalog-forge/actions/workflows/pages.yml/badge.svg)](https://github.com/zodia8393/catalog-forge/actions/workflows/pages.yml)

**[Recorded operations demo](https://zodia8393.github.io/catalog-forge/)**

**구조 변경과 장애에 견디는 commerce web ingestion control plane**입니다. URL을 많이 요청하는 scraper가 아니라 수집 실패, worker crash, schema drift가 생겨도 상품 catalog를 조용히 오염시키지 않는 운영 제품을 만들었습니다.

> **Verified evidence · 2026-08-27 KST** — 1,000 targets 중 83 transient failures와 17 stale messages를 전부 복구 · succeeded 1,000 · lost/duplicate 0 · labeled required fields 400/400 · Books to Scrape 20/20

## 핵심 결과

| Metric | Result | Evidence |
|---|---:|---|
| Failure-recovery rehearsal | 1,000 / 1,000 succeeded | [1,083 attempts · recovery 83/83](docs/evidence/recovery_rehearsal.json) |
| Worker crash recovery | 17 / 17 reclaimed | [pending-message reclaim rehearsal](docs/evidence/recovery_rehearsal.json) |
| Data integrity | lost 0 · duplicate 0 | [`target_id` idempotency evidence](docs/evidence/recovery_rehearsal.json) |
| Parser accuracy | 400 / 400 fields | [100 labeled products × 4 fields](tests/test_parser.py) |
| Public connector | 20 / 20 succeeded | [Books to Scrape · listing discovery 1 page](docs/evidence/books_to_scrape_demo.json) |
| Async throughput | 28.76× baseline | [1,000 pages · controlled 10ms fixture](docs/evidence/benchmark.json) |
| Automated regression | 20 tests | config, parser, drift, API, SSRF, redirect guard, retry, recovery |
| Frontend security | 0 vulnerabilities | `npm audit` after Next.js 16.3.3 update |

## Product surface

- **Async collection:** host별 concurrency/rate limit, robots policy, response size와 SSRF guard
- **Failure recovery:** PostgreSQL transactional outbox, Redis Streams consumer group, retry/backoff, circuit breaker, stale reclaim
- **Explainable parsing:** JSON-LD → connector selector → semantic fallback, field-level provenance/confidence
- **Drift control:** DOM fingerprint 변화와 field coverage/confidence 저하를 함께 감지해 human review로 격리
- **Operations UI:** FastAPI REST/health/metrics와 Next.js overview, crawl run, catalog review 화면
- **Browser fallback:** JavaScript-rendered 문서는 allowlisted Playwright Chromium mode로 처리

![CatalogForge dashboard](docs/dashboard-preview.png)

## Architecture

```text
Next.js ──> FastAPI ──> PostgreSQL + transactional outbox
                              │
                              ▼
                        Redis Streams
                              │
                async worker / stale reclaim
                              │
                  httpx ──> Playwright fallback
                              │
                 parser ──> drift/review gate ──> catalog
```

상세 설계는 [system design](docs/system_design.md), field 계약은 [data contract](docs/data_contract.md), 공고 대응은 [hiring alignment](docs/hiring_market_alignment.md)에 정리했습니다.

## 5분 실행

```bash
cp .env.example .env
docker compose up --build
```

- Dashboard: `http://localhost:3000`
- API docs: `http://localhost:8100/docs`
- Fixture: `http://localhost:8101/catalog`

Fixture crawl 생성:

```bash
curl -X POST http://localhost:8100/api/v1/crawl-runs \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: local-demo-key' \
  -d '{"connector":"generic","start_urls":["http://fixture:8101/products/1"],"max_pages":1,"render_mode":"http"}'
```

## 검증

```bash
pip install -e ".[dev]"
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m catalog_forge.rehearsal --targets 1000 --output-root /tmp/catalog-forge

cd web
npm ci
npm audit --audit-level=high
npm run typecheck
npm run build
```

외부 connector 검증은 대상이 명시적으로 scraping sandbox임을 확인한 뒤 실행합니다.

```bash
PYTHONPATH=src python3 -m catalog_forge.public_demo --products 20 --output-root /tmp/catalog-forge
```

## 한계

- v1은 login, CAPTCHA, proxy rotation, 차단 우회를 지원하지 않습니다.
- LLM attribute extraction은 재현 가능한 scraping·recovery 품질을 흐리지 않도록 제외했습니다.
- Static Pages demo는 recorded evidence를 보여주며 public write API를 노출하지 않습니다.
- 실제 상용 source를 추가할 때는 해당 사이트 약관, robots, 요청 예산을 별도 검토해야 합니다.
