.PHONY: install dev backend worker frontend redis test test-backend test-frontend lint format create-fixtures seed-demo verify-lmstudio

install:
	uv sync --project backend --extra dev
	cd frontend && npm install

dev:
	@echo "Run 'make backend' and 'make frontend' in separate terminals. The built-in worker is enabled by default."

backend:
	uv run --project backend uvicorn app.main:app --app-dir backend --reload --port 8000

worker:
	uv run --project backend python -m app.jobs.worker

frontend:
	cd frontend && npm run dev

redis:
	docker compose up redis

test: test-backend test-frontend

test-backend:
	uv run --project backend pytest backend/tests

test-frontend:
	cd frontend && npm test -- --run

lint:
	uv run --project backend ruff check backend
	cd frontend && npm run lint

format:
	uv run --project backend ruff format backend
	cd frontend && npm run format

create-fixtures:
	uv run --project backend python scripts/create_test_workbooks.py

seed-demo:
	uv run --project backend python scripts/seed_demo.py

verify-lmstudio:
	uv run --project backend python scripts/verify_lmstudio.py

