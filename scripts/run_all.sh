#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m compileall -q src tests
python3 -m pytest -q
python3 -m catalog_forge.benchmark --pages 200 --output "${OUTPUT_ROOT:-artifacts}/benchmark.json"
python3 -m catalog_forge.rehearsal --targets 200 --output-root "${OUTPUT_ROOT:-artifacts}"
