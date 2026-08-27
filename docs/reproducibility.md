# Reproducibility

## Local checks

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m catalog_forge.rehearsal --targets 1000 --output-root /tmp/catalog-forge

cd web
npm ci
npm audit --audit-level=high
npm run typecheck
npm run build
```

`rehearsal`은 local ASGI fixture와 in-memory SQLite를 사용해 외부 환경과 무관하게 429, retry, stale message reclaim, idempotent write를 재현한다. `public_demo`만 외부 network를 사용한다.

## Evidence

2026-08-27 KST 검증 artifact 기본 위치:

- `/DATA/HJ/prj/data-scientist-career/projects/catalog-forge/recovery_rehearsal.json`
- `/DATA/HJ/prj/data-scientist-career/projects/catalog-forge/books_to_scrape_demo.json`
- `/DATA/HJ/prj/data-scientist-career/projects/catalog-forge/benchmark.json`

수치는 artifact에서 다시 읽어 README와 demo에 반영하며 실행하지 않은 결과를 기재하지 않는다.
