"""
View-layer «события» таймлайна поверх family-visible memories (без БД, без миграций).
TW-2026-04-26-B3
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import Memory

_OWN_MEANING_MAX = 280


@dataclass
class TimelineEventView:
    source_memory_id: int
    person_id: int | None
    author_display_name: str
    author_person_href: str
    title: str
    meaning_layer: str
    event_date: str
    event_date_display: str
    status_key: str
    visibility_key: str
    related_stories_count: int


def _memory_title_and_preview(m: Memory) -> tuple[str, str]:
    from app.api.routes import tree as tr

    text = tr._memory_display_text(m)
    if not text or tr._looks_like_technical_blob(text):
        return ("", "")
    first_line = text.split("\n", 1)[0].strip()
    title_src = tr._own_story_line_title_src(first_line)
    display_title = (
        tr._text_excerpt(title_src, tr._OWN_STORY_TITLE_MAX).strip()
        if title_src
        else ""
    )
    if not display_title or not display_title.replace("…", "").strip():
        display_title = "Без заголовка"
    preview = tr._own_memory_body_preview_for_card(text)
    return (display_title, preview)


def _meaning_layer_for_family(m: Memory, title: str, preview: str) -> str:
    from app.api.routes import tree as tr

    raw_ess = (getattr(m, "essence_text", None) or "").strip()
    if raw_ess and not tr._looks_like_technical_blob(raw_ess):
        return tr._text_excerpt(raw_ess, _OWN_MEANING_MAX).strip() or title
    if preview:
        return tr._text_excerpt(preview, _OWN_MEANING_MAX).strip()
    return title


def memory_to_timeline_event_view(
    m: Memory,
    *,
    author_display_name: str | None = None,
) -> TimelineEventView | None:
    from app.api.routes import tree as tr

    text = tr._memory_display_text(m)
    if not text or tr._looks_like_technical_blob(text):
        return None
    title, preview = _memory_title_and_preview(m)
    if not title:
        return None
    meaning = _meaning_layer_for_family(m, title, preview)
    ev_raw = m.created_at
    event_date = (
        (ev_raw or "")
        if isinstance(ev_raw, str)
        else (str(ev_raw) if ev_raw is not None else "")
    )
    raw_author = (author_display_name or "").strip()
    if not raw_author and m.author_id is not None:
        raw_author = f"Персона #{m.author_id}"
    if not raw_author:
        raw_author = "Неизвестный автор"
    author_person_href = (
        f"/family/person/{m.author_id}" if m.author_id is not None else ""
    )
    return TimelineEventView(
        source_memory_id=m.id,
        person_id=m.author_id,
        author_display_name=raw_author,
        author_person_href=author_person_href,
        title=title,
        meaning_layer=meaning,
        event_date=event_date,
        event_date_display=tr._family_timeline_date_display(m.created_at),
        status_key="family.timeline.status.family_ready",
        visibility_key="family.timeline.visibility.family",
        related_stories_count=1,
    )
