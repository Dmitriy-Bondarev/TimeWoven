import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes.health import router as health_router

from app.api.routes.bot_webhooks import router as bot_webhooks_router
from app.api.routes.tree import router as tree_router
from app.api.routes.TW_Explorer import router as explorer_router
from app.api.timeline import router as timeline_router
from app.api.routes.admin import router as admin_router
from app.api.routes.media import router as media_router
app = FastAPI(title="TimeWoven")


@app.get("/")
async def root(request: Request):
    family_member_id = request.cookies.get("family_member_id", "").strip()
    if family_member_id:
        return RedirectResponse(url="/family/welcome", status_code=303)

    return RedirectResponse(url="/family/need-access", status_code=303)


@app.get("/login")
async def login():
    return RedirectResponse(url="/family/need-access", status_code=303)


@app.get("/f/{slug}/")
async def family_root(slug: str, request: Request):
    family_member_id = request.cookies.get("family_member_id", "").strip()
    if family_member_id:
        return RedirectResponse(url=f"/f/{slug}/family/welcome", status_code=303)

    return RedirectResponse(url=f"/f/{slug}/family/need-access", status_code=303)





try:
    app.mount(
        "/static",
        StaticFiles(directory="app/web/static"),
        name="static",
    )
except RuntimeError:
    pass

app.include_router(bot_webhooks_router)
# Семейные HTML-страницы (в т.ч. GET/POST /family/memory/new) объявлены в app.api.routes.tree — без prefix.
app.include_router(tree_router)
app.include_router(explorer_router)
app.include_router(timeline_router)
app.include_router(admin_router)
app.include_router(media_router)
app.include_router(health_router)

logger = logging.getLogger(__name__)


@app.on_event("startup")
def _assert_family_memory_new_route() -> None:
    """Помогает поймать 404 в проде, если на сервере устарел tree.py или router не тот."""
    paths = {getattr(r, "path", None) for r in app.routes}
    if "/family/memory/new" not in paths:
        logger.error(
            "TwFamilyRoutes: /family/memory/new is not registered — deploy app.api.routes.tree with family_memory_new_get, then restart the service"
        )


def _ensure_jinja_i18n_globals() -> None:
    """Each module using Jinja2Templates gets its own Environment; register t/ts on all of them."""
    from app.core.i18n import install_jinja_i18n
    from app.api import timeline as timeline_api
    from app.api.routes import TW_Explorer
    from app.api.routes import admin as admin_routes
    from app.api.routes import tree as tree_routes

    install_jinja_i18n(tree_routes.templates)
    install_jinja_i18n(admin_routes.templates)
    install_jinja_i18n(timeline_api.templates)
    install_jinja_i18n(TW_Explorer.TEMPLATES)


_ensure_jinja_i18n_globals()
