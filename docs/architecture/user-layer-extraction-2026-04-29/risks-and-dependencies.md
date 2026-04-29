# Risks and dependencies — user layer extraction

**Ticket:** T-USER-LAYER-EXTRACTION-003-2026-04-29  

## Coupling risk in `People`

- **Auth columns** (`totp_secret_encrypted`, access flags, timestamps) live beside **genealogy** fields — any future identity extraction must **untangle migrations** and row-level security boundaries.
- **`is_user`** / **`role`** columns exist at domain level; semantics may overlap with future account roles — naming drift risk.

## Hidden dependency on `public_uuid`

- External **shareable URLs** are keyed by UUID on **`People`** — changing ownership model without breaking links requires **stable redirects** or dual-published identifiers during transition.
- Rate limiting is keyed **`(ip, public_uuid)`** — abuse surfaces tied to same identifier used for invites.

## Session-based identity drift

- Multiple acceptance paths: **`tw_family_access`** (preferred), **`family_member_id`** legacy cookie, optional **`resolve_viewer`** fallback — **three ways** to assert “same person,” increasing test matrix for any user-layer split.
- Sessions store **`person_id`** only — **no** separate session principal type today.

## Multi-DB tenant coupling (`timewoven_core` → tenant DB)

- **Registry:** `timewoven_core.families` — no auth sessions here.
- **All family identity state** in tenant DB — backup, replication, and GDPR responses are **per-database**.
- Cross-tenant **single sign-on** cannot exist without a **shared identity store** in core or elsewhere.

## Operational / backup dependencies

- Family access secrets (**TOTP ciphertext**) depend on **`TW_FAMILY_FERNET_KEY` / dev seed** behaviour — rotation strategies affect extraction timeline (documented in ops, not duplicated here).

## Summary matrix

| Risk | Severity | Notes |
| --- | --- | --- |
| Dual role of `People` | High | Blocks clean GDPR and SSO stories |
| URL tied to person row | Medium | Needs continuity plan for `public_uuid` |
| Legacy cookie path | Medium | Must sunset explicitly when user layer lands |
| Tenant-isolated sessions | Low/Medium | By design; conflicts with multi-family users |

---

*Planning notes — no remediation executed in this ticket.*
