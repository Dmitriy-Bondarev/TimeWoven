"""
Minimal YAML-based i18n for TimeWoven (T33 I18N-1).
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Mapping

import yaml
from jinja2 import pass_context
from urllib.parse import quote as _urlquote

# Request-scoped language for Jinja and sync call sites
_current_lang: ContextVar[str] = ContextVar("tw_i18n_lang", default="ru")

_LOCALES_DIR = Path(__file__).resolve().parent.parent.parent / "locales"
_KNOWN_LANGS = frozenset({"ru", "en"})
_KNOWN_NAMESPACES: tuple[str, ...] = ("app", "landing", "family")
_CACHE: dict[tuple[str, str], dict[str, str]] = {}
_SECTION_CACHE: dict[tuple[str, str], dict[str, str]] = {}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _flatten_mapping(data: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, Mapping):
            out.update(_flatten_mapping(v, key))
        elif v is None:
            out[key] = ""
        else:
            out[key] = str(v)
    return out


def _load_namespace_file(lang: str, namespace: str) -> dict[str, str]:
    if lang not in _KNOWN_LANGS or namespace not in _KNOWN_NAMESPACES:
        return {}
    key = (lang, namespace)
    if key in _CACHE:
        return _CACHE[key]
    path = _LOCALES_DIR / lang / f"{namespace}.yml"
    if not path.is_file():
        _CACHE[key] = {}
        return _CACHE[key]
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, Mapping):
        _CACHE[key] = {}
    else:
        _CACHE[key] = _flatten_mapping(data)
    return _CACHE[key]


def get_locale_section(lang: str, section: str) -> dict[str, str]:
    """
    Return a flat dict for a top-level YAML section.

    Example: locales/ru/landing.yml contains:
      landing:
        hero_title: "..."
        ...

    get_locale_section("ru", "landing") -> {"hero_title": "...", ...}

    Fallback: if a key is missing in the requested lang, fall back to ru.
    """
    sec = (section or "").strip().lower()
    if sec not in _KNOWN_NAMESPACES:
        return {}

    def _load(lang_code: str) -> dict[str, str]:
        l = (lang_code or "ru").strip().lower()[:2]
        if l not in _KNOWN_LANGS:
            l = "ru"
        cache_key = (l, sec)
        if cache_key in _SECTION_CACHE:
            return _SECTION_CACHE[cache_key]

        path = _LOCALES_DIR / l / f"{sec}.yml"
        if not path.is_file():
            _SECTION_CACHE[cache_key] = {}
            return _SECTION_CACHE[cache_key]

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, Mapping):
            _SECTION_CACHE[cache_key] = {}
            return _SECTION_CACHE[cache_key]

        raw_section = data.get(sec, {})
        if not isinstance(raw_section, Mapping):
            _SECTION_CACHE[cache_key] = {}
            return _SECTION_CACHE[cache_key]

        out: dict[str, str] = {}
        for k, v in raw_section.items():
            if isinstance(v, Mapping):
                # We intentionally keep section values flat for template usage.
                continue
            out[str(k)] = "" if v is None else str(v)

        _SECTION_CACHE[cache_key] = out
        return out

    requested = _load(lang)
    if (lang or "ru").strip().lower()[:2] == "ru":
        return dict(requested)

    ru = _load("ru")
    merged: dict[str, str] = dict(ru)
    merged.update({k: v for k, v in requested.items() if v is not None})
    return merged


def _lookup_one_lang(lang: str, key: str, namespace: str | None) -> str | None:
    if namespace:
        if namespace not in _KNOWN_NAMESPACES:
            return None
        d = _load_namespace_file(lang, namespace)
        return d.get(key)
    merged: dict[str, str] = {}
    for ns in _KNOWN_NAMESPACES:
        merged.update(_load_namespace_file(lang, ns))
    return merged.get(key)


def t(
    key: str,
    lang: str = "ru",
    namespace: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Return translated string. If missing in *lang*, fall back to *ru*; if still missing, return *key*.
    """
    # Compatibility: allow keys like "app.nav.home" (namespace-prefixed) without
    # changing YAML shape. If namespace is not explicitly provided and the key
    # begins with a known namespace, treat it as namespace selection.
    if namespace is None:
        k = (key or "").strip()
        if "." in k:
            prefix, rest = k.split(".", 1)
            if prefix in _KNOWN_NAMESPACES and rest:
                namespace = prefix
                key = rest
    l = (lang or "ru").strip()[:2].lower() if (lang or "").strip() else "ru"
    if l not in _KNOWN_LANGS:
        l = "ru"
    s = _lookup_one_lang(l, key, namespace)
    if s is None and l != "ru":
        s = _lookup_one_lang("ru", key, namespace)
    if s is None:
        s = key
    if not kwargs:
        return s
    try:
        return s.format(**kwargs)
    except (KeyError, ValueError, IndexError):
        return s


def translate(
    key: str,
    lang: str | None = None,
    namespace: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Thin wrapper over t() for Python-side usage.

    Supports keys like:
      - "app.family_access.invalid_code"
      - "timeline.empty" with namespace="app"
    Falls back to ru and finally returns key if missing.
    """
    return t(
        key=key,
        lang=(lang or "ru"),
        namespace=namespace,
        **kwargs,
    )


def detect_language_from_path(path: str) -> str | None:
    p = (path or "").split("?", 1)[0] or "/"
    if p == "/en" or p.startswith("/en/"):
        return "en"
    return None


def _cookie_lang(request) -> str | None:
    raw = (request.cookies.get("tw_lang") or "").strip().lower()[:2]
    if raw in _KNOWN_LANGS:
        return raw
    return None


def _accept_header_lang(accept: str) -> str | None:
    h = (accept or "").lower()
    if not h:
        return None
    # Prefer the first en or ru in the order listed (simplified)
    for part in h.split(","):
        tag = (part.split(";")[0] or "").strip()
        m = re.match(r"^([a-zA-Z]+)", tag)
        if not m:
            continue
        code = m.group(1).lower()[:2]
        if code == "en":
            return "en"
        if code == "ru":
            return "ru"
    return None


def detect_language(request) -> str:
    """
    Priority: tw_lang cookie (ru|en) → /en/ URL prefix → Accept-Language → default ru.
    """
    c = _cookie_lang(request)
    if c is not None:
        return c
    p = request.url.path if hasattr(request, "url") else (request.get("path") or "/")
    from_path = detect_language_from_path(p)
    if from_path is not None:
        return from_path
    if hasattr(request, "headers"):
        ac = _accept_header_lang(request.headers.get("accept-language", ""))
        if ac is not None:
            return ac
    return "ru"


def get_current_lang() -> str:
    return _current_lang.get()


def set_context_lang(lang: str) -> object:
    """Returns a context token to reset; usually done in middleware only."""
    l = (lang or "ru").strip().lower()[:2]
    if l not in _KNOWN_LANGS:
        l = "ru"
    return _current_lang.set(l)


def reset_context_lang(token: object) -> None:
    _current_lang.reset(token)


@pass_context
def jinja_t(
    context: Any,
    key: str,
    namespace: str | None = None,
    lang: str | None = None,
    **kwargs: Any,
) -> str:
    if lang is None:
        request = context.get("request")
        if request is not None:
            lang = getattr(request.state, "i18n_lang", None)
        if lang is None:
            lang = get_current_lang()
    return t(key, lang=lang or "ru", namespace=namespace, **kwargs)


@pass_context
def jinja_ts(
    context: Any,
    key: str,
    default: str = "",
    namespace: str | None = None,
    lang: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Safe translate for UI labels: never return raw technical key to templates.

    If translation is missing (resolved value equals the key), returns *default* (or empty string).
    """
    resolved = jinja_t(context, key, namespace=namespace, lang=lang, **kwargs)
    if not resolved or resolved == key:
        return str(default or "")
    return resolved


def jinja_current_lang() -> str:
    """Current UI language; use in templates: {{ current_lang() }}."""
    return get_current_lang()


def _tw_path_quote(path: str | None) -> str:
    return _urlquote((path or "")[:2048] or "/", safe="/")


def install_jinja_i18n(templates) -> None:
    """Register t() and current_lang on a Jinja2 environment (idempotent per env)."""
    env = templates.env
    if getattr(env, "_tw_i18n_jinja", False):
        return
    env.globals["t"] = jinja_t
    env.globals["ts"] = jinja_ts
    env.globals["current_lang"] = jinja_current_lang
    env.filters["tw_path_quote"] = _tw_path_quote
    env._tw_i18n_jinja = True  # type: ignore[attr-defined]


def safe_next_path(next_url: str | None, default: str = "/") -> str:
    """
    Only allow same-origin path redirects. Avoid open-redirects (http:, //evil, \\).
    """
    raw = (next_url or "").strip()
    if not raw or not raw.startswith("/"):
        return default
    if raw.startswith("//"):
        return default
    if "://" in raw:
        return default
    if "\\" in raw or "\0" in raw:
        return default
    return raw


def get_locales_dir() -> Path:
    return _LOCALES_DIR
