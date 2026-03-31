"""Classificador de mensagens — decide se precisa de LLM ou não."""

import re

from cerebro.core.config import PROJETO_ALIASES


def detectar_projeto(msg: str) -> str | None:
    """Detecta o projeto mencionado na mensagem."""
    msg_lower = msg.lower()
    # Tenta match do mais longo pro mais curto (evita match parcial)
    for alias in sorted(PROJETO_ALIASES.keys(), key=len, reverse=True):
        if alias in msg_lower:
            return PROJETO_ALIASES[alias]
    return None


def _extrair_id(msg: str) -> int | None:
    """Extrai ID numérico da mensagem."""
    match = re.search(r"#?(\d+)", msg)
    return int(match.group(1)) if match else None


def _match(msg: str, patterns: list[str]) -> bool:
    """Verifica se algum pattern está contido na mensagem."""
    msg_lower = msg.lower()
    return any(p in msg_lower for p in patterns)


def _is_simple_query(msg: str) -> bool:
    """Verifica se é uma consulta simples (sem intenção complexa)."""
    complex_markers = [
        "anota", "registra", "manda", "fala pro", "envia", "ajuda",
        "monta", "revisa", "analisa", "compara", "pesquisa", "gera",
        "cria job", "preciso", "delega",
    ]
    msg_lower = msg.lower()
    return not any(m in msg_lower for m in complex_markers)


def _parse_criar_tarefa(msg: str) -> dict | None:
    """Tenta parsear 'cria tarefa: ...' em campos estruturados."""
    match = re.match(
        r"cria(?:r)?\s+tarefa[:\s]+(.+)",
        msg,
        re.IGNORECASE,
    )
    if not match:
        return None

    texto = match.group(1).strip()
    result = {"tarefa": texto, "projeto": None, "prazo": None}

    # Detecta projeto
    projeto = detectar_projeto(texto)
    if projeto:
        result["projeto"] = projeto

    # Detecta "pro/pra/da/do [projeto]"
    proj_match = re.search(r"\b(?:pro|pra|da|do)\s+(\w+)", texto, re.IGNORECASE)
    if proj_match and not result["projeto"]:
        alias = proj_match.group(1).lower()
        if alias in PROJETO_ALIASES:
            result["projeto"] = PROJETO_ALIASES[alias]

    # Detecta prazo simples "até [data]"
    prazo_match = re.search(r"até\s+(.+?)(?:\s*$)", texto, re.IGNORECASE)
    if prazo_match:
        result["prazo_raw"] = prazo_match.group(1).strip()

    return result


def classificar(mensagem: str) -> dict:
    """
    Classifica a mensagem e retorna rota.

    Returns:
        {"handler": "deterministic", "func": "nome_funcao", ...} ou
        {"handler": "agent", "projeto": "slug" | None}
    """
    msg = mensagem.strip()
    msg_lower = msg.lower()

    # 1. Status geral
    if _match(msg, ["status geral", "resumo geral", "como tá tudo", "como ta tudo"]):
        return {"handler": "deterministic", "func": "status_geral"}

    # 2. Atrasadas
    if _match(msg, ["atrasad", "vencid"]):
        return {"handler": "deterministic", "func": "atrasadas"}

    # 3. Top do dia / prioridade
    if _match(msg, ["o que faço", "o que fazer", "o que eu faço", "prioridade", "top 3", "top3"]):
        return {"handler": "deterministic", "func": "top_n_do_dia"}

    # 4. Concluir tarefa
    concluir_match = re.search(
        r"(fiz|conclu[íi]|terminei|feito|pronto)\b.*?(?:tarefa\s*)?#?(\d+)",
        msg_lower,
    )
    if concluir_match:
        task_id = int(concluir_match.group(2))
        return {"handler": "deterministic", "func": "concluir_tarefa", "args": {"id": task_id}}

    # 5. Criar tarefa simples
    parsed = _parse_criar_tarefa(msg)
    if parsed and parsed.get("projeto"):
        return {
            "handler": "deterministic",
            "func": "criar_tarefa",
            "args": {
                "tarefa": parsed["tarefa"],
                "projeto": parsed["projeto"],
            },
        }

    # 6. Review semanal
    if _match(msg, ["review semanal", "resumo semanal", "resumo da semana", "review da semana"]):
        return {"handler": "deterministic", "func": "resumo_semanal"}

    # 7. Delegações
    if _match(msg, ["delegaç", "delegac", "cobranç", "cobranc"]):
        return {"handler": "deterministic", "func": "delegacoes_pendentes"}

    # 8. Consulta simples de projeto
    projeto = detectar_projeto(msg)
    if projeto and _is_simple_query(msg):
        # Queries como "pendências da WIPR", "como tá o ERP", "WIPR"
        if _match(msg, ["pendência", "pendencia", "como tá", "como ta", "status"]) or msg_lower.strip() in PROJETO_ALIASES:
            return {"handler": "deterministic", "func": "pendencias_projeto", "args": {"projeto": projeto}}

    # 9. Fallback → agente LLM
    return {"handler": "agent", "projeto": projeto}
