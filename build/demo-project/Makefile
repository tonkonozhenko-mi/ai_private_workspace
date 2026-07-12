.PHONY: test lint run

test:
	pytest tests -q

lint:
	ruff check src tests

run:
	uvicorn src.api.main:app --reload
