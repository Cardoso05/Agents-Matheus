"""Texto WhatsApp simplificado pro cliente (Nicolas).

Sem CPR por campanha, sem frequência, sem nomes técnicos, sem emojis de severidade,
sem 'PAUSAR/ESCALAR/TROCAR_CRIATIVO'. Linguagem direta, foco em resultado.
"""

from __future__ import annotations

import os
from datetime import date

from cerebro.meta_optimizer.rules import Action
from cerebro.meta_reports.metrics import _action_value, _f

_DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

# Marcas conhecidas — ordem importa: a primeira que casar vence.
_BRANDS = ["JACK", "SIRUBA", "ZOJE", "CARO", "ENGAJ"]


def _conv_type() -> str:
    return os.environ.get(
        "META_CONVERSION_ACTION_TYPE",
        "onsite_conversion.messaging_conversation_started_7d",
    )


def _br_money(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _br_int(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def _bucket_brand(name: str) -> str:
    up = (name or "").upper()
    for b in _BRANDS:
        if b in up:
            return b
    return "GERAL"


def _results(row: dict) -> int:
    return int(_action_value(row.get("actions"), _conv_type()))


def _spend(row: dict) -> float:
    return _f(row.get("spend"))


def _agg(rows: list[dict]) -> tuple[float, int, float]:
    """Retorna (spend, results, cpr)."""
    spend = sum(_spend(r) for r in rows)
    results = sum(_results(r) for r in rows)
    cpr = (spend / results) if results > 0 else 0.0
    return spend, results, cpr


def _brand_breakdown(rows: list[dict]) -> list[tuple[str, int, float]]:
    """Retorna lista [(marca, results, spend)] ordenada por results desc."""
    bucket: dict[str, dict[str, float]] = {}
    for r in rows:
        brand = _bucket_brand(r.get("campaign_name", ""))
        b = bucket.setdefault(brand, {"results": 0, "spend": 0.0})
        b["results"] += _results(r)
        b["spend"] += _spend(r)
    out = [(k, int(v["results"]), v["spend"]) for k, v in bucket.items() if v["results"] > 0]
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def _action_phrase(actions: list[Action]) -> str:
    types = {a.type for a in actions if a.type != Action.MANTER}
    phrases: list[str] = []
    if Action.TROCAR_CRIATIVO in types:
        phrases.append("Renovando criativos pra manter os resultados")
    if Action.ESCALAR in types:
        phrases.append("Aumentando investimento nas campanhas que mais trazem resultado")
    if Action.REDUZIR in types:
        phrases.append("Otimizando a distribuição de investimento entre campanhas")
    if Action.PAUSAR in types:
        phrases.append("Reorganizando campanhas pra focar no que funciona melhor")
    if not phrases:
        return "Monitorando performance e mantendo as otimizações ativas."
    return ".\n".join(phrases[:2]) + "."


def _variation_label(cur_cpr: float, prev_cpr: float) -> str:
    if prev_cpr <= 0 or cur_cpr <= 0:
        return ""
    pct = (cur_cpr - prev_cpr) / prev_cpr * 100
    if abs(pct) < 2.0:
        return "  ➡️ estável"
    if pct < 0:
        return f"  📉 melhorou {abs(pct):.1f}%"
    return f"  📈 subiu {pct:.1f}%"


def _date_dow(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d} ({_DIAS[d.weekday()]})"


def _business() -> str:
    return os.environ.get("META_REPORT_BUSINESS_NAME", "")


def render_client_daily(
    cur_camp: list[dict],
    prev_camp: list[dict],
    actions: list[Action],
    cur_date: date,
    prev_date: date,
) -> str:
    cur_spend, cur_results, cur_cpr = _agg(cur_camp)
    _, _, prev_cpr = _agg(prev_camp or [])

    biz = _business()
    titulo = f"📊 *{biz} — Relatório {_date_dow(cur_date)}*" if biz else f"📊 *Relatório {_date_dow(cur_date)}*"

    lines: list[str] = []
    lines.append(titulo)
    lines.append("")

    if cur_results == 0:
        lines.append("Ontem não chegaram contatos novos pelas campanhas.")
        lines.append(f"Investido: {_br_money(cur_spend)}.")
        lines.append("")
        lines.append("Já estou ajustando aqui pra retomar o ritmo. Qualquer dúvida, chama! 📲")
        return "\n".join(lines)

    var = _variation_label(cur_cpr, prev_cpr)
    lines.append(f"💰 Investido ontem: {_br_money(cur_spend)}")
    lines.append(f"💬 Pessoas que chamaram: {_br_int(cur_results)}")
    lines.append(f"📊 Custo por contato: {_br_money(cur_cpr)}{var}")
    lines.append("")

    breakdown = _brand_breakdown(cur_camp)
    if breakdown:
        best_brand, best_results, _ = breakdown[0]
        lines.append(f"✅ Melhor marca: *{best_brand}* — {_br_int(best_results)} contatos")
        lines.append("")
        if len(breakdown) > 1:
            lines.append("📋 *Por marca:*")
            for brand, results, _ in breakdown:
                lines.append(f"   • {brand}: {_br_int(results)} contatos")
            lines.append("")

    lines.append("🔧 *O que estamos fazendo:*")
    lines.append(_action_phrase(actions))
    lines.append("")
    lines.append("Qualquer dúvida, chama! 📲")
    return "\n".join(lines)


def render_client_weekly(
    cur_camp: list[dict],
    prev_camp: list[dict],
    actions: list[Action],
    cur_start: date,
    cur_end: date,
) -> str:
    cur_spend, cur_results, cur_cpr = _agg(cur_camp)
    _, _, prev_cpr = _agg(prev_camp or [])

    biz = _business()
    periodo = f"{cur_start.day:02d}/{cur_start.month:02d} a {cur_end.day:02d}/{cur_end.month:02d}"
    titulo = f"📅 *{biz} — Resumo da semana*" if biz else "📅 *Resumo da semana*"

    lines: list[str] = []
    lines.append(titulo)
    lines.append(f"_{periodo}_")
    lines.append("")

    if cur_results == 0:
        lines.append("Semana sem contatos pelas campanhas.")
        lines.append(f"Investido: {_br_money(cur_spend)}.")
        lines.append("")
        lines.append("Já estou ajustando. Qualquer dúvida, chama! 📲")
        return "\n".join(lines)

    var = _variation_label(cur_cpr, prev_cpr)
    lines.append(f"💰 Investido na semana: {_br_money(cur_spend)}")
    lines.append(f"💬 Total de contatos: {_br_int(cur_results)}")
    lines.append(f"📊 Custo por contato: {_br_money(cur_cpr)}{var}")
    lines.append("")

    breakdown = _brand_breakdown(cur_camp)
    if breakdown:
        best_brand, best_results, _ = breakdown[0]
        lines.append(f"✅ Marca destaque: *{best_brand}* — {_br_int(best_results)} contatos")
        lines.append("")
        if len(breakdown) > 1:
            lines.append("📋 *Distribuição por marca:*")
            for brand, results, _ in breakdown:
                lines.append(f"   • {brand}: {_br_int(results)} contatos")
            lines.append("")

    lines.append("🔧 *Próximos passos:*")
    lines.append(_action_phrase(actions))
    lines.append("")
    lines.append("Qualquer dúvida, chama! 📲")
    return "\n".join(lines)
