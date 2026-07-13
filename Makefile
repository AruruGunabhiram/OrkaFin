.PHONY: install format lint typecheck test migrate knowledge-validate run

install:
	python -m pip install -e '.[dev]'

format:
	ruff format .

lint:
	ruff check .

typecheck:
	mypy src

test:
	pytest -q

migrate:
	alembic upgrade head

knowledge-validate:
	python scripts/validate_knowledge.py

run:
	uvicorn orkafin.main:app --reload
