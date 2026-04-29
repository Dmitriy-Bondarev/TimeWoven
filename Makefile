.PHONY: help install dev test lint fmt run migrate revision db-upgrade clean health snapshot

help:
	@echo "Available commands:"
	@echo "  install     - install dependencies"
	@echo "  dev         - run local dev server"
	@echo "  test        - run tests"
	@echo "  lint        - run lint checks"
	@echo "  fmt         - format code"
	@echo "  run         - run production-like server"
	@echo "  migrate     - apply migrations"
	@echo "  revision    - create migration (msg=...)"
	@echo "  db-upgrade  - upgrade db to head"
	@echo "  snapshot    - run safety snapshot"
	@echo "  health      - check service health"
	@echo "  clean       - cleanup pycache"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check .

fmt:
	black .

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

migrate:
	alembic upgrade head

revision:
	alembic revision -m "$(msg)"

db-upgrade:
	alembic upgrade head

snapshot:
	bash scripts/ops/safety_snapshot.sh MANUAL-$(shell date +%Y%m%d-%H%M)

health:
	curl -sf http://localhost:8000/health || exit 1

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
