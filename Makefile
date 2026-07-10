.PHONY: install run test lint typecheck check
install:
	python -m pip install -e '.[dev]'
run:
	uvicorn source_readiness_agent.app:app --host 0.0.0.0 --port 8000
test:
	pytest
lint:
	ruff check .
typecheck:
	mypy src
check: lint typecheck test
