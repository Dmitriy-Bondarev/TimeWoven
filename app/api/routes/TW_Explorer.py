from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import get_daily_password

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__"}
EXCLUDED_FILES = {".env"}
PREVIEW_EXTENSIONS = {".py", ".html", ".md", ".sql"}
MAX_PREVIEW_CHARS = 200_000

router = APIRouter(prefix="/explorer", tags=["TW Explorer"])


def _is_hidden(item: Path) -> bool:
    if item.name in EXCLUDED_FILES:
        return True
    return any(part in EXCLUDED_DIRS for part in item.parts)


def _build_tree(directory: Path, root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    for entry in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if _is_hidden(entry):
            continue

        relative = str(entry.relative_to(root))
        if entry.is_dir():
            nodes.append(
                {
                    "type": "dir",
                    "name": entry.name,
                    "path": relative,
                    "children": _build_tree(entry, root),
                }
            )
            continue

        suffix = entry.suffix.lower()
        nodes.append(
            {
                "type": "file",
                "name": entry.name,
                "path": relative,
                "previewable": suffix in PREVIEW_EXTENSIONS,
            }
        )

    return nodes


def _read_changelog() -> str:
    changelog_path = PROJECT_ROOT / "CHANGELOG.md"
    if not changelog_path.exists():
        return "CHANGELOG.md не найден."
    return changelog_path.read_text(encoding="utf-8", errors="replace")


@router.get("/get-daily-password")
async def explorer_get_daily_password():
    """Return today's daily password as JSON (no auth required — password alone is the secret)."""
    return {"password": get_daily_password()}


@router.post("/login")
async def explorer_login(
    request: Request,
    from_admin: bool = Query(default=False),
    password: str = Form(...),
):
    expected = get_daily_password()
    if password != expected:
        context: dict[str, Any] = {
            "request": request,
            "authorized": False,
            "from_admin": from_admin,
            "auth_error": "Неверный пароль. Попробуйте ещё раз.",
            "changelog_content": "",
            "tree": [],
            "preview_path": "",
            "preview_content": "",
            "preview_error": "",
        }
        return TEMPLATES.TemplateResponse(
            "site/TWExplorer/explorer_view.html", context, status_code=401
        )

    # Cookie valid until midnight UTC today
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    max_age = int((midnight - now).total_seconds())

    redirect_url = "/explorer/?from_admin=1" if from_admin else "/explorer/"
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key="tw_explorer_session",
        value=expected,
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/", response_class=HTMLResponse)
async def explorer_view(
    request: Request,
    from_admin: bool = Query(default=False),
    file: str | None = Query(default=None),
):
    referer = request.headers.get("referer", "")
    referer_path = urlparse(referer).path if referer else ""
    from_admin = from_admin or referer_path.startswith("/admin")

    expected_password = get_daily_password()
    session_cookie = request.cookies.get("tw_explorer_session")
    authorized = session_cookie == expected_password

    context: dict[str, Any] = {
        "request": request,
        "authorized": authorized,
        "from_admin": from_admin,
        "auth_error": "",
        "changelog_content": "",
        "tree": [],
        "preview_path": "",
        "preview_content": "",
        "preview_error": "",
    }

    if not authorized:
        return TEMPLATES.TemplateResponse("site/TWExplorer/explorer_view.html", context)

    context["changelog_content"] = _read_changelog()
    context["tree"] = _build_tree(PROJECT_ROOT, PROJECT_ROOT)

    if file:
        candidate = (PROJECT_ROOT / file).resolve()
        root_resolved = PROJECT_ROOT.resolve()

        if not str(candidate).startswith(str(root_resolved)):
            context["preview_error"] = "Недопустимый путь для предпросмотра."
        elif not candidate.exists() or not candidate.is_file():
            context["preview_error"] = "Файл не найден."
        elif _is_hidden(candidate):
            context["preview_error"] = "Доступ к этому файлу запрещен."
        elif candidate.suffix.lower() not in PREVIEW_EXTENSIONS:
            context["preview_error"] = "Предпросмотр доступен только для .py, .html, .md, .sql"
        else:
            content = candidate.read_text(encoding="utf-8", errors="replace")
            context["preview_path"] = str(candidate.relative_to(PROJECT_ROOT))
            context["preview_content"] = content[:MAX_PREVIEW_CHARS]
            if len(content) > MAX_PREVIEW_CHARS:
                context["preview_content"] += "\n\n... [обрезано]"

    return TEMPLATES.TemplateResponse("site/TWExplorer/explorer_view.html", context)
