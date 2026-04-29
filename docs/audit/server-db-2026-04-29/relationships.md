# Foreign key relationships

Grouped by database. Format: `from_table`.`column` → `to_table`.`column`.

## timewoven_core

*No FK constraints in public schema.*

## timewoven_bondarev

- `AvatarHistory`.`person_id` → `People`.`person_id`
- `EventParticipants`.`person_id` → `People`.`person_id`
- `EventParticipants`.`event_id` → `Events`.`event_id`
- `Events`.`author_id` → `People`.`person_id`
- `Events`.`location_id` → `Places`.`place_id`
- `MaxContactEvents`.`matched_person_id` → `People`.`person_id`
- `Memories`.`author_id` → `People`.`person_id`
- `Memories`.`event_id` → `Events`.`event_id`
- `Memories`.`parent_memory_id` → `Memories`.`id`
- `Memories`.`created_by` → `People`.`person_id`
- `MemoryPeople`.`memory_id` → `Memories`.`id`
- `MemoryPeople`.`person_id` → `People`.`person_id`
- `People`.`successor_id` → `People`.`person_id`
- `People_I18n`.`person_id` → `People`.`person_id`
- `PersonRelationship`.`person_from_id` → `People`.`person_id`
- `PersonRelationship`.`relationship_type_id` → `RelationshipType`.`id`
- `PersonRelationship`.`person_to_id` → `People`.`person_id`
- `Quotes`.`author_id` → `People`.`person_id`
- `Quotes`.`source_memory_id` → `Memories`.`id`
- `RelationshipType`.`inverse_type_id` → `RelationshipType`.`id`
- `UnionChildren`.`child_id` → `People`.`person_id`
- `UnionChildren`.`union_id` → `Unions`.`id`
- `Unions`.`partner2_id` → `People`.`person_id`
- `Unions`.`partner1_id` → `People`.`person_id`
- `family_access_sessions`.`person_id` → `People`.`person_id`
- `max_chat_sessions`.`person_id` → `People`.`person_id`
- `max_chat_sessions`.`memory_id` → `Memories`.`id`
- `person_access_backup_codes`.`person_id` → `People`.`person_id`
- `personaliases`.`person_id` → `People`.`person_id`
- `personaliases`.`spoken_by_person_id` → `People`.`person_id`