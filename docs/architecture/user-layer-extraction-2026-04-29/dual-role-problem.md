# Dual-role problem — People as identity and domain entity

**Ticket:** T-USER-LAYER-EXTRACTION-003-2026-04-29  

## The issue

`People` currently satisfies **two incompatible conceptual roles**:

1. **Authentication subject** — who proved access via TOTP/backup/session (`public_uuid`, `totp_secret_encrypted`, `family_access_sessions`).
2. **Domain entity** — genealogical person in the tree (names via `People_I18n`, unions, memories, events).

Those concerns share one row type and one primary key (`person_id`).

## Risks

### Coupling of auth and domain model

- Security lifecycle (rotate TOTP, revoke sessions, disable access) is **physically stored on the same row** as biography, dates of birth/death, and tree placement.
- Authorization bugs risk conflating **“can edit tree”** with **“is this node in the graph”** — today partially mitigated by route design, but the **data model does not enforce separation**.

### Migration complexity

- Introducing global login (email/OIDC) or cross-family identity requires either **splitting** these concerns or **overlaying** new tables while keeping `person_id` as legacy anchor — high coordination cost while both modes coexist.

### GDPR / privacy ambiguity

- **Data subject** for consent and erasure may be ambiguous: is it the **living user** behind TOTP or the **historical figure** represented in the tree? Same row mixes **credentials**, **contact hooks** (`contact_email`, messengers), and **genealogical facts**.
- Export/erase flows must treat columns with different legal bases; a single-table dump **does not** mirror natural boundaries.

### Multi-family scaling limitation

- If one human should participate in **multiple families** with **one** identity, today they would map to **multiple `People` rows** in **different tenant DBs** — no shared user registry.
- `timewoven_core.families` routes DB selection only; there is **no** core-level “natural person” linking tenants.

---

*Design critique for planning; no implementation in this ticket.*
