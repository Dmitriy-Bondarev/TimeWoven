from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.admin import router as admin_router
from app.api.routes.bot_webhooks import router as bot_webhooks_router
from app.api.routes.tree import router as tree_router
from app.api.routes.TW_Explorer import router as explorer_router
from app.api.timeline import router as timeline_router
app = FastAPI(title="TimeWoven")


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