.PHONY: install format lint typecheck test test-coverage security-scan migrate database-init knowledge-validate run demo demo-check inspect-activity

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

test-coverage:
	pytest --cov=orkafin --cov-report=term-missing -q

security-scan:
	python scripts/scan_secrets.py

migrate:
	alembic upgrade head

database-init: migrate

knowledge-validate:
	python scripts/validate_knowledge.py

run:
	uvicorn orkafin.main:app --reload

demo:
	python scripts/run_local_demo.py --subject admin

demo-check:
	python scripts/run_local_demo.py --subject admin --check-only

inspect-activity:
	python scripts/inspect_local_activity.py
