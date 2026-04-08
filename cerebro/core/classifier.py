"""Classificador de mensagens — decide se precisa de LLM ou não."""

import logging
import re
import unicodedata

from cerebro.core.config import PROJETO_ALIASES

logger = logging.getLogger("cerebro.classifier")


def _normalize(text: str) -> str:
    """Remove acentos e normaliza texto para comparação."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def detectar_projeto(msg: str) -> str | None:
    """Detecta o projeto mencionado na mensagem."""
    msg_lower = msg.lower()
    msg_norm = _normalize(msg)
    # Tenta match do mais longo pro mais curto (evita match parcial)
    for alias in sorted(PROJETO_ALIASES.keys(), key=len, reverse=True):
        if alias in msg_lower or _normalize(alias) in msg_norm:
            return PROJETO_ALIASES[alias]
    return None


def _extrair_id(msg: str) -> int | None:
    """Extrai ID numérico da mensagem."""
    match = re.search(r"#?(\d+)", msg)
    return int(match.group(1)) if match else None


def _match(msg: str, patterns: list[str]) -> bool:
    """Verifica se algum pattern está contido na mensagem (com normalização)."""
    msg_lower = msg.lower()
    msg_norm = _normalize(msg)
    return any(p in msg_lower or _normalize(p) in msg_norm for p in patterns)


def _is_simple_query(msg: str) -> bool:
    """Verifica se é uma consulta simples (sem intenção complexa)."""
    complex_markers = [
        "anota", "registra", "manda", "fala pro", "envia", "ajuda",
        "monta", "revisa", "analisa", "compara", "pesquisa", "gera",
        "cria job", "preciso", "delega", "escreve", "elabora", "prepara",
        "sugere", "recomenda",
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


def _is_only_project_name(msg: str) -> str | None:
    """Verifica se a mensagem é apenas o nome de um projeto."""
    msg_clean = msg.strip().lower().rstrip("?!.")
    if msg_clean in PROJETO_ALIASES:
        return PROJETO_ALIASES[msg_clean]
    return None


def classificar(mensagem: str) -> dict:
    """
    Classifica a mensagem e retorna rota.

    Returns:
        {"handler": "deterministic", "func": "nome_funcao", ...} ou
        {"handler": "agent", "projeto": "slug" | None}
    """
    msg = mensagem.strip()
    msg_lower = msg.lower()

    # 0. Mensagem é apenas nome do projeto → pendências dele
    projeto_direto = _is_only_project_name(msg)
    if projeto_direto:
        result = {"handler": "deterministic", "func": "pendencias_projeto", "args": {"projeto": projeto_direto}}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 1. Resumo financeiro (antes de status_geral para evitar conflito com "resumo")
    if _is_simple_query(msg) and _match(msg, [
        "resumo financeiro", "finanças", "financas", "financeiro",
        "quanto gastei", "gastos do mês", "gastos do mes",
        "quanto entrou", "saldo do mês", "saldo do mes",
        "balanço", "balanco",
    ]):
        result = {"handler": "deterministic", "func": "resumo_financeiro"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 1b. Contas vencidas (antes de atrasadas para evitar conflito com "vencid")
    if _match(msg, ["conta vencida", "contas vencidas", "inadimplente"]):
        result = {"handler": "deterministic", "func": "contas_vencidas"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 1c. Contas a pagar / vencendo
    if _match(msg, [
        "contas a pagar", "tenho que pagar", "preciso pagar",
        "contas vencendo", "vence amanhã", "vence amanha",
        "boleto", "conta de",
    ]):
        result = {"handler": "deterministic", "func": "contas_vencendo"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 2. Status geral
    if _match(msg, [
        "status geral", "resumo geral", "como tá tudo", "como ta tudo",
        "como tão as coisas", "como tao as coisas", "como estão as coisas",
        "como estao as coisas", "visão geral", "visao geral", "overview",
        "me atualiza", "resumo", "como está tudo", "como esta tudo",
        "situação geral", "situacao geral",
    ]):
        result = {"handler": "deterministic", "func": "status_geral"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 2. Atrasadas
    if _match(msg, [
        "atrasad", "vencid", "tem algo atrasado", "algo vencido",
        "tá tudo em dia", "ta tudo em dia", "tudo em dia",
        "em atraso", "prazo vencido",
    ]):
        result = {"handler": "deterministic", "func": "atrasadas"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 3. Top do dia / prioridade
    if _match(msg, [
        "o que faço", "o que fazer", "o que eu faço", "prioridade",
        "top 3", "top3", "top 5", "top5",
        "tarefas de hoje", "o que tenho pra hoje", "o que tenho para hoje",
        "resumo do dia", "meu dia", "por onde começo", "por onde comeco",
        "o que tem pra hoje", "agenda de hoje", "qual a prioridade",
        "quais são minhas tarefas", "quais sao minhas tarefas",
        "o que faço hoje", "o que fazer hoje", "o que eu faço hoje",
    ]):
        result = {"handler": "deterministic", "func": "top_n_do_dia"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 4. Concluir tarefa
    concluir_match = re.search(
        r"(fiz|conclu[íi]|terminei|feito|pronto)\b.*?(?:tarefa\s*)?#?(\d+)",
        msg_lower,
    )
    if concluir_match:
        task_id = int(concluir_match.group(2))
        result = {"handler": "deterministic", "func": "concluir_tarefa", "args": {"id": task_id}}
        logger.info("MSG=%s → handler=%s func=%s id=%d", msg[:80], result["handler"], result.get("func"), task_id)
        return result

    # 4b. Iniciar tarefa
    iniciar_match = re.search(
        r"(comecei|iniciei|to fazendo|estou fazendo|começando|comecando)\b.*?(?:tarefa\s*)?#?(\d+)",
        msg_lower,
    )
    if iniciar_match:
        task_id = int(iniciar_match.group(2))
        result = {"handler": "deterministic", "func": "iniciar_tarefa", "args": {"id": task_id}}
        logger.info("MSG=%s → handler=%s func=%s id=%d", msg[:80], result["handler"], result.get("func"), task_id)
        return result

    # 4c. Bloquear tarefa
    bloquear_match = re.search(
        r"(travei|bloqueei|empacou|parei|bloqueada)\b.*?(?:tarefa\s*)?#?(\d+)",
        msg_lower,
    )
    if bloquear_match:
        task_id = int(bloquear_match.group(2))
        result = {"handler": "deterministic", "func": "bloquear_tarefa", "args": {"id": task_id}}
        logger.info("MSG=%s → handler=%s func=%s id=%d", msg[:80], result["handler"], result.get("func"), task_id)
        return result

    # 4d. Cancelar tarefa
    cancelar_match = re.search(
        r"(cancelei|cancela|desist[ei])\b.*?(?:tarefa\s*)?#?(\d+)",
        msg_lower,
    )
    if cancelar_match:
        task_id = int(cancelar_match.group(2))
        result = {"handler": "deterministic", "func": "cancelar_tarefa", "args": {"id": task_id}}
        logger.info("MSG=%s → handler=%s func=%s id=%d", msg[:80], result["handler"], result.get("func"), task_id)
        return result

    # 5. Criar tarefa simples (agora funciona com ou sem projeto)
    parsed = _parse_criar_tarefa(msg)
    if parsed:
        args = {"tarefa": parsed["tarefa"], "projeto": parsed.get("projeto") or "geral"}
        result = {"handler": "deterministic", "func": "criar_tarefa", "args": args}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 6. Review semanal
    if _match(msg, [
        "review semanal", "resumo semanal", "resumo da semana",
        "review da semana", "como foi a semana", "semanal",
    ]):
        result = {"handler": "deterministic", "func": "resumo_semanal"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 7. Delegações
    if _match(msg, [
        "delegaç", "delegac", "cobranç", "cobranc",
        "cobranças", "cobrancas", "quem tá devendo", "quem ta devendo",
        "sem resposta",
    ]):
        result = {"handler": "deterministic", "func": "delegacoes_pendentes"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 8. Agenda / calendário / eventos
    if _match(msg, [
        "agenda da semana", "agenda semanal", "calendário", "calendario",
        "próximos eventos", "proximos eventos", "eventos da semana",
        "o que tem na agenda", "minha agenda",
    ]):
        result = {"handler": "deterministic", "func": "eventos_semana"}
        logger.info("MSG=%s → handler=%s func=%s", msg[:80], result["handler"], result.get("func"))
        return result

    # 9. Gasto rápido: "gastei 45 no almoço", "paguei 350 de internet"
    gasto_match = re.search(
        r"(?:gastei|paguei|comprei)\s+(?:r?\$\s*)?(\d+(?:[.,]\d{1,2})?)\s+(?:no?|em|de|com|na|pro|pra|reais)?\s*(.*)",
        msg_lower,
    )
    if gasto_match:
        valor_str = gasto_match.group(1).replace(",", ".")
        descricao = gasto_match.group(2).strip().rstrip(".")
        if descricao:
            result = {
                "handler": "deterministic",
                "func": "registrar_gasto",
                "args": {"valor": float(valor_str), "descricao": descricao},
            }
            logger.info("MSG=%s → handler=%s func=%s valor=%.2f", msg[:80], result["handler"], result.get("func"), float(valor_str))
            return result

    # 10. Receita rápida: "recebi 700 da gruta", "entrou 100 do erp"
    receita_match = re.search(
        r"(?:recebi|entrou|veio)\s+(?:r?\$\s*)?(\d+(?:[.,]\d{1,2})?)\s+(?:da|do|de|d[oa]s?)?\s*(.*)",
        msg_lower,
    )
    if receita_match:
        valor_str = receita_match.group(1).replace(",", ".")
        descricao = receita_match.group(2).strip().rstrip(".")
        if descricao:
            result = {
                "handler": "deterministic",
                "func": "registrar_receita",
                "args": {"valor": float(valor_str), "descricao": descricao},
            }
            logger.info("MSG=%s → handler=%s func=%s valor=%.2f", msg[:80], result["handler"], result.get("func"), float(valor_str))
            return result

    # 14. Consulta simples de projeto
    projeto = detectar_projeto(msg)
    if projeto and _is_simple_query(msg):
        if _match(msg, ["pendência", "pendencia", "como tá", "como ta", "status", "como está", "como esta"]):
            result = {"handler": "deterministic", "func": "pendencias_projeto", "args": {"projeto": projeto}}
            logger.info("MSG=%s → handler=%s func=%s projeto=%s", msg[:80], result["handler"], result.get("func"), projeto)
            return result

    # 15. Fallback → agente LLM
    result = {"handler": "agent", "projeto": projeto}
    logger.info("MSG=%s → handler=%s (fallback to LLM)", msg[:80], result["handler"])
    return result
