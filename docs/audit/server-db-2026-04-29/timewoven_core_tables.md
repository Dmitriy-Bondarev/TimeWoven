# timewoven_core — table reference

*Read-only snapshot (estimated row counts where available).*

## `families`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | uuid | NO |  |
| slug | text | NO |  |
| db_name | text | NO |  |
| data_path | text | NO |  |
| created_at | timestamp without time zone | YES | now() |

**PK:** `id`

**Indexes:**
- `families_pkey`: `CREATE UNIQUE INDEX families_pkey ON public.families USING btree (id)`
- `families_slug_key`: `CREATE UNIQUE INDEX families_slug_key ON public.families USING btree (slug)`

**FK:**
- —

**Estimated rows:** 1

---

## Sequences (database)

*None in `public`.*

## Views

*None.*
## Triggers

*None.*