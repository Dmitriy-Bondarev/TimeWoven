# Compare: timewoven_core vs timewoven_bondarev

## Tables in both databases

(none)

## Tables unique to timewoven_core

- `families`

## Tables unique to timewoven_bondarev

(none)

## Same table name, different columns

(none)

## Likely shared model vs tenant model

- **`timewoven_core`**: expected registry / cross-family metadata (e.g. `families` registry per ADR-007).
- **`timewoven_bondarev`**: tenant/family-scoped application data (memories, people, etc.).
- Tables appearing in **both** without identical columns suggest **parallel evolution** or shared naming across tenants — verify migrations before unifying schema.
