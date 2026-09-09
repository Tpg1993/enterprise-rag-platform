.PHONY: venv sync dev test lint format docker-up docker-down clean

venv:
	uv venv .venv

sync:
	uv sync

dev:
	uv run uvicorn backend.src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest backend/tests/unit backend/tests/integration backend/tests/e2e

lint:
	uv run ruff check backend/src backend/tests
	uv run mypy backend/src

format:
	uv run ruff format backend/src backend/tests

docker-up:
	docker compose --profile core up -d

docker-down:
	docker compose --profile core down

clean:
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache .ruff_cache
