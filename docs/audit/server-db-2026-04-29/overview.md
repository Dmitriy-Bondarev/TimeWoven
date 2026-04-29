# Production database audit snapshot

**Ticket:** T-SERVER-DB-AUDIT-SNAPSHOT-001-2026-04-29

## Server environment

| Field | Value |
| --- | --- |
| Hostname | `vm-nano` |
| OS | Linux 5.15.x (Ubuntu), x86_64 |
| PostgreSQL server | `PostgreSQL 14.22 (Ubuntu 14.22-0ubuntu0.22.04.1) on x86_64-pc-linux-gnu` |
| App service | `timewoven.service` → `EnvironmentFile=/root/projects/TimeWoven/.env`, working dir `/root/projects/TimeWoven` |

### Connection discovery (masked)

- **Source:** `/root/projects/TimeWoven/.env` (`DATABASE_URL`), systemd unit `timewoven.service`.
- **Host / port:** `localhost`:`5432`
- **User:** `postgres` (role name only; password not stored in docs)
- **Note:** `DATABASE_URL` path still references legacy DB name `timewoven`; that database **does not exist** on this server. Runtime builds engines per `db_name` from `timewoven_core.families` (see `app/db/session.py`, `app/core/family_resolver.py`).

### Deployment / runtime discovery

| Source | Finding |
| --- | --- |
| `timewoven.service` | Loads `/root/projects/TimeWoven/.env`; `ExecStart` = uvicorn `app.main:app` on `:8000` |
| `/root/scripts/deploy/update_timewoven.sh` | `git pull` + `systemctl restart timewoven.service` — **no separate DB DSN** |
| Repository search | No `pm2` / `ecosystem` config for this app |
| Docker Compose | No compose file in-repo for the FastAPI app (auxiliary LLM/Whisper stacks may exist outside this audit) |
| Nginx | Site config present under `/etc/nginx/sites-enabled/` (reverse proxy to app); **no DB credentials in scope** |

**Verified target usage:** `timewoven_core` (family registry) + `timewoven_bondarev` (tenant DB for slug resolved via core) match `family_resolver.py` / `session.py`.

### Pre-check results

| Check | Result |
| --- | --- |
| PostgreSQL reachable | OK (via `postgres` database) |
| `timewoven_core` exists | OK |
| `timewoven_bondarev` exists | OK |
| Read-only introspection | OK (`default_transaction_read_only=on` on connection) |

## Databases reviewed

| Database | Tables (`public`) | Probable role |
| --- | --- | --- |
| `timewoven_core` | 1 | Registry of families / routing to tenant DBs |
| `timewoven_bondarev` | 20 | Tenant data for family slug `bondarev` |

## Largest tables (by estimated row count)

### timewoven_core

| Table | Est. rows |
| --- | ---:|
| `families` | 1 |

### timewoven_bondarev

| Table | Est. rows |
| --- | ---:|
| `People_I18n` | 89 |
| `People` | 54 |
| `Memories` | 36 |
| `PersonRelationship` | 26 |
| `UnionChildren` | 21 |
| `MemoryPeople` | 19 |
| `family_access_sessions` | 16 |
| `person_access_backup_codes` | 16 |
| `RelationshipType` | 12 |
| `Unions` | 10 |
| `max_chat_sessions` | 7 |
| `Events` | 6 |
| `AvatarHistory` | 4 |
| `EarlyAccessRequests` | 3 |
| `Quotes` | 3 |

## Immediate anomalies

- **Stale `DATABASE_URL` database segment:** `.env` still lists database `timewoven`; connection must use registry-derived names (`timewoven_bondarev`, `timewoven_core`). 
- **Extra DB on server:** `timewoven_test` exists (not part of this audit scope).

---

*Generated read-only; no schema or data mutations.*