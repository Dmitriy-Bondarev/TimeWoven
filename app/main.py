from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.admin import router as admin_router
from app.api.routes.bot_webhooks import router as bot_webhooks_router
from app.api.routes.tree import router as tree_router
from app.api.routes.TW_Explorer import router as explorer_router
from app.api.timeline import router as timeline_router
from app.core.i18n import detect_language, reset_context_lang, set_context_lang
from app.core.theme import get_active_theme_preset
from app.db.session import SessionLocal
app = FastAPI(title="TimeWoven")

@app.middleware("http")
async def tw_request_state_middleware(request: Request, call_next):
    """
    Populate request.state with:
      - i18n_lang (and contextvar) for templates
      - active_theme preset for base layout
    """
    lang = detect_language(request)
    token = set_context_lang(lang)
    request.state.i18n_lang = lang

    db = SessionLocal()
    try:
        request.state.active_theme = get_active_theme_preset(db)
    except Exception:
        request.state.active_theme = "current_dark"
    finally:
        try:
            db.close()
        except Exception:
            pass

    try:
        response = await call_next(request)
        return response
    finally:
        reset_context_lang(token)


@app.get("/")
async def root(request: Request):
    family_member_id = request.cookies.get("family_member_id", "").strip()
    if family_member_id:
        return RedirectResponse(url="/family/welcome", status_code=303)

    return RedirectResponse(url="/who-am-i", status_code=303)


@app.get("/login")
async def login():
    return RedirectResponse(url="/who-am-i", status_code=303)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


try:
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
except RuntimeError:
    pass

app.include_router(admin_router)
app.include_router(bot_webhooks_router)
app.include_router(tree_router)
app.include_router(explorer_router)
app.include_router(timeline_router)