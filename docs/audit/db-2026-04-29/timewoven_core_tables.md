# Tables — `timewoven_core`

## `families`

Columns:

| column | type | nullable | default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('families_id_seq'::regclass) |
| `slug` | text | NO |  |
| `db_name` | text | NO |  |
| `data_path` | text | NO |  |
| `created_at` | timestamp without time zone | YES | now() |

Primary key

`id`

Indexes

- **`families_pkey`**: `CREATE UNIQUE INDEX families_pkey ON public.families USING btree (id)`
- **`families_slug_key`**: `CREATE UNIQUE INDEX families_slug_key ON public.families USING btree (slug)`

Foreign keys

(none)

Estimated row count

1

---
