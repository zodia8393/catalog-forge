# Web Scraping 포지션 대응

| 공고 요구 | CatalogForge evidence |
|---|---|
| 다양한 source의 안정적 수집·처리 | connector boundary, robots/allowlist, HTTP·Playwright mode |
| 대규모 동시 요청과 실패 복구 | async fetch, host limiter, Redis consumer group, retry/circuit breaker, stale reclaim |
| 서로 다른 웹 문서의 구조화 | JSON-LD, source selector, semantic fallback, field provenance |
| 안정적인 데이터 pipeline | PostgreSQL source of truth, transactional outbox, idempotent target contract |
| 외부 구조 변경 대응 | DOM fingerprint, confidence·coverage drift gate, human review queue |
| Backend API 운영 | FastAPI health/readiness/metrics와 versioned REST API |
| Product·business impact | 잘못된 상품 정보를 자동 확정하지 않고 신뢰 가능한 catalog freshness를 운영 화면에서 관리 |

프로젝트의 핵심 설명은 “1,000개를 빨리 긁었다”가 아니라 “83개 transient failure와 17개 stale message가 있어도 1,000개를 유실·중복 없이 terminal state로 만들고, 구조 변경은 review로 격리했다”이다.
