"""
Minimal shim: exports used by `app.api.routes.admin` until the full
person-alias service layer is restored (only `.pyc` was left in tree).
"""

# alias_kind / type values (see migrations/007_add_person_aliases.sql)
ALIAS_TYPES: frozenset[str] = frozenset(
    {
        "kinship_term",
        "nickname",
        "diminutive",
        "formal_with_patronymic",
        "other",
    }
)

# Workflow states referenced in admin filters and forms
ALIAS_STATUS: frozenset[str] = frozenset(
    {
        "active",
        "rejected",
        "pending",
    }
)
