#!/bin/bash
# Local CI script - mirrors GitHub Actions CI workflow
# Run this before pushing to catch errors early

set -euo pipefail

echo "=== Local CI ==="
echo ""

echo "1. Lint with ruff..."
uv run ruff check .
echo "   PASSED"
echo ""

echo "2. Run tests..."
uv run pytest tests/ -v --ignore=tests/test_real_llm_integration.py
echo "   PASSED"
echo ""

echo "=== All CI checks passed ==="
