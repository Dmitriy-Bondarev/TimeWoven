# Risks and opportunities

## Duplicate structures

- **Overlapping table names:** 0 tables appear in both databases — risk of **schema drift** if migrations are applied to one tenant DB only.

## Missing constraints

- Review tables **without primary keys** (see `overview.md`) — append-only or staging tables may be intentional; otherwise consider PKs for ORM performance and integrity.

## Nullable risks

- Columns marked nullable may hide incomplete joins; validate critical paths (person/memory ownership) before User Layer v1 identity joins.

## Naming inconsistencies

- Mixed naming between registry (`timewoven_core`) and tenant DBs is expected; enforce consistent prefixes only when consolidating tooling.

## Migration readiness for User Layer v1

- Introducing `users`, memberships, invites (ADR-010/011) requires **clear placement**: registry vs tenant DB — align with ADR-007 multi-family boundaries before DDL.

## Recommendation: two DBs vs unify later

- **Short term:** keep **`timewoven_core` + per-family DB** as implemented — lowest blast radius for GDPR/export per family.
- **Long term:** optional consolidation only if operational complexity outweighs isolation benefits; any unify needs migration playbook + downtime strategy.
