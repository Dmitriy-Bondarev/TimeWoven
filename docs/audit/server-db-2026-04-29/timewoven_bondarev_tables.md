# timewoven_bondarev — table reference

*Read-only snapshot (estimated row counts where available).*

## `AvatarHistory`

| column | type | nullable | default |
| --- | --- | --- | --- |
| avatar_id | integer(32) | NO | nextval('"AvatarHistory_avatar_id_seq"'::regclass) |
| person_id | integer(32) | NO |  |
| storage_path | character varying | NO |  |
| target_year | integer(32) | YES |  |
| is_current | integer(32) | NO | 0 |
| source_type | character varying | NO |  |
| created_at | character varying | YES |  |
| metadata | text | YES |  |

**PK:** `avatar_id`

**Indexes:**
- `AvatarHistory_pkey`: `CREATE UNIQUE INDEX "AvatarHistory_pkey" ON public."AvatarHistory" USING btree (avatar_id)`

**FK:**
- `person_id` → `People`.`person_id` (`AvatarHistory_person_id_fkey`)

**Estimated rows:** 4

---

## `EarlyAccessRequests`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('"EarlyAccessRequests_id_seq"'::regclass) |
| created_at | timestamp without time zone | NO | now() |
| first_name | character varying | NO |  |
| last_name | character varying | YES |  |
| preferred_channel | character varying | NO |  |
| contact_value | character varying | NO |  |
| about | text | YES |  |
| source | character varying | NO | 'landing'::character varying |
| status | character varying | NO | 'new'::character varying |

**PK:** `id`

**Indexes:**
- `EarlyAccessRequests_pkey`: `CREATE UNIQUE INDEX "EarlyAccessRequests_pkey" ON public."EarlyAccessRequests" USING btree (id)`
- `idx_early_access_requests_created_at`: `CREATE INDEX idx_early_access_requests_created_at ON public."EarlyAccessRequests" USING btree (created_at DESC)`
- `idx_early_access_requests_status`: `CREATE INDEX idx_early_access_requests_status ON public."EarlyAccessRequests" USING btree (status)`

**FK:**
- —

**Estimated rows:** 3

---

## `EventParticipants`

| column | type | nullable | default |
| --- | --- | --- | --- |
| event_id | integer(32) | NO |  |
| person_id | integer(32) | NO |  |
| participant_role | character varying | NO |  |
| is_featured | integer(32) | YES | 0 |
| added_at | character varying | YES |  |

**PK:** `event_id`, `person_id`, `participant_role`

**Indexes:**
- `EventParticipants_pkey`: `CREATE UNIQUE INDEX "EventParticipants_pkey" ON public."EventParticipants" USING btree (event_id, person_id, participant_role)`

**FK:**
- `person_id` → `People`.`person_id` (`EventParticipants_person_id_fkey`)
- `event_id` → `Events`.`event_id` (`EventParticipants_event_id_fkey`)

**Estimated rows:** 0

---

## `Events`

| column | type | nullable | default |
| --- | --- | --- | --- |
| event_id | integer(32) | NO | nextval('"Events_event_id_seq"'::regclass) |
| author_id | integer(32) | YES |  |
| location_id | integer(32) | YES |  |
| event_type | character varying | NO |  |
| date_start | character varying | YES |  |
| date_start_prec | character varying | YES |  |
| date_end | character varying | YES |  |
| date_end_prec | character varying | YES |  |
| is_private | integer(32) | NO | 0 |
| cover_asset_id | integer(32) | YES |  |

**PK:** `event_id`

**Indexes:**
- `Events_pkey`: `CREATE UNIQUE INDEX "Events_pkey" ON public."Events" USING btree (event_id)`

**FK:**
- `author_id` → `People`.`person_id` (`Events_author_id_fkey`)
- `location_id` → `Places`.`place_id` (`Events_location_id_fkey`)

**Estimated rows:** 6

---

## `MaxContactEvents`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('"MaxContactEvents_id_seq"'::regclass) |
| created_at | character varying | NO |  |
| sender_max_user_id | character varying | NO |  |
| contact_max_user_id | character varying | YES |  |
| contact_name | character varying | YES |  |
| contact_first_name | character varying | YES |  |
| contact_last_name | character varying | YES |  |
| raw_payload | text | NO |  |
| matched_person_id | integer(32) | YES |  |
| status | character varying | NO | 'new'::character varying |

**PK:** `id`

**Indexes:**
- `MaxContactEvents_pkey`: `CREATE UNIQUE INDEX "MaxContactEvents_pkey" ON public."MaxContactEvents" USING btree (id)`
- `idx_max_contact_events_contact`: `CREATE INDEX idx_max_contact_events_contact ON public."MaxContactEvents" USING btree (contact_max_user_id)`
- `idx_max_contact_events_sender`: `CREATE INDEX idx_max_contact_events_sender ON public."MaxContactEvents" USING btree (sender_max_user_id)`
- `idx_max_contact_events_status`: `CREATE INDEX idx_max_contact_events_status ON public."MaxContactEvents" USING btree (status)`

**FK:**
- `matched_person_id` → `People`.`person_id` (`MaxContactEvents_matched_person_id_fkey`)

**Estimated rows:** 2

---

## `Memories`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('"Memories_id_seq"'::regclass) |
| author_id | integer(32) | YES |  |
| event_id | integer(32) | YES |  |
| parent_memory_id | integer(32) | YES |  |
| content_text | text | YES |  |
| audio_url | character varying | YES |  |
| transcript_verbatim | text | YES |  |
| transcript_readable | text | YES |  |
| emotional_tone | character varying | YES |  |
| intimacy_level | integer(32) | YES | 1 |
| sensitivity_flag | integer(32) | YES | 0 |
| confidence_score | double precision(53) | YES |  |
| created_at | character varying | YES | to_char(now(), 'YYYY-MM-DD HH24:MI:SS'::text) |
| created_by | integer(32) | YES |  |
| source_type | character varying | YES |  |
| transcription_status | character varying(20) | YES | 'pending'::character varying |
| is_archived | boolean | NO | false |
| essence_text | text | YES |  |

**PK:** `id`

**Indexes:**
- `Memories_pkey`: `CREATE UNIQUE INDEX "Memories_pkey" ON public."Memories" USING btree (id)`

**FK:**
- `author_id` → `People`.`person_id` (`Memories_author_id_fkey`)
- `event_id` → `Events`.`event_id` (`Memories_event_id_fkey`)
- `parent_memory_id` → `Memories`.`id` (`Memories_parent_memory_id_fkey`)
- `created_by` → `People`.`person_id` (`Memories_created_by_fkey`)

**Estimated rows:** 36

---

## `MemoryPeople`

| column | type | nullable | default |
| --- | --- | --- | --- |
| memory_id | integer(32) | NO |  |
| person_id | integer(32) | NO |  |
| role | character varying | NO |  |

**PK:** `memory_id`, `person_id`, `role`

**Indexes:**
- `MemoryPeople_pkey`: `CREATE UNIQUE INDEX "MemoryPeople_pkey" ON public."MemoryPeople" USING btree (memory_id, person_id, role)`

**FK:**
- `memory_id` → `Memories`.`id` (`MemoryPeople_memory_id_fkey`)
- `person_id` → `People`.`person_id` (`MemoryPeople_person_id_fkey`)

**Estimated rows:** 19

---

## `People`

| column | type | nullable | default |
| --- | --- | --- | --- |
| person_id | integer(32) | NO | nextval('"People_person_id_seq"'::regclass) |
| maiden_name | character varying | YES |  |
| gender | character varying | YES |  |
| birth_date | character varying | YES |  |
| birth_date_prec | character varying | YES |  |
| death_date | character varying | YES |  |
| death_date_prec | character varying | YES |  |
| is_alive | integer(32) | NO | 1 |
| is_user | integer(32) | NO | 0 |
| role | character varying | NO | 'placeholder'::character varying |
| successor_id | integer(32) | YES |  |
| default_lang | character varying | NO | 'ru'::character varying |
| phone | character varying | YES |  |
| preferred_ch | character varying | YES |  |
| avatar_url | character varying | YES |  |
| pin | character varying | YES |  |
| messenger_max_id | character varying | YES |  |
| messenger_tg_id | character varying | YES |  |
| contact_email | character varying | YES |  |
| record_status | character varying | NO | 'active'::character varying |
| public_uuid | uuid | NO |  |
| family_access_enabled | boolean | NO | false |
| totp_secret_encrypted | text | YES |  |
| totp_enabled_at | timestamp with time zone | YES |  |
| totp_last_used_at | timestamp with time zone | YES |  |
| family_access_revoked_at | timestamp with time zone | YES |  |

**PK:** `person_id`

**Indexes:**
- `People_pkey`: `CREATE UNIQUE INDEX "People_pkey" ON public."People" USING btree (person_id)`
- `uq_people_public_uuid`: `CREATE UNIQUE INDEX uq_people_public_uuid ON public."People" USING btree (public_uuid) WHERE (public_uuid IS NOT NULL)`

**FK:**
- `successor_id` → `People`.`person_id` (`People_successor_id_fkey`)

**Estimated rows:** 54

---

## `People_I18n`

| column | type | nullable | default |
| --- | --- | --- | --- |
| person_id | integer(32) | NO |  |
| lang_code | character varying | NO |  |
| first_name | character varying | NO |  |
| last_name | character varying | YES |  |
| patronymic | character varying | YES |  |
| biography | text | YES |  |

**PK:** `person_id`, `lang_code`

**Indexes:**
- `People_I18n_pkey`: `CREATE UNIQUE INDEX "People_I18n_pkey" ON public."People_I18n" USING btree (person_id, lang_code)`

**FK:**
- `person_id` → `People`.`person_id` (`People_I18n_person_id_fkey`)

**Estimated rows:** 89

---

## `PersonRelationship`

| column | type | nullable | default |
| --- | --- | --- | --- |
| rel_id | integer(32) | NO | nextval('"PersonRelationship_rel_id_seq"'::regclass) |
| person_from_id | integer(32) | NO |  |
| person_to_id | integer(32) | NO |  |
| relationship_type_id | integer(32) | NO |  |
| is_primary | integer(32) | NO | 1 |
| valid_from | character varying | YES |  |
| valid_to | character varying | YES |  |
| comment | character varying | YES |  |

**PK:** `rel_id`

**Indexes:**
- `PersonRelationship_pkey`: `CREATE UNIQUE INDEX "PersonRelationship_pkey" ON public."PersonRelationship" USING btree (rel_id)`

**FK:**
- `person_from_id` → `People`.`person_id` (`PersonRelationship_person_from_id_fkey`)
- `relationship_type_id` → `RelationshipType`.`id` (`PersonRelationship_relationship_type_id_fkey`)
- `person_to_id` → `People`.`person_id` (`PersonRelationship_person_to_id_fkey`)

**Estimated rows:** 26

---

## `Places`

| column | type | nullable | default |
| --- | --- | --- | --- |
| place_id | integer(32) | NO | nextval('"Places_place_id_seq"'::regclass) |
| country | character varying | YES |  |
| region | character varying | YES |  |
| city | character varying | YES |  |
| coordinates | character varying | YES |  |
| address_raw | character varying | YES |  |
| metadata | text | YES |  |

**PK:** `place_id`

**Indexes:**
- `Places_pkey`: `CREATE UNIQUE INDEX "Places_pkey" ON public."Places" USING btree (place_id)`

**FK:**
- —

**Estimated rows:** 0

---

## `Quotes`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('"Quotes_id_seq"'::regclass) |
| author_id | integer(32) | NO |  |
| content_text | text | NO |  |
| source_memory_id | integer(32) | YES |  |
| created_at | character varying | YES | to_char(now(), 'YYYY-MM-DD HH24:MI:SS'::text) |

**PK:** `id`

**Indexes:**
- `Quotes_pkey`: `CREATE UNIQUE INDEX "Quotes_pkey" ON public."Quotes" USING btree (id)`

**FK:**
- `author_id` → `People`.`person_id` (`Quotes_author_id_fkey`)
- `source_memory_id` → `Memories`.`id` (`Quotes_source_memory_id_fkey`)

**Estimated rows:** 3

---

## `RelationshipType`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('"RelationshipType_id_seq"'::regclass) |
| code | character varying | NO |  |
| symmetry_type | character varying | NO |  |
| category | character varying | NO |  |
| inverse_type_id | integer(32) | YES |  |

**PK:** `id`

**Indexes:**
- `RelationshipType_pkey`: `CREATE UNIQUE INDEX "RelationshipType_pkey" ON public."RelationshipType" USING btree (id)`

**FK:**
- `inverse_type_id` → `RelationshipType`.`id` (`RelationshipType_inverse_type_id_fkey`)

**Estimated rows:** 12

---

## `UnionChildren`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('"UnionChildren_id_seq"'::regclass) |
| union_id | integer(32) | YES |  |
| child_id | integer(32) | YES |  |

**PK:** `id`

**Indexes:**
- `UnionChildren_pkey`: `CREATE UNIQUE INDEX "UnionChildren_pkey" ON public."UnionChildren" USING btree (id)`

**FK:**
- `child_id` → `People`.`person_id` (`UnionChildren_child_id_fkey`)
- `union_id` → `Unions`.`id` (`UnionChildren_union_id_fkey`)

**Estimated rows:** 21

---

## `Unions`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('"Unions_id_seq"'::regclass) |
| partner1_id | integer(32) | YES |  |
| partner2_id | integer(32) | YES |  |
| start_date | character varying | YES |  |
| end_date | character varying | YES |  |

**PK:** `id`

**Indexes:**
- `Unions_pkey`: `CREATE UNIQUE INDEX "Unions_pkey" ON public."Unions" USING btree (id)`

**FK:**
- `partner2_id` → `People`.`person_id` (`Unions_partner2_id_fkey`)
- `partner1_id` → `People`.`person_id` (`Unions_partner1_id_fkey`)

**Estimated rows:** 10

---

## `bot_sessions`

| column | type | nullable | default |
| --- | --- | --- | --- |
| user_id | character varying | NO |  |
| current_step | character varying | YES |  |
| data_json | text | YES |  |

**PK:** `user_id`

**Indexes:**
- `bot_sessions_pkey`: `CREATE UNIQUE INDEX bot_sessions_pkey ON public.bot_sessions USING btree (user_id)`

**FK:**
- —

**Estimated rows:** 1

---

## `family_access_sessions`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('family_access_sessions_id_seq'::regclass) |
| person_id | integer(32) | NO |  |
| session_token_hash | character varying(64) | NO |  |
| created_at | timestamp with time zone | NO | now() |
| expires_at | timestamp with time zone | NO |  |
| revoked_at | timestamp with time zone | YES |  |
| created_ip | character varying(64) | YES |  |
| user_agent | text | YES |  |

**PK:** `id`

**Indexes:**
- `family_access_sessions_pkey`: `CREATE UNIQUE INDEX family_access_sessions_pkey ON public.family_access_sessions USING btree (id)`
- `family_access_sessions_session_token_hash_key`: `CREATE UNIQUE INDEX family_access_sessions_session_token_hash_key ON public.family_access_sessions USING btree (session_token_hash)`
- `idx_fas_expires`: `CREATE INDEX idx_fas_expires ON public.family_access_sessions USING btree (expires_at)`
- `idx_fas_person`: `CREATE INDEX idx_fas_person ON public.family_access_sessions USING btree (person_id)`
- `idx_fas_token`: `CREATE INDEX idx_fas_token ON public.family_access_sessions USING btree (session_token_hash)`

**FK:**
- `person_id` → `People`.`person_id` (`family_access_sessions_person_id_fkey`)

**Estimated rows:** 16

---

## `max_chat_sessions`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('max_chat_sessions_id_seq'::regclass) |
| max_user_id | character varying | NO |  |
| person_id | integer(32) | YES |  |
| status | character varying | NO | 'open'::character varying |
| created_at | character varying | NO |  |
| updated_at | character varying | NO |  |
| finalized_at | character varying | YES |  |
| draft_text | text | YES |  |
| draft_items | text | YES |  |
| message_count | integer(32) | NO | 0 |
| audio_count | integer(32) | NO | 0 |
| memory_id | integer(32) | YES |  |
| analysis_status | character varying | YES |  |

**PK:** `id`

**Indexes:**
- `idx_mcs_user_status`: `CREATE INDEX idx_mcs_user_status ON public.max_chat_sessions USING btree (max_user_id, status)`
- `max_chat_sessions_pkey`: `CREATE UNIQUE INDEX max_chat_sessions_pkey ON public.max_chat_sessions USING btree (id)`

**FK:**
- `person_id` → `People`.`person_id` (`max_chat_sessions_person_id_fkey`)
- `memory_id` → `Memories`.`id` (`max_chat_sessions_memory_id_fkey`)

**Estimated rows:** 7

---

## `person_access_backup_codes`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('person_access_backup_codes_id_seq'::regclass) |
| person_id | integer(32) | NO |  |
| code_hash | character varying(64) | NO |  |
| used_at | timestamp with time zone | YES |  |
| created_at | timestamp with time zone | NO | now() |

**PK:** `id`

**Indexes:**
- `idx_backup_codes_person`: `CREATE INDEX idx_backup_codes_person ON public.person_access_backup_codes USING btree (person_id)`
- `person_access_backup_codes_pkey`: `CREATE UNIQUE INDEX person_access_backup_codes_pkey ON public.person_access_backup_codes USING btree (id)`

**FK:**
- `person_id` → `People`.`person_id` (`person_access_backup_codes_person_id_fkey`)

**Estimated rows:** 16

---

## `personaliases`

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | integer(32) | NO | nextval('personaliases_id_seq'::regclass) |
| person_id | integer(32) | NO |  |
| label | character varying | NO |  |
| alias_type | character varying | NO |  |
| used_by_generation | character varying | YES |  |
| note | text | YES |  |
| created_at | timestamp without time zone | NO | now() |
| spoken_by_person_id | integer(32) | YES |  |
| source | character varying | NO | 'manual'::character varying |
| status | character varying | NO | 'active'::character varying |
| updated_at | timestamp without time zone | NO | now() |

**PK:** `id`

**Indexes:**
- `idx_personaliases_person`: `CREATE INDEX idx_personaliases_person ON public.personaliases USING btree (person_id)`
- `idx_personaliases_person_spoken_status`: `CREATE INDEX idx_personaliases_person_spoken_status ON public.personaliases USING btree (person_id, spoken_by_person_id, status)`
- `idx_personaliases_spoken_by`: `CREATE INDEX idx_personaliases_spoken_by ON public.personaliases USING btree (spoken_by_person_id)`
- `personaliases_pkey`: `CREATE UNIQUE INDEX personaliases_pkey ON public.personaliases USING btree (id)`

**FK:**
- `person_id` → `People`.`person_id` (`personaliases_person_id_fkey`)
- `spoken_by_person_id` → `People`.`person_id` (`personaliases_spoken_by_person_id_fkey`)

**Estimated rows:** 3

---

## Sequences (database)

| sequence | type | increment |
| --- | --- | --- |
| `AvatarHistory_avatar_id_seq` | integer | 1 |
| `EarlyAccessRequests_id_seq` | integer | 1 |
| `Events_event_id_seq` | integer | 1 |
| `MaxContactEvents_id_seq` | integer | 1 |
| `Memories_id_seq` | integer | 1 |
| `People_person_id_seq` | integer | 1 |
| `PersonRelationship_rel_id_seq` | integer | 1 |
| `Places_place_id_seq` | integer | 1 |
| `Quotes_id_seq` | integer | 1 |
| `RelationshipType_id_seq` | integer | 1 |
| `UnionChildren_id_seq` | integer | 1 |
| `Unions_id_seq` | integer | 1 |
| `family_access_sessions_id_seq` | integer | 1 |
| `max_chat_sessions_id_seq` | integer | 1 |
| `person_access_backup_codes_id_seq` | integer | 1 |
| `personaliases_id_seq` | integer | 1 |

## Views

*None.*
## Triggers

*None.*