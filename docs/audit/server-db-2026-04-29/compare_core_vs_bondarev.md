# timewoven_core vs timewoven_bondarev

## Tables common to both databases

*None.*

## Tables only in timewoven_core

- `families`

## Tables only in timewoven_bondarev

- `AvatarHistory`
- `EarlyAccessRequests`
- `EventParticipants`
- `Events`
- `MaxContactEvents`
- `Memories`
- `MemoryPeople`
- `People`
- `People_I18n`
- `PersonRelationship`
- `Places`
- `Quotes`
- `RelationshipType`
- `UnionChildren`
- `Unions`
- `bot_sessions`
- `family_access_sessions`
- `max_chat_sessions`
- `person_access_backup_codes`
- `personaliases`

## Schema drift (same table name)

*No overlapping tables with column differences.*

## Likely shared-system vs family-tenant split

- **`timewoven_core`**: family registry (`families` and related) — routing/metadata shared across tenants.
- **`timewoven_bondarev`**: per-family application data for slug `bondarev` (people, media, timeline, etc.).

The application resolves `slug` → `timewoven_core.families` → `db_name`, then opens SQLAlchemy sessions against that per-family database.