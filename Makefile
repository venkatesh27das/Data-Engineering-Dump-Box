.PHONY: install test lint typecheck run check
install:
	python -m pip install -e '.[dev]'
test:
	pytest
lint:
	ruff check .
typecheck:
	mypy src
run:
	uvicorn processing_quality_agent.app:app --reload --port 8000
check: lint typecheck test
