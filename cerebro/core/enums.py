"""Fonte única de verdade — enums, emojis e metadados de categorias."""

from enum import StrEnum


# ── Status ─────────────────────────────────────────────────


class StatusPendencia(StrEnum):
    PENDENTE = "pendente"
    CONCLUIDA = "concluida"
    CANCELADA = "cancelada"


class StatusCompromisso(StrEnum):
    ABERTO = "aberto"
    PAGO = "pago"
    VENCIDO = "vencido"
    CANCELADO = "cancelado"


class StatusJob(StrEnum):
    PENDENTE = "pendente"
    EXECUTANDO = "executando"
    CONCLUIDO = "concluido"
    ERRO = "erro"


class StatusLancamento(StrEnum):
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"


# ── Tipos ──────────────────────────────────────────────────


class TipoLancamento(StrEnum):
    ENTRADA = "entrada"
    SAIDA = "saida"


class TipoCompromisso(StrEnum):
    PAGAR = "pagar"
    RECEBER = "receber"


class TipoJob(StrEnum):
    REVISAO_CODIGO = "revisao_codigo"
    PESQUISA = "pesquisa"
    GERACAO_CONTEUDO = "geracao_conteudo"
    ANALISE_DADOS = "analise_dados"
    AUDITORIA = "auditoria"
    RELATORIO = "relatorio"


# ── Projetos ───────────────────────────────────────────────


class ProjetoSlug(StrEnum):
    WIPR = "wipr"
    ERP = "erp"
    ENGENHARIA = "engenharia"
    GRUTA = "gruta"
    FACULDADE = "faculdade"
    GERAL = "geral"
    PESSOAL = "pessoal"


# ── Categorias ─────────────────────────────────────────────


class CategoriaFato(StrEnum):
    SOBRE = "sobre"
    REGRA = "regra"
    META = "meta"
    RESTRICAO = "restricao"


class CategoriaFinanceira(StrEnum):
    ALIMENTACAO = "alimentacao"
    TRANSPORTE = "transporte"
    MATERIAL = "material"
    SERVICO = "servico"
    INFRA = "infra"
    MARKETING = "marketing"
    ASSINATURA = "assinatura"
    EDUCACAO = "educacao"
    SAUDE = "saude"
    PROJETO_RECEITA = "projeto_receita"
    SERVICO_RECEITA = "servico_receita"
    OUTROS = "outros"


# ── Emojis unificados ─────────────────────────────────────


EMOJI_CATEGORIA: dict[str, str] = {
    CategoriaFinanceira.ALIMENTACAO: "🍔",
    CategoriaFinanceira.TRANSPORTE: "🚗",
    CategoriaFinanceira.MATERIAL: "🔧",
    CategoriaFinanceira.SERVICO: "👷",
    CategoriaFinanceira.INFRA: "💻",
    CategoriaFinanceira.MARKETING: "📢",
    CategoriaFinanceira.ASSINATURA: "📦",
    CategoriaFinanceira.EDUCACAO: "📚",
    CategoriaFinanceira.SAUDE: "💊",
    CategoriaFinanceira.PROJETO_RECEITA: "💰",
    CategoriaFinanceira.SERVICO_RECEITA: "🏗️",
    CategoriaFinanceira.OUTROS: "📝",
}

EMOJI_STATUS_JOB: dict[str, str] = {
    StatusJob.PENDENTE: "⏳",
    StatusJob.EXECUTANDO: "🔄",
    StatusJob.CONCLUIDO: "✅",
    StatusJob.ERRO: "❌",
}

EMOJI_STATUS_COMPROMISSO: dict[str, str] = {
    StatusCompromisso.ABERTO: "⏳",
    StatusCompromisso.PAGO: "✅",
    StatusCompromisso.VENCIDO: "🚨",
    StatusCompromisso.CANCELADO: "❌",
}


# ── Metadados de categorias financeiras ────────────────────


CATEGORIAS_META: dict[str, dict] = {
    CategoriaFinanceira.ALIMENTACAO: {
        "tipo": "saida",
        "emoji": "🍔",
        "keywords": ["ifood", "restaurante", "almoço", "jantar", "padaria", "mercado", "lanche"],
    },
    CategoriaFinanceira.TRANSPORTE: {
        "tipo": "saida",
        "emoji": "🚗",
        "keywords": ["uber", "99", "combustível", "gasolina", "estacionamento", "pedágio"],
    },
    CategoriaFinanceira.MATERIAL: {
        "tipo": "saida",
        "emoji": "🔧",
        "keywords": ["intelbras", "furukawa", "cabo", "switch", "câmera", "nvr", "rack"],
    },
    CategoriaFinanceira.SERVICO: {
        "tipo": "saida",
        "emoji": "👷",
        "keywords": ["mão de obra", "diária", "frete", "terceirizado"],
    },
    CategoriaFinanceira.INFRA: {
        "tipo": "saida",
        "emoji": "💻",
        "keywords": ["hostinger", "domínio", "servidor", "vps", "api", "anthropic"],
    },
    CategoriaFinanceira.MARKETING: {
        "tipo": "saida",
        "emoji": "📢",
        "keywords": ["meta ads", "google ads", "facebook", "criativos", "canva"],
    },
    CategoriaFinanceira.ASSINATURA: {
        "tipo": "saida",
        "emoji": "📦",
        "keywords": ["netflix", "spotify", "total pass", "icloud", "canva"],
    },
    CategoriaFinanceira.EDUCACAO: {
        "tipo": "saida",
        "emoji": "📚",
        "keywords": ["unifesp", "faculdade", "livro", "curso"],
    },
    CategoriaFinanceira.SAUDE: {
        "tipo": "saida",
        "emoji": "💊",
        "keywords": ["farmácia", "academia", "médico", "dentista", "natação"],
    },
    CategoriaFinanceira.PROJETO_RECEITA: {
        "tipo": "entrada",
        "emoji": "💰",
        "keywords": ["setup", "mensalidade", "retainer"],
    },
    CategoriaFinanceira.SERVICO_RECEITA: {
        "tipo": "entrada",
        "emoji": "🏗️",
        "keywords": ["obra", "instalação", "nf emitida"],
    },
    CategoriaFinanceira.OUTROS: {
        "tipo": "ambos",
        "emoji": "📝",
        "keywords": [],
    },
}


# ── Validação ──────────────────────────────────────────────


def validate_enum(value: str, enum_class: type[StrEnum], field_name: str) -> str:
    """Valida que o valor pertence ao enum. Retorna o valor ou levanta ValueError."""
    value = value.strip() if isinstance(value, str) else value
    try:
        return enum_class(value)
    except ValueError:
        valid = ", ".join(e.value for e in enum_class)
        raise ValueError(
            f"Valor inválido para {field_name}: '{value}'. Válidos: {valid}"
        )
