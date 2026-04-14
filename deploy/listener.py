"""Webhook listener — recebe push do GitHub e dispara deploy."""

import hashlib
import hmac
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="Cérebro Deploy Listener")
logger = logging.getLogger("deploy")

WEBHOOK_SECRET = os.getenv("DEPLOY_WEBHOOK_SECRET", "")
DEPLOY_SCRIPT = Path(__file__).parent / "deploy.sh"
DEPLOY_LOG = Path(__file__).parent / "deploys.log"


def _verify_signature(payload: bytes, signature: str) -> bool:
    """Valida HMAC-SHA256 do GitHub webhook."""
    if not WEBHOOK_SECRET:
        logger.warning("DEPLOY_WEBHOOK_SECRET não configurado — rejeitando webhook")
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook/deploy")
async def handle_webhook(request: Request):
    """Recebe webhook do GitHub e dispara deploy."""
    # 1. Validar assinatura
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()

    if not _verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    # 2. Parsear payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    ref = payload.get("ref", "")

    # 3. Só deploya branch main
    if ref != "refs/heads/main":
        return {"status": "ignorado", "reason": f"Branch {ref} não é main"}

    # 4. Extrair info do commit
    head_commit = payload.get("head_commit", {})
    commit_msg = head_commit.get("message", "sem mensagem")[:100]
    commit_sha = head_commit.get("id", "")[:8]
    pusher = payload.get("pusher", {}).get("name", "desconhecido")

    # 5. Disparar deploy em background
    logger.info(f"Deploy iniciado: {commit_sha} - {commit_msg} (por {pusher})")

    log_file = open(str(DEPLOY_LOG), "a")
    subprocess.Popen(
        ["bash", str(DEPLOY_SCRIPT), commit_sha, commit_msg, pusher],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(DEPLOY_SCRIPT.parent.parent),
    )

    return {
        "status": "deploy_iniciado",
        "commit": commit_sha,
        "message": commit_msg,
        "pusher": pusher,
    }


@app.get("/webhook/health")
async def health():
    """Liveness check."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
