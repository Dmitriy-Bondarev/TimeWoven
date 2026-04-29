# Database Audit Snapshot

## Connection method (project)

- Application reads **`DATABASE_URL`** from `.env` (loaded before `app.main`).
- `app/db/session.py` swaps the **database name** in the URL path to target **`timewoven_core`** vs **`timewoven_{tenant}`** (here: `timewoven_bondarev`).
- `app/core/family_resolver.py` uses **`CORE_DATABASE_URL`** → fixed path `/timewoven_core` for the `families` registry.
- **Masked DSN pattern:** `postgresql://***:***@localhost:5432/timewoven_core` (password never logged).

## Databases Found

- `timewoven_core`
- `timewoven_bondarev`

## High-Level Summary

### `timewoven_core`

- **Total tables:** 1
- **Tables with most rows (estimated, `pg_stat_user_tables`)**
  - `families` — ~1
- **Tables with foreign keys:** 0
- **Tables without primary key**
  - (none)
- **Suspicious legacy tables (heuristic)**
  - (none matched)
- **Notes**
  - Read-only introspection; row counts are **estimates** from catalog stats unless analyzed recently.

### `timewoven_bondarev`

- **Total tables:** 0
- **Observation:** No `BASE TABLE` objects were found in schema `public` at snapshot time (empty database, non-public schema, or different migration state on this host).
- **Tables with most rows (estimated, `pg_stat_user_tables`)**
- **Tables with foreign keys:** 0
- **Tables without primary key**
  - (none)
- **Suspicious legacy tables (heuristic)**
  - (none matched)
- **Notes**
  - Read-only introspection; row counts are **estimates** from catalog stats unless analyzed recently.

---

*Generated read-only snapshot for architecture review.*
