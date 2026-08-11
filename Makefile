.PHONY: install api web local test reset-demo

install:
	cd backend && uv sync --dev
	cd frontend && npm install

api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

local:
	./scripts/run-local.sh

test:
	cd backend && uv run python -m pytest
	cd frontend && npm run lint && npm run build && npm test -- --run

reset-demo:
	cd backend && uv run python -m scripts.reset_demo
