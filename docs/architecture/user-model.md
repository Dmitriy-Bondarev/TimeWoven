# User Model (v1)

## Entities

User
- id
- email
- created_at
- consent_given_at

Family
- id
- slug
- db_name
- owner_user_id

## Relationships

User (1) → (1) Family

## Principles

- 1 user = 1 family (initially)
- family data fully isolated
- ownership is absolute