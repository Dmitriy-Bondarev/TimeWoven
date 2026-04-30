import os
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.family_resolver import resolve_family

router = APIRouter()


@router.get("/media/{slug}/{file_path:path}")
def serve_media(slug: str, file_path: str):
    try:
        family = resolve_family(slug)
    except Exception:
        raise HTTPException(status_code=404, detail="Family not found")

    base_path = os.path.join(family["data_path"], "media")

    # FastAPI/Starlette может нормализовать путь; дополнительно запрещаем
    # абсолютные пути и любые parent-traversal сегменты на уровне параметра.
    posix_path = PurePosixPath("/" + file_path.lstrip("/"))
    if ".." in posix_path.parts:
        raise HTTPException(status_code=403, detail="Forbidden")

    full_path = os.path.join(base_path, file_path)

    # защита от выхода за пределы директории
    if not os.path.abspath(full_path).startswith(os.path.abspath(base_path)):
        raise HTTPException(status_code=403, detail="Forbidden")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)
