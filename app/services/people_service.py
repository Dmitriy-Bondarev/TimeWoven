from sqlalchemy.orm import Session

from app.models import Person, PersonI18n

ALLOWED_ROLES = {"placeholder", "relative", "family_admin", "bot_only"}


def _to_flag(value: bool | int | None, default: int) -> int:
    if value is None:
        return default
    return 1 if bool(value) else 0


def _optional_text(value: object) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def create_person_with_i18n(
    db: Session,
    person_data: dict,
    ru_data: dict,
    en_data: dict | None = None,
) -> Person:
    """Create one People row and related RU/EN People_I18n rows in one transaction."""
    ru_first_name = str((ru_data or {}).get("first_name") or "").strip()
    if not ru_first_name:
        raise ValueError("Поле first_name_ru обязательно")

    person_payload = person_data or {}
    raw_role = _optional_text(person_payload.get("role")) or "placeholder"
    role = raw_role if raw_role in ALLOWED_ROLES else "placeholder"
    person = Person(
        gender=_optional_text(person_payload.get("gender")) or "Unknown",
        is_alive=_to_flag(person_payload.get("is_alive"), default=1),
        role=role,
        default_lang=_optional_text(person_payload.get("default_lang")) or "ru",
        maiden_name=_optional_text(person_payload.get("maiden_name")),
        birth_date=_optional_text(person_payload.get("birth_date")),
        birth_date_prec=_optional_text(person_payload.get("birth_date_prec")),
        death_date=_optional_text(person_payload.get("death_date")),
        death_date_prec=_optional_text(person_payload.get("death_date_prec")),
        phone=_optional_text(person_payload.get("phone")),
        preferred_ch=_optional_text(person_payload.get("preferred_ch")),
        contact_email=_optional_text(person_payload.get("contact_email")),
        avatar_url=_optional_text(person_payload.get("avatar_url")),
        is_user=_to_flag(person_payload.get("is_user"), default=0),
        record_status=_optional_text(person_payload.get("record_status")) or "active",
        messenger_max_id=(
            _optional_text(person_payload.get("max_user_id"))
            or _optional_text(person_payload.get("messenger_max_id"))
        ),
    )

    try:
        db.add(person)
        db.flush()

        db.add(
            PersonI18n(
                person_id=person.person_id,
                lang_code="ru",
                first_name=ru_first_name,
                last_name=(ru_data or {}).get("last_name"),
                patronymic=(ru_data or {}).get("patronymic"),
                biography=(ru_data or {}).get("biography"),
            )
        )

        en_first_name = str((en_data or {}).get("first_name") or "").strip()
        if en_first_name:
            db.add(
                PersonI18n(
                    person_id=person.person_id,
                    lang_code="en",
                    first_name=en_first_name,
                    last_name=(en_data or {}).get("last_name"),
                    patronymic=(en_data or {}).get("patronymic"),
                    biography=(en_data or {}).get("biography"),
                )
            )

        db.commit()
        db.refresh(person)
        return person
    except Exception:
        db.rollback()
        raise


def update_person_with_i18n(
    db: Session,
    person_id: int,
    person_data: dict,
    ru_data: dict,
    en_data: dict | None = None,
) -> Person:
    """Update People row and upsert RU/EN People_I18n rows in one transaction."""
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise ValueError("Персона не найдена")

    ru_first_name = str((ru_data or {}).get("first_name") or "").strip()
    if not ru_first_name:
        raise ValueError("Поле first_name_ru обязательно")

    person_payload = person_data or {}
    raw_role = _optional_text(person_payload.get("role")) or "placeholder"
    role = raw_role if raw_role in ALLOWED_ROLES else "placeholder"

    person.gender = _optional_text(person_payload.get("gender")) or "Unknown"
    person.is_alive = _to_flag(person_payload.get("is_alive"), default=1)
    person.role = role
    person.default_lang = _optional_text(person_payload.get("default_lang")) or "ru"
    person.maiden_name = _optional_text(person_payload.get("maiden_name"))
    person.birth_date = _optional_text(person_payload.get("birth_date"))
    person.birth_date_prec = _optional_text(person_payload.get("birth_date_prec"))
    person.death_date = _optional_text(person_payload.get("death_date"))
    person.death_date_prec = _optional_text(person_payload.get("death_date_prec"))
    person.phone = _optional_text(person_payload.get("phone"))
    person.preferred_ch = _optional_text(person_payload.get("preferred_ch"))
    person.contact_email = _optional_text(person_payload.get("contact_email"))
    person.avatar_url = _optional_text(person_payload.get("avatar_url"))
    person.is_user = _to_flag(person_payload.get("is_user"), default=0)
    person.record_status = (
        _optional_text(person_payload.get("record_status")) or "active"
    )
    person.messenger_max_id = _optional_text(
        person_payload.get("max_user_id")
    ) or _optional_text(person_payload.get("messenger_max_id"))

    ru_i18n = (
        db.query(PersonI18n)
        .filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "ru")
        .first()
    )
    if not ru_i18n:
        ru_i18n = PersonI18n(person_id=person_id, lang_code="ru")
        db.add(ru_i18n)

    ru_i18n.first_name = ru_first_name
    ru_i18n.last_name = _optional_text((ru_data or {}).get("last_name"))
    ru_i18n.patronymic = _optional_text((ru_data or {}).get("patronymic"))
    ru_i18n.biography = _optional_text((ru_data or {}).get("biography"))

    en_payload = en_data or {}
    en_first_name = str(en_payload.get("first_name") or "").strip()
    has_en_payload = any(
        str(en_payload.get(field) or "").strip()
        for field in ("first_name", "last_name", "patronymic", "biography")
    )

    en_i18n = (
        db.query(PersonI18n)
        .filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "en")
        .first()
    )

    if has_en_payload and not en_first_name:
        raise ValueError("Для EN-профиля нужно заполнить first_name_en")

    if has_en_payload:
        if not en_i18n:
            en_i18n = PersonI18n(person_id=person_id, lang_code="en")
            db.add(en_i18n)

        en_i18n.first_name = en_first_name
        en_i18n.last_name = _optional_text(en_payload.get("last_name"))
        en_i18n.patronymic = _optional_text(en_payload.get("patronymic"))
        en_i18n.biography = _optional_text(en_payload.get("biography"))

    try:
        db.commit()
        db.refresh(person)
        return person
    except Exception:
        db.rollback()
        raise
