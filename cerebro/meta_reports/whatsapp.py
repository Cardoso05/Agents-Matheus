"""Cliente Evolution API — envio de texto via WhatsApp."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)


class WhatsAppError(RuntimeError):
    pass


def enviar_texto(numero: str, texto: str) -> dict:
    """Envia mensagem via Evolution API. Lança WhatsAppError em falha."""
    base = os.environ["EVOLUTION_API_URL"].rstrip("/")
    apikey = os.environ["EVOLUTION_API_KEY"]
    instance = os.environ["EVOLUTION_INSTANCE"]
    url = f"{base}/message/sendText/{instance}"

    payload = {"number": numero, "text": texto}
    headers = {"apikey": apikey, "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as e:
        raise WhatsAppError(f"network error: {e}") from e

    if resp.status_code >= 400:
        snippet = resp.text[:300]
        raise WhatsAppError(f"http {resp.status_code}: {snippet}")
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}
