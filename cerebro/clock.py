"""Timezone centralizado — America/Sao_Paulo."""

from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    """Retorna datetime atual no fuso de São Paulo (naive, compatível com timestamps existentes)."""
    return datetime.now(FUSO).replace(tzinfo=None)


def hoje() -> str:
    """Retorna data de hoje em ISO (YYYY-MM-DD) no fuso de SP."""
    return agora().date().isoformat()


def agora_iso() -> str:
    """Retorna datetime atual ISO no fuso de SP."""
    return agora().isoformat()
