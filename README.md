# TimeWoven

TimeWoven — платформа для построения семейной истории во времени.

## Core Idea

- Одна семья = одна база данных
- Полная изоляция данных между семьями
- История семьи как временная линия (timeline), а не просто граф

## Architecture

- Multi-family architecture (ADR-007)
- Core registry: `timewoven_core`
- Family DB: `timewoven_{slug}`
- Data storage: `/root/data/timewoven/{slug}`
- Media access: `/media/{slug}/...`

## Structure

- `app/` — backend (FastAPI)
- `docs/` — архитектура и ADR
- `scripts/` — операции и обслуживание
- `migrations/` — SQL-миграции
- `locales/` — i18n

## Current Status

Active development  
Architecture stabilized (multi-family + media layer implemented)

## Next Steps

- UX/UI improvements
- Family onboarding flow
- Public family pages

---

TimeWoven is evolving into a scalable family history platform.

## Deployment

Deployment flow:

Mac → git push → GitHub → webhook → /deploy → HMAC → deploy script

Requirements:

- `GITHUB_WEBHOOK_SECRET` must be set on the server
- `/deploy` accepts only signed GitHub requests
- query-based secrets are forbidden
