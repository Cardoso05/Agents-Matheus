"""Integração com Google Calendar."""

import json
import logging
import os
from datetime import datetime, timedelta

from cerebro.db.setup import get_connection

logger = logging.getLogger(__name__)

# ── CRUD de eventos ─────────────────────────────────────────


def criar_evento(
    titulo: str,
    data: str,
    hora: str | None = None,
    duracao_minutos: int = 60,
    projeto: str | None = None,
    notas: str | None = None,
    conn=None,
) -> dict:
    """Cria um evento no calendário local e sincroniza com Google Calendar."""
    conn = conn or get_connection()
    cursor = conn.execute(
        """INSERT INTO eventos (titulo, data, hora, duracao_minutos, projeto, notas)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (titulo, data, hora, duracao_minutos, projeto, notas),
    )
    conn.commit()
    evento = _get_evento(cursor.lastrowid, conn)

    # Sincronizar com Google Calendar
    google_id = sync_to_google(evento)
    if google_id:
        conn.execute(
            "UPDATE eventos SET google_event_id = ? WHERE id = ?",
            (google_id, evento["id"]),
        )
        conn.commit()
        evento = _get_evento(evento["id"], conn)
        logger.info(f"Evento '{titulo}' sincronizado com Google Calendar: {google_id}")

    return evento


def listar_eventos(
    data_inicio: str | None = None,
    data_fim: str | None = None,
    projeto: str | None = None,
    conn=None,
) -> list[dict]:
    """Lista eventos do calendário."""
    conn = conn or get_connection()
    query = "SELECT * FROM eventos WHERE 1=1"
    params = []

    if data_inicio:
        query += " AND data >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND data <= ?"
        params.append(data_fim)
    if projeto:
        query += " AND projeto = ?"
        params.append(projeto)

    query += " ORDER BY data ASC, hora ASC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def eventos_do_dia(data: str | None = None, conn=None) -> list[dict]:
    """Retorna eventos de um dia específico (default: hoje)."""
    if data is None:
        data = datetime.now().date().isoformat()
    return listar_eventos(data_inicio=data, data_fim=data, conn=conn)


def eventos_da_semana(conn=None) -> list[dict]:
    """Retorna eventos da semana atual."""
    hoje = datetime.now().date()
    # Início da semana (segunda)
    inicio = hoje - timedelta(days=hoje.weekday())
    fim = inicio + timedelta(days=6)
    return listar_eventos(
        data_inicio=inicio.isoformat(),
        data_fim=fim.isoformat(),
        conn=conn,
    )


def deletar_evento(id: int, conn=None) -> bool:
    """Remove um evento."""
    conn = conn or get_connection()
    cursor = conn.execute("DELETE FROM eventos WHERE id = ?", (id,))
    conn.commit()
    return cursor.rowcount > 0


def _get_evento(id: int, conn) -> dict:
    row = conn.execute("SELECT * FROM eventos WHERE id = ?", (id,)).fetchone()
    return dict(row) if row else {}


# ── Google Calendar (quando configurado) ────────────────────


def _get_google_service():
    """
    Retorna o serviço do Google Calendar se as credenciais existirem.
    Requer: google-api-python-client, google-auth-oauthlib
    """
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    token_path = os.getenv("GOOGLE_TOKEN_PATH")

    if not creds_path or not os.path.exists(creds_path):
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/calendar"]
        creds = None

        if token_path and os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            if token_path:
                with open(token_path, "w") as f:
                    f.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)
    except ImportError:
        logger.debug("Google Calendar libraries not installed. Using local calendar only.")
        return None
    except Exception as e:
        logger.warning(f"Google Calendar auth failed: {e}. Using local calendar only.")
        return None


def sync_to_google(evento: dict) -> str | None:
    """Tenta sincronizar evento com Google Calendar. Retorna event_id ou None."""
    service = _get_google_service()
    if not service:
        return None

    try:
        hora = evento.get("hora", "09:00")
        data = evento["data"]
        duracao = evento.get("duracao_minutos", 60)

        start_dt = datetime.fromisoformat(f"{data}T{hora}:00")
        end_dt = start_dt + timedelta(minutes=duracao)

        body = {
            "summary": evento["titulo"],
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/Sao_Paulo"},
        }
        if evento.get("notas"):
            body["description"] = evento["notas"]

        result = service.events().insert(calendarId="primary", body=body).execute()
        return result.get("id")
    except Exception as e:
        logger.error(f"Erro ao sincronizar com Google Calendar: {e}")
        return None


# ── Formatação ──────────────────────────────────────────────


def formatar_eventos(eventos: list[dict]) -> str:
    """Formata lista de eventos para exibição."""
    if not eventos:
        return "Nenhum evento encontrado."

    lines = []
    data_atual = None
    for ev in eventos:
        if ev["data"] != data_atual:
            data_atual = ev["data"]
            lines.append(f"\n📅 **{data_atual}**")
        hora = ev.get("hora") or "dia todo"
        duracao = ev.get("duracao_minutos", 60)
        projeto = f" [{ev['projeto'].upper()}]" if ev.get("projeto") else ""
        lines.append(f"  • {hora} ({duracao}min) — {ev['titulo']}{projeto}")

    return "\n".join(lines)
