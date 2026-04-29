# Auth flow analysis — family vs admin vs explorer

**Ticket:** T-USER-LAYER-EXTRACTION-003-2026-04-29  

Maps **current** flows to **People**, sessions, and databases. Implementation references: `app/api/routes/tree.py`, `app/services/family_access_service.py`, `app/security.py`, `app/api/routes/admin.py`, `app/api/routes/TW_Explorer.py`.

---

## 1. UUID family entry (`/family/p/{public_uuid}`)

| Step | Behaviour | DB / identity |
| --- | --- | --- |
| Lookup | `find_person_by_public_uuid` | Tenant DB: `People.public_uuid` → `Person` |
| Visibility | `_is_live_visible_person` | Tenant DB: `People` (+ record rules) |
| If session matches same `person_id` | Redirect to `/family/welcome` | `resolve_viewer` → `family_access_sessions` or legacy cookie |
| Else | Redirect to `/family/access/{uuid}?next=…` | Bootstrap TOTP flow |

**Subject:** resolved **`person_id`** after subsequent login; URL alone proves nothing beyond reaching the challenge page.

---

## 2. TOTP validation (`GET/POST /family/access/{public_uuid}`)

| Step | Behaviour | DB / identity |
| --- | --- | --- |
| GET page | Load `Person` by `public_uuid`; show form if `person_family_access_permitted` | Tenant: `People` flags + `totp_secret_encrypted` presence |
| Rate limit | `(client_ip, public_uuid)` in-memory window | No DB |
| POST verify | Decrypt `totp_secret_encrypted`; `verify_totp_code` **or** `use_one_backup_code` | Tenant: `People`, `person_access_backup_codes` |
| On success | `create_family_access_session`, set cookies | Tenant: insert **`family_access_sessions`** (`person_id`) |

**Subject:** **`person_id`** bound to opaque session token (hashed in DB).

---

## 3. Session creation and use (`family_access_sessions`)

| Artifact | Role |
| --- | --- |
| Cookie `tw_family_access` | Raw opaque token; validated via SHA-256 + pepper → lookup session row |
| Row | `session_token_hash`, `expires_at`, `revoked_at`, **`person_id`** |
| `resolve_viewer` | Returns `FamilyViewer(person_id, source)` |

**Subject:** always **`person_id`** once session valid.

**Legacy:** cookie `family_member_id` with numeric `person_id` if `TW_FAMILY_ALLOW_LEGACY_COOKIE` allows — parallel identity path with weaker binding.

---

## 4. Protected family routes (`_require_family_session`)

| Check order | Source |
| --- | --- |
| Valid opaque session | `resolve_viewer` → `get_valid_family_access_session` |
| Else legacy numeric cookie | `_get_family_member_id` |

Failure → redirect to **`/family/need-access`** with `next` return URL.

---

## 5. Admin vs family layer split

### Family layer (People-bound)

- Uses **tenant** DB (`get_db` → resolved family slug → `timewoven_bondarev` today).
- Principal = **`person_id`** via session cookies above.

### Admin layer (`/admin/*`)

| Aspect | Implementation |
| --- | --- |
| Cookie | `tw_admin_session` |
| Token value | `sha256(ADMIN_USERNAME : ADMIN_PASSWORD)` from environment |
| Idle timeout | In-memory `_ADMIN_LAST_SEEN`; cookie cleared if idle |
| Link to People | **None** — admins authenticate as **global operator**, then **mutate** `People` rows for the configured tenant |

Admin provisioning of `public_uuid`, TOTP, backup codes touches **`People`** and related tables **as data**, not as “logged-in family member.”

---

## 6. Explorer (`/explorer`)

| Aspect | Implementation |
| --- | --- |
| Gate | Daily password from `get_daily_password()` (salt + UTC date → SHA-256 prefix) |
| People linkage | **None** — separate experimental/read-only UI plane |

---

## Multi-DB coupling (core → bondarev)

| Concern | Mechanism |
| --- | --- |
| Which tenant DB | `timewoven_core.families` (`slug` → `db_name`) |
| Family auth rows | **Only** in tenant DB (`People`, `family_access_sessions`) |
| Core role | **Routing registry**, not session store |

Session **does not** span families; switching slug implies **different** DB connection — identity is **not global** across tenants.

---

*Analysis only.*
