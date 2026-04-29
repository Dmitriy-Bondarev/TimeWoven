# User layer extraction — overview

**Ticket:** T-USER-LAYER-EXTRACTION-003-2026-04-29  

This document describes the **implicit “User” architecture** embedded in People, auth columns, and session storage. No separate `users` table exists today.

## What “User” means today (implicit)

There is **no first-class User entity** in the schema. The closest equivalents are:

| Concept | Actual implementation |
| --- | --- |
| Authenticated family-site visitor | `People` row **plus** successful TOTP (or backup code) and an opaque browser session |
| Entry identifier for links | `People.public_uuid` (stable UUID in URLs) |
| Cryptographic second factor | `People.totp_secret_encrypted` (application-layer encryption; provisioning via pyotp) |
| Session persistence | `family_access_sessions` keyed by `person_id`, cookie holds opaque token |

So **“user” in product language** maps operationally to **“this `person_id` passed family gate”**, not to an abstract account independent of genealogy.

## Where identity actually lives

- **Surrogate key:** `People.person_id` (integer PK in tenant DB `timewoven_bondarev`).
- **Stable public handle:** `People.public_uuid` — unique, indexed; used in `/family/p/{uuid}`, `/family/access/{uuid}` routes.
- **Tenant routing:** `timewoven_core.families` resolves URL slug → `db_name`; all `People` rows live in that tenant database only.

Identity for the family web app is therefore **co-extensive with a genealogical Person row** in the tenant DB.

## How auth maps to identity

1. **Bootstrap:** User receives a URL containing `public_uuid`. The server resolves `Person` via `find_person_by_public_uuid` (filter on `People.public_uuid`).
2. **Proof:** User enters **TOTP** (6-digit) or a **one-time backup code**. Valid codes prove possession of secrets bound to that same `Person` row (`totp_secret_encrypted`, `person_access_backup_codes`).
3. **Session:** On success, `create_family_access_session` inserts a row with **hashed** opaque token; the browser stores cookie `tw_family_access`. Optional legacy path resolves `family_member_id` cookie (numeric `person_id`) when enabled.

There is **no password login** for family users in the classical sense; gate is **possession of link + TOTP/backup**.

## How family access binds to `person_id`

- Table **`family_access_sessions`**: `person_id` FK → `People.person_id`, plus `session_token_hash`, expiry, revocation.
- Cookie **`tw_family_access`**: raw token (not stored in DB); validated by hashing and lookup in `family_access_sessions`.
- **`resolve_viewer`** returns `FamilyViewer(person_id=..., source="totp_session" | "legacy_cookie")` — downstream routes authorize **by integer `person_id`**.

Family UI checks often combine:

- Valid session (cookie → DB row → `person_id`), and/or  
- Legacy `family_member_id` cookie.

## How UUID links act as temporary user bootstrap

- **`public_uuid`** is **not** a session; it is a **capability**: anyone who knows it can reach the TOTP challenge for that person (subject to rate limits and `family_access_*` flags).
- First visit typically redirects `/family/p/{uuid}` → `/family/access/{uuid}` unless an existing session already matches that `person_id`.
- After TOTP success, **opaque session** replaces repeated proof until TTL/expiry/revocation — **bootstrap → sustained session**.

Admin-created **`public_uuid`** (and TOTP enrollment in admin) is the operational “invite channel”; there is no separate signup email flow tied to a global user directory.

## Related layers (out of scope for “People user”, but part of full auth picture)

- **Admin:** `tw_admin_session` cookie — env username/password hashed into token; **not** tied to `People`.
- **Explorer:** `/explorer` uses a **daily derived password** (`get_daily_password()`); **not** tied to `People`.

---

*Analysis only — no schema or code changes in this ticket.*
