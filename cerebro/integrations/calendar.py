"""Integração com Google Calendar."""

import json
import logging
import os
from datetime import datetime, timedelta

from cerebro.db.setup import get_connection

logger = logging.getLogger(__name__)

# Último erro de sync com Google Calendar (para diagnóstico)
_last_google_error: str | None = None

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
    google_id = _sync_create_google(evento)
    if google_id:
        conn.execute(
            "UPDATE eventos SET google_event_id = ? WHERE id = ?",
            (google_id, evento["id"]),
        )
        conn.commit()
        evento = _get_evento(evento["id"], conn)
        logger.info(f"Evento '{titulo}' sincronizado com Google Calendar: {google_id}")

    return evento


def atualizar_evento(id: int, conn=None, **campos) -> dict | None:
    """Atualiza campos de um evento e sincroniza com Google Calendar."""
    conn = conn or get_connection()
    evento = _get_evento(id, conn)
    if not evento:
        return None

    allowed = {"titulo", "data", "hora", "duracao_minutos", "projeto", "notas"}
    updates = {k: v for k, v in campos.items() if k in allowed and v is not None}
    if not updates:
        return evento

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [id]
    conn.execute(f"UPDATE eventos SET {set_clause} WHERE id = ?", values)
    conn.commit()

    evento = _get_evento(id, conn)

    # Sincronizar atualização com Google Calendar
    if evento.get("google_event_id"):
        _sync_update_google(evento)

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
    """Remove um evento local e do Google Calendar."""
    conn = conn or get_connection()
    evento = _get_evento(id, conn)
    if not evento:
        return False

    # Deletar do Google Calendar primeiro
    if evento.get("google_event_id"):
        _sync_delete_google(evento["google_event_id"])

    conn.execute("DELETE FROM eventos WHERE id = ?", (id,))
    conn.commit()
    return True


def _get_evento(id: int, conn) -> dict:
    row = conn.execute("SELECT * FROM eventos WHERE id = ?", (id,)).fetchone()
    return dict(row) if row else {}


# ── Google Calendar Sync ──────────────────────────────────────


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
        logger.warning("Google Calendar libraries not installed. Using local calendar only.")
        return None
    except Exception as e:
        logger.warning(f"Google Calendar auth failed: {e}. Using local calendar only.")
        return None


def _build_google_body(evento: dict) -> dict:
    """Constrói o body para a API do Google Calendar."""
    hora = evento.get("hora") or "09:00"
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
    return body


def _sync_create_google(evento: dict) -> str | None:
    """Cria evento no Google Calendar. Retorna event_id ou None."""
    global _last_google_error
    service = _get_google_service()
    if not service:
        _last_google_error = "Google Calendar não configurado (credenciais ausentes)"
        return None
    try:
        body = _build_google_body(evento)
        result = service.events().insert(calendarId="primary", body=body).execute()
        _last_google_error = None
        return result.get("id")
    except Exception as e:
        _last_google_error = str(e)
        logger.error(f"Erro ao criar no Google Calendar: {e}")
        return None


def _sync_update_google(evento: dict) -> bool:
    """Atualiza evento no Google Calendar."""
    global _last_google_error
    service = _get_google_service()
    if not service:
        return False
    try:
        body = _build_google_body(evento)
        service.events().update(
            calendarId="primary",
            eventId=evento["google_event_id"],
            body=body,
        ).execute()
        logger.info(f"Evento '{evento['titulo']}' atualizado no Google Calendar")
        return True
    except Exception as e:
        _last_google_error = str(e)
        logger.error(f"Erro ao atualizar no Google Calendar: {e}")
        return False


def _sync_delete_google(google_event_id: str) -> bool:
    """Deleta evento do Google Calendar."""
    global _last_google_error
    service = _get_google_service()
    if not service:
        return False
    try:
        service.events().delete(
            calendarId="primary",
            eventId=google_event_id,
        ).execute()
        logger.info(f"Evento {google_event_id} deletado do Google Calendar")
        return True
    except Exception as e:
        _last_google_error = str(e)
        logger.error(f"Erro ao deletar do Google Calendar: {e}")
        return False


# Alias for backwards compatibility
sync_to_google = _sync_create_google


def google_calendar_status() -> dict:
    """Retorna status da conexão com Google Calendar."""
    service = _get_google_service()
    return {
        "connected": service is not None,
        "last_error": _last_google_error,
    }


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
