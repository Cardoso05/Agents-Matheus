"""Categorização automática de lançamentos financeiros."""

import re

from cerebro.db.setup import get_connection


# Regras built-in (fallback se não houver regras no banco)
REGRAS_PADRAO = [
    # Alimentação
    (r"\b(ifood|i food|rappi|uber\s*eats|almoço|almoco|jantar|restaurante|padaria|mercado|lanche|café|cafe|comida|pizza|hamburguer|sushi|açaí|acai)\b", "alimentacao", None, 1),
    # Transporte
    (r"\b(uber|99|99pop|combustível|combustivel|gasolina|álcool|alcool|estacionamento|pedagio|pedágio|metro|onibus|ônibus)\b", "transporte", None, 2),
    # Material (engenharia)
    (r"\b(intelbras|furukawa|nexans|systimax|cabo|switch|câmera|camera|nvr|rack|conector|patch\s*panel|cftv|fibra\s*óptica|fibra\s*optica)\b", "material", "engenharia", 1),
    # Infra digital
    (r"\b(hostinger|hostgator|domínio|dominio|servidor|vps|api|anthropic|openai|vercel|aws|digital\s*ocean)\b", "infra", None, 3),
    # Marketing
    (r"\b(meta\s*ads|facebook\s*ads|google\s*ads|campanha|criativos|canva|tráfego|trafego)\b", "marketing", None, 3),
    # Assinaturas
    (r"\b(netflix|spotify|total\s*pass|icloud|youtube\s*premium|amazon\s*prime|chatgpt|claude)\b", "assinatura", "pessoal", 4),
    # Educação
    (r"\b(unifesp|faculdade|livro|curso|apostila|mensalidade\s*facu)\b", "educacao", "pessoal", 4),
    # Saúde
    (r"\b(farmácia|farmacia|academia|bioritmo|médico|medico|dentista|consulta|exame|natação|natacao)\b", "saude", "pessoal", 4),
    # Receita de projeto
    (r"\b(setup|retainer|mensalidade|nf\s*emitida|nota\s*fiscal.*receb)\b", "projeto_receita", None, 5),
    # Receita de serviço
    (r"\b(obra|instalação|instalacao|mão\s*de\s*obra|mao\s*de\s*obra)\b", "servico_receita", None, 5),
    # Serviço (saída)
    (r"\b(frete|terceirizado|diária|diaria|manutenção|manutencao)\b", "servico", None, 5),
]


def categorizar(descricao: str, projeto_hint: str | None = None, conn=None) -> dict:
    """
    Categoriza um lançamento pela descrição.

    Returns:
        {"categoria": str, "projeto": str | None, "confianca": float}
    """
    desc_lower = descricao.lower()

    # 1. Tentar regras do banco primeiro
    conn = conn or get_connection()
    try:
        regras_db = conn.execute(
            "SELECT pattern, categoria, projeto, prioridade FROM regras_categorizacao WHERE ativo = 1 ORDER BY prioridade ASC"
        ).fetchall()
        for regra in regras_db:
            if re.search(regra["pattern"], desc_lower, re.IGNORECASE):
                return {
                    "categoria": regra["categoria"],
                    "projeto": regra["projeto"] or projeto_hint,
                    "confianca": 0.9,
                }
    except Exception:
        pass

    # 2. Regras built-in
    for pattern, categoria, projeto, _ in REGRAS_PADRAO:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return {
                "categoria": categoria,
                "projeto": projeto or projeto_hint,
                "confianca": 0.8,
            }

    # 3. Fallback
    return {
        "categoria": "outros",
        "projeto": projeto_hint or "pessoal",
        "confianca": 0.3,
    }


def inferir_tipo(descricao: str) -> str:
    """Infere se é entrada ou saída pela descrição."""
    desc_lower = descricao.lower()
    marcadores_entrada = ["recebi", "entrou", "veio", "pagamento recebido", "transferência recebida", "pix recebido"]
    if any(m in desc_lower for m in marcadores_entrada):
        return "entrada"
    return "saida"
