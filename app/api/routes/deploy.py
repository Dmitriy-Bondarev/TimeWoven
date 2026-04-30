import hashlib
import hmac
import os
import subprocess

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


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
        raise HTTPException(status_code=403)

    # 🚨 2. secret must be configured server-side
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500)

    # 🚨 3. verify HMAC (fail-fast, no side effects)
    if not verify_github_signature(secret, body, signature):
        raise HTTPException(status_code=403)

    subprocess.Popen(
        ["/root/scripts/deploy/update_timewoven.sh"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return {"status": "deploy started"}
