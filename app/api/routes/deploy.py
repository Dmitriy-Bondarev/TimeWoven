import hashlib
import hmac
import logging
import os
import subprocess

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_github_signature(secret: str, body: bytes, signature: str) -> bool:
    expected = (
        "sha256="
        + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


@router.post("/deploy")
async def deploy(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    # 🚨 1. signature must be present (GitHub webhook contract)
    if not signature:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 🚨 2. secret must be configured server-side
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        logger.error("Deploy endpoint disabled: missing GITHUB_WEBHOOK_SECRET")
        # Avoid 500 loops in GitHub delivery; this is a misconfiguration (service not ready).
        raise HTTPException(
            status_code=503,
            detail="Deploy endpoint is not configured (missing GITHUB_WEBHOOK_SECRET)",
        )

    # 🚨 3. verify HMAC (fail-fast, no side effects)
    if not verify_github_signature(secret, body, signature):
        raise HTTPException(status_code=401, detail="Unauthorized")

    script = "/root/scripts/deploy/update_timewoven.sh"
    try:
        proc = subprocess.Popen(
            [script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        logger.exception("Deploy failed: could not start update script")
        raise HTTPException(status_code=503, detail="Deploy failed to start") from None

    logger.info("Deploy triggered (pid=%s)", getattr(proc, "pid", None))
    return {"status": "ok"}
