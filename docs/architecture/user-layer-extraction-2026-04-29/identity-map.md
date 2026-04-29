# Identity map — current implicit model

**Ticket:** T-USER-LAYER-EXTRACTION-003-2026-04-29  

## CURRENT STATE (implicit model)

### User (logical)

There is **no** `users` row type. Logically:

```text
User (logical)
  → People (only concrete representation)
    → person_id (surrogate PK)
```

External-facing identifiers:

| Role | Field / artifact |
| --- | --- |
| URL entry token | `People.public_uuid` |
| Live session subject | `person_id` (from cookie + `family_access_sessions` or legacy cookie) |
| 2FA secret storage | `People.totp_secret_encrypted` |

### Auth signals

| Signal | Storage | Purpose |
| --- | --- | --- |
| `public_uuid` | `People.public_uuid` | Stable link target; maps HTTP route → single `Person` |
| `totp_secret_encrypted` | `People` | Encrypted TOTP seed (Fernet); enrollment/revocation via admin flows |
| `family_access_sessions` | Tenant DB table | Opaque session tokens (hashed), TTL, revocation by `person_id` |
| Backup codes | `person_access_backup_codes` | Hashed one-time codes per `person_id` |
| Flags | `family_access_enabled`, `family_access_revoked_at`, `totp_*` timestamps | Product rules for whether access is allowed |

### Relations — People ↔ Families (routing)

- **Not** a foreign key from `People` to `timewoven_core.families`.
- **Runtime:** HTTP path or default slug → `resolve_family(slug)` reads **`timewoven_core.families`** → `db_name` → SQLAlchemy session for **that** database.
- Each tenant DB contains a **full** `People` table for that family’s domain data.

So **family membership** for app routing is **implicit**: “you are in the DB selected for slug `bondarev`” rather than a join table in core.

### Relations — People ↔ other tenant entities

Representative FK patterns (genealogy + content):

- `Memories.author_id`, `Memories.created_by` → `People.person_id`
- `Events.author_id` → `People.person_id`
- `family_access_sessions.person_id`, `person_access_backup_codes.person_id` → `People.person_id`
- `max_chat_sessions.person_id` → `People.person_id` (channel automation)

**Observation:** the same `person_id` denotes **author**, **session principal**, and **graph node** — unified column namespace.

---

*Analysis only — describes production behaviour as of 2026-04-29.*
