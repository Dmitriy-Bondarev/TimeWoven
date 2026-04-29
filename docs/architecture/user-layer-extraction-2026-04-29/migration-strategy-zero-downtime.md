# Migration strategy — zero-risk extraction (strategy only)

**Ticket:** T-USER-LAYER-EXTRACTION-003-2026-04-29  

**No execution, migrations, or downtime procedures are performed in this ticket.** This document defines **phases** for a future programme.

## Principles

- **Coexistence:** old model (`person_id` + People-bound auth) and new model (`users` + mappings) must run in parallel until cutover confidence is high.
- **Rollback safety:** each phase must be reversible **by configuration/feature flags** before irreversible data moves.
- **No big-bang:** avoid single release that both rewrites schema and switches auth.

---

## Phase 0 — Introduce “users” concept logically

- **Documentation and diagrams** — shared vocabulary (`logical user` vs `person`).
- **Code annotations / ADRs** — optional naming in comments only (no behavioural change).
- **Metrics/logging** — if desired later, log both `person_id` and future `user_id` placeholder **without** persisting new IDs yet.

**Rollback:** N/A (documentation-only).

---

## Phase 1 — Shadow user mapping (no DB change)

- **Offline or analytical mapping:** spreadsheets or scripts **outside production mutation** that propose `person_id` → prospective `users.id` pairs for stakeholders.
- **Dual-read experiments (future):** read-only comparison jobs validating counts and uniqueness — **still no writes**.

**Rollback:** discard analytical artifacts.

---

## Phase 2 — Gradual separation of auth identity

Future implementation might:

1. Add **`users`** (and bridge) **additive-only** migrations — existing flows unchanged.
2. **Dual-write:** new sessions optionally reference `users.id` while legacy cookies/sessions still validate via `person_id`.
3. **Migrate secrets** (TOTP storage target) behind flags — tenant-by-tenant or cohort-by-cohort.

**Rollback:**

- Disable dual-write paths; fall back to People-only validation until secrets are stable again.
- Keep **revocation lists** and session invalidation semantics identical during overlap.

---

## Phase 3 — People no longer sole auth subject

- **Authorization APIs** consume **`users.id`** (or membership records) as primary subject.
- **`People`** referenced only for domain authorization (e.g. “may edit this subtree”).
- Legacy **`person_id`**-only paths retired behind deprecation window.

**Rollback:**

- Extended overlap where both principals accepted — only safe if designed in Phase 2.

---

## No-downtime strategy (intent)

- Schema additions preferred over destructive changes until cutover.
- **Blue/green or rolling deploy** compatible: behaviour gated by env flags per instance.
- Session churn: issue **new cookie shape** while honouring old hashes until TTL drains.

---

## Coexistence model (summary)

| Period | Behaviour |
| --- | --- |
| Early | Single subject = `person_id` |
| Middle | Shadow `users.id`; dual validation |
| Late | Primary subject = `user_id`; `person_id` domain-only |

---

*Strategy document — not an execution plan.*
