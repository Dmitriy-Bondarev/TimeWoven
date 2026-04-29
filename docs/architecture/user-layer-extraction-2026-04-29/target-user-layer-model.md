# Target user layer model (canonical — not implemented)

**Ticket:** T-USER-LAYER-EXTRACTION-003-2026-04-29  

This section defines a **clean separation** for future architecture. **No tables or migrations are implied here** — logical target state only.

## Canonical identity layer (future)

Conceptual table:

```text
users
  id              UUID        -- stable cross-cutting identity
  email           TEXT NULL   -- optional future; unique when present
  status          TEXT        -- active, suspended, deleted, …
  created_at      TIMESTAMPTZ
  …               -- auth provider refs, MFA flags, etc., as needed later
```

**Rules:**

- **`users`** represents **authentication and account lifecycle** only.
- **PII policy** (what lives on `users` vs tenant domain tables) is a separate privacy design — email might remain optional indefinitely.

## Mapping (legacy bridge)

Initial coexistence:

```text
users 1 — 1 People   (bridge table or nullable FK on one side)
```

- Bridge might live in **tenant DB** (`users.id` ↔ `People.person_id` or separate mapping UUID) or partially in **core** — **decision deferred** to migration phases.
- Purpose: **every existing `person_id` with family access** gains a stable **`users.id`** without rewriting all FKs overnight.

## People becomes domain-only

After separation is complete (long horizon):

- **`People`** holds genealogy: names, unions, visibility, media refs, etc.
- **Auth columns** (`totp_secret_encrypted`, possibly `public_uuid` usage model) **migrate** off `People` onto **`users`** or dedicated **`credentials` / `family_memberships`** structures — exact split is a later schema design.

Non-goals for this document:

- Concrete DDL
- Choice of IdP
- Whether `public_uuid` remains capability URL or moves to membership records

---

*Forward-looking architecture only.*
