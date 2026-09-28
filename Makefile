.PHONY: venv sync dev test lint format docker-up docker-down docker-build benchmark clean

venv:
	uv venv .venv

sync:
	uv sync

dev:
	uv run uvicorn backend.src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest backend/tests/unit backend/tests/integration backend/tests/e2e

benchmark:
	uv run python backend/src/evaluation/run_benchmarks.py --limit 5

lint:
	uv run ruff check backend/src backend/tests
	uv run mypy backend/src

format:
	uv run ruff format backend/src backend/tests

docker-build:
	docker build -t enterprise-rag:latest .

docker-up:
	docker compose --profile core up -d

docker-down:
	docker compose --profile core down

clean:
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache .ruff_cache
