# Risks and opportunities (architecture notes)

## Duplicated structures

- No identically named tables in both DBs with different columns (see compare report); duplication is primarily **conceptual** (e.g. future shared users vs per-tenant profiles).

## Missing constraints

- Review nullable FK targets and optional columns on identity-touching tables in bondarev (see per-table docs). Add FKs/indexes where referential integrity should be enforced in DB, not only in application code.

## Nullable risks

- Wide nullability on legacy columns may complicate User Layer v1 guarantees; cross-check critical identifiers (`public_uuid`, channel IDs, etc.) against product rules.

## Naming inconsistencies

- Legacy vs migrated names (`timewoven` → `timewoven_bondarev`) may linger in env/docs; align `DATABASE_URL` path with operational truth to reduce operator confusion.

## Auth model clues

- Core holds **`families`** registry; tenant DB holds people/admin/session-related structures — consistent with **multi-DB multi-tenant** routing.

## User-layer readiness

- Introducing a cross-tenant **user** identity likely requires either: linking tables in `timewoven_core`, or a dedicated auth DB — current split favors **registry in core + tenant payload in bondarev**.

## Two-DB model justification

- **Still justified:** `timewoven_core` as minimal shared routing/registry; per-family databases for isolation and backup granularity.
- **Watch:** operational overhead (migrations N times), and cross-tenant queries requiring federation or replication.

*Opinion notes for planning only — not production directives.*