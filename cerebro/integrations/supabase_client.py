"""Integração com Supabase — ponte Cérebro → FinBot."""

import json
import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache

logger = logging.getLogger(__name__)

# Cache do client
_client = None


def _get_client():
    """Retorna client Supabase singleton. None se não configurado."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except ImportError:
        logger.warning("supabase-py não instalado. pip install supabase")
        return None
    except Exception as e:
        logger.error(f"Erro ao conectar Supabase: {e}")
        return None


def is_configured() -> bool:
    """Retorna True se Supabase está configurado."""
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _get_user_id() -> str | None:
    """Retorna o user_id do Matheus no Supabase."""
    return os.getenv("SUPABASE_USER_ID")


# ── Mapeamento de Categorias ────────────────────────────────

# Cérebro categoria → FinBot category name (da tabela categories seed)
CATEGORIA_MAP = {
    "alimentacao": "Restaurante",
    "transporte": "Uber/99",
    "material": "Equipamentos",
    "infra": "Ferramentas/Software",
    "marketing": "Marketing/Tráfego",
    "assinatura": "Streaming",
    "educacao": "Cursos",
    "saude": "Academia",
    "projeto_receita": "Freelance/Projetos",
    "servico_receita": "Freelance/Projetos",
    "servico": "Outros (Despesa)",
    "outros": "Outros (Despesa)",
}

# Cache de category_id por nome (carregado do Supabase)
_category_cache: dict[str, str] = {}


def _get_category_id(categoria_cerebro: str) -> str | None:
    """Busca o UUID da categoria no Supabase. Cache em memória."""
    client = _get_client()
    if not client:
        return None

    finbot_name = CATEGORIA_MAP.get(categoria_cerebro)
    if not finbot_name:
        finbot_name = "Outros (Despesa)"

    # Checar cache
    if finbot_name in _category_cache:
        return _category_cache[finbot_name]

    # Carregar todas as categorias de uma vez
    try:
        result = client.table("categories").select("id, name").is_("user_id", "null").execute()
        for cat in result.data:
            _category_cache[cat["name"]] = cat["id"]

        # Também carregar categorias do user
        user_id = _get_user_id()
        if user_id:
            result2 = client.table("categories").select("id, name").eq("user_id", user_id).execute()
            for cat in result2.data:
                _category_cache[cat["name"]] = cat["id"]

        return _category_cache.get(finbot_name)
    except Exception as e:
        logger.error(f"Erro ao buscar categorias: {e}")
        return None


# ── Transações ───────────────────────────────────────────────

TIPO_MAP = {"saida": "expense", "entrada": "income"}


def inserir_transacao(
    tipo: str,
    valor: float,
    descricao: str,
    categoria_cerebro: str,
    data: str | None = None,
    projeto: str | None = None,
) -> dict | None:
    """Insere uma transação no Supabase (FinBot)."""
    client = _get_client()
    user_id = _get_user_id()
    if not client or not user_id:
        return None

    if data is None:
        data = datetime.now().date().isoformat()

    category_id = _get_category_id(categoria_cerebro)
    finbot_type = TIPO_MAP.get(tipo, "expense")

    row = {
        "user_id": user_id,
        "date": data,
        "amount": abs(valor),
        "description": descricao,
        "clean_description": descricao,
        "type": finbot_type,
        "source": "manual",
        "confidence": 0.85,
        "is_confirmed": True,
        "is_recurring": False,
        "metadata": json.dumps({"projeto": projeto, "origem": "cerebro_telegram"}),
    }
    if category_id:
        row["category_id"] = category_id

    try:
        result = client.table("transactions").insert(row).execute()
        if result.data:
            logger.info(f"Transação inserida no Supabase: {result.data[0]['id']}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Erro ao inserir transação no Supabase: {e}")
        return None


def listar_transacoes(
    mes: str | None = None,
    tipo: str | None = None,
    limite: int = 50,
) -> list[dict]:
    """Lista transações do Supabase."""
    client = _get_client()
    user_id = _get_user_id()
    if not client or not user_id:
        return []

    try:
        query = client.table("transactions").select(
            "id, date, amount, description, type, source, category_id, metadata, categories(name, group_name)"
        ).eq("user_id", user_id).order("date", desc=True).limit(limite)

        if tipo:
            finbot_type = TIPO_MAP.get(tipo, tipo)
            query = query.eq("type", finbot_type)

        if mes:
            # mes = "2026-04" → filter date between start and end of month
            start = f"{mes}-01"
            # End of month: add 1 month
            year, month = int(mes[:4]), int(mes[5:7])
            if month == 12:
                end = f"{year + 1}-01-01"
            else:
                end = f"{year}-{month + 1:02d}-01"
            query = query.gte("date", start).lt("date", end)

        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Erro ao listar transações: {e}")
        return []


def resumo_mes(mes: str | None = None) -> dict | None:
    """Retorna resumo financeiro do mês (entradas, saídas, por categoria)."""
    client = _get_client()
    user_id = _get_user_id()
    if not client or not user_id:
        return None

    if mes is None:
        mes = datetime.now().strftime("%Y-%m")

    try:
        transacoes = listar_transacoes(mes=mes, limite=500)
        if not transacoes:
            return {"entradas": 0, "saidas": 0, "saldo": 0, "por_categoria": []}

        entradas = sum(t["amount"] for t in transacoes if t["type"] == "income")
        saidas = sum(t["amount"] for t in transacoes if t["type"] == "expense")

        # Agrupar por categoria
        cat_totals: dict[str, float] = {}
        for t in transacoes:
            if t["type"] != "expense":
                continue
            cat_name = "Outros"
            if t.get("categories"):
                cat_name = t["categories"]["name"]
            cat_totals[cat_name] = cat_totals.get(cat_name, 0) + t["amount"]

        por_categoria = sorted(
            [{"categoria": k, "total": v} for k, v in cat_totals.items()],
            key=lambda x: x["total"],
            reverse=True,
        )

        return {
            "entradas": entradas,
            "saidas": saidas,
            "saldo": entradas - saidas,
            "por_categoria": por_categoria,
        }
    except Exception as e:
        logger.error(f"Erro ao gerar resumo: {e}")
        return None


# ── Dívidas ──────────────────────────────────────────────────

STATUS_MAP = {"aberto": "active", "pago": "paid_off", "vencido": "active", "cancelado": "paid_off"}


def inserir_divida(
    descricao: str,
    valor: float,
    credor: str | None = None,
    taxa_juros: float = 0,
    parcela_restante: int | None = None,
    dia_vencimento: int | None = None,
    notas: str | None = None,
) -> dict | None:
    """Insere uma dívida no Supabase (FinBot)."""
    client = _get_client()
    user_id = _get_user_id()
    if not client or not user_id:
        return None

    row = {
        "user_id": user_id,
        "name": descricao,
        "creditor": credor,
        "original_amount": abs(valor),
        "current_balance": abs(valor),
        "interest_rate": taxa_juros,
        "minimum_payment": 0,
        "remaining_installments": parcela_restante,
        "due_day": dia_vencimento,
        "status": "active",
        "notes": notas,
    }

    try:
        result = client.table("debts").insert(row).execute()
        if result.data:
            logger.info(f"Dívida inserida no Supabase: {result.data[0]['id']}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Erro ao inserir dívida: {e}")
        return None


def listar_dividas_ativas() -> list[dict]:
    """Lista dívidas ativas do Supabase."""
    client = _get_client()
    user_id = _get_user_id()
    if not client or not user_id:
        return []

    try:
        result = client.table("debts").select("*").eq(
            "user_id", user_id
        ).eq("status", "active").order("due_day").execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Erro ao listar dívidas: {e}")
        return []


def dividas_vencendo(dias: int = 7) -> list[dict]:
    """Retorna dívidas com due_day nos próximos N dias."""
    client = _get_client()
    user_id = _get_user_id()
    if not client or not user_id:
        return []

    try:
        hoje = datetime.now().date()
        dividas = listar_dividas_ativas()

        vencendo = []
        for d in dividas:
            if d.get("due_day"):
                # Calcular próximo vencimento
                dia = d["due_day"]
                prox_venc = hoje.replace(day=min(dia, 28))
                if prox_venc < hoje:
                    # Já passou este mês, considerar próximo
                    if hoje.month == 12:
                        prox_venc = prox_venc.replace(year=hoje.year + 1, month=1)
                    else:
                        prox_venc = prox_venc.replace(month=hoje.month + 1)

                diff = (prox_venc - hoje).days
                if 0 <= diff <= dias:
                    d["_vencimento"] = prox_venc.isoformat()
                    d["_dias_ate"] = diff
                    vencendo.append(d)

        return sorted(vencendo, key=lambda x: x["_dias_ate"])
    except Exception as e:
        logger.error(f"Erro ao buscar dívidas vencendo: {e}")
        return []
