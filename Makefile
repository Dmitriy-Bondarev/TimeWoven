.PHONY: help install dev test lint fmt run migrate migrate-check revision upgrade downgrade db-shell clean health snapshot cursorrules-sync


# =========================
# ENV LOADING
# =========================
include .env
export


# =========================
# HELP
# =========================
help:
	@echo "Available commands:"
	@echo "  install        - install dependencies"
	@echo "  dev            - run local dev server (reload)"
	@echo "  test           - run tests"
	@echo "  lint           - run lint checks"
	@echo "  fmt            - format code"
	@echo "  run            - run production-like server"
	@echo "  migrate        - apply migrations (head)"
	@echo "  migrate-check  - dry-run migrations (SQL only)"
	@echo "  revision       - create migration (msg=...)"
	@echo "  upgrade        - alias for migrate"
	@echo "  downgrade      - rollback 1 migration"
	@echo "  db-shell       - open database shell"
	@echo "  snapshot       - run safety snapshot"
	@echo "  health         - check service health"
	@echo "  clean          - cleanup pycache"


# =========================
# INSTALL / DEV
# =========================
install:
	poetry install --no-interaction


dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


run:
	poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000


test:
	poetry run pytest -q


lint:
	poetry run ruff check app scripts


fmt:
	poetry run black app scripts
	# или, если перейдёшь на форматер ruff:
	# ruff format .


# =========================
# DATABASE / ALEMBIC
# =========================
migrate: upgrade


migrate-check:
	poetry run alembic upgrade head --sql


upgrade:
	poetry run alembic upgrade head


downgrade:
	poetry run alembic downgrade -1


downgrade:
	poetry run alembic downgrade -1

revision:
	@if [ -z "$(msg)" ]; then \
	  echo "ERROR: please provide msg, e.g. 'make revision msg=add_early_access'"; \
	  exit 1; \
	fi
	poetry run alembic revision --autogenerate -m "$(msg)"


db-shell:
	@if [ -z "$$DATABASE_URL" ]; then \
		echo "ERROR: DATABASE_URL is not set"; \
		exit 1; \
	fi; \
	psql $$DATABASE_URL


# =========================
# OPS
# =========================
snapshot:
	bash scripts/ops/safety_snapshot.sh MANUAL-$(shell date +%Y%m%d-%H%M)


health:
	curl -sf http://localhost:8000/health || exit 1


clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +


cursorrules-sync:
	bash scripts/ops/sync_cursorrules_to_server.sh
