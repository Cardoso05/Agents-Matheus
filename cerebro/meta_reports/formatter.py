"""Render do texto WhatsApp (formatação *negrito*, _itálico_)."""

from __future__ import annotations

import os
from datetime import date

from cerebro.meta_reports.metrics import (
    AccountMetrics,
    CampaignRow,
    comparar,
)


_DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _br_money(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _br_int(v: float) -> str:
    n = int(round(v))
    if n >= 1000:
        return f"{n:,}".replace(",", ".")
    return str(n)


def _short_count(v: float) -> str:
    n = float(v)
    if n >= 1000:
        return f"{n/1000:.1f}".replace(".", ",") + "k"
    return str(int(round(n)))


def _br_pct(v: float) -> str:
    return f"{v:.2f}%".replace(".", ",")


def _date_short(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}"


def _date_dow(d: date) -> str:
    return f"{_date_short(d)} ({_DIAS_SEMANA[d.weekday()]})"


def _conversion_label() -> str:
    return os.environ.get("META_CONVERSION_LABEL", "Conversões")


def _business_name() -> str:
    return os.environ.get("META_REPORT_BUSINESS_NAME", "")


def _line(label_emoji: str, label: str, value: str, delta_label: str | None) -> str:
    base = f"{label_emoji} {label}: {value}"
    if delta_label:
        base += f"  {delta_label}"
    return base


def _format_top(top: list[CampaignRow], conv_label: str) -> list[str]:
    if not top:
        return ["_Nenhuma campanha com resultado no período._"]
    out = []
    for i, c in enumerate(top, 1):
        nome = c.name[:30]
        out.append(f"{i}. {nome} — {_br_money(c.cpa)}")
    return out


def render_daily(
    cur: AccountMetrics,
    prev: AccountMetrics,
    top_cur: list[CampaignRow],
    cur_date: date,
    prev_date: date,
) -> str:
    biz = _business_name()
    titulo_extra = f" — {biz}" if biz else ""
    conv_label = _conversion_label()
    lines: list[str] = []

    lines.append(f"📊 *Meta Ads{titulo_extra} — {_date_dow(cur_date)}*")
    if prev.has_data:
        lines.append(f"_vs {_date_dow(prev_date)}_")
    else:
        lines.append(f"_({_date_dow(prev_date)} sem dados)_")
    lines.append("")

    if not cur.has_data:
        lines.append(f"📭 Nenhuma atividade em {_date_short(cur_date)}.")
        lines.append("Campanhas pausadas?")
        return "\n".join(lines)

    def _maybe_delta(curv, prevv, *, inverted=False):
        if not prev.has_data:
            return None
        return comparar(curv, prevv, inverted=inverted).label

    lines.append(_line("💰", "Investido", _br_money(cur.spend),
                       _maybe_delta(cur.spend, prev.spend)))
    lines.append(_line("👁 ", "Impressões", _short_count(cur.impressions),
                       _maybe_delta(cur.impressions, prev.impressions)))
    cliques = f"{_br_int(cur.link_clicks)} (CTR {_br_pct(cur.ctr_link)})"
    lines.append(_line("🖱 ", "Cliques no link", cliques,
                       _maybe_delta(cur.link_clicks, prev.link_clicks)))
    lines.append(_line("💬", conv_label, _br_int(cur.conversions),
                       _maybe_delta(cur.conversions, prev.conversions)))
    if cur.conversions > 0:
        lines.append(_line("📊", "Custo/resultado", _br_money(cur.cpa),
                           _maybe_delta(cur.cpa, prev.cpa, inverted=True)))
    else:
        lines.append("📊 Custo/resultado: —")

    lines.append("")
    lines.append("*Top campanhas* (menor custo/resultado):")
    lines.extend(_format_top(top_cur, conv_label))
    lines.append("")
    lines.append("_Atribuição da Meta pode ajustar nas próximas 24-48h._")
    return "\n".join(lines)


def render_weekly(
    cur: AccountMetrics,
    prev: AccountMetrics,
    top_cur: list[CampaignRow],
    cur_start: date,
    cur_end: date,
    prev_start: date,
    prev_end: date,
    best_day: tuple[date, AccountMetrics] | None,
    worst_day: tuple[date, AccountMetrics] | None,
) -> str:
    biz = _business_name()
    titulo_extra = f" — {biz}" if biz else ""
    conv_label = _conversion_label()
    lines: list[str] = []

    lines.append(f"📅 *Semanal Meta Ads{titulo_extra}*")
    lines.append(f"{_date_short(cur_start)} a {_date_short(cur_end)}")
    if prev.has_data:
        lines.append(f"_vs {_date_short(prev_start)} a {_date_short(prev_end)}_")
    else:
        lines.append("_(semana anterior sem dados)_")
    lines.append("")

    if not cur.has_data:
        lines.append("📭 Nenhuma atividade na semana.")
        return "\n".join(lines)

    def _maybe_delta(curv, prevv, *, inverted=False):
        if not prev.has_data:
            return None
        return comparar(curv, prevv, inverted=inverted).label

    lines.append(_line("💰", "Investido", _br_money(cur.spend),
                       _maybe_delta(cur.spend, prev.spend)))
    lines.append(_line("💬", conv_label, _br_int(cur.conversions),
                       _maybe_delta(cur.conversions, prev.conversions)))
    if cur.conversions > 0:
        lines.append(_line("📊", "Custo/resultado", _br_money(cur.cpa),
                           _maybe_delta(cur.cpa, prev.cpa, inverted=True)))
    lines.append(_line("🖱 ", "CTR link médio", _br_pct(cur.ctr_link),
                       _maybe_delta(cur.ctr_link, prev.ctr_link)))
    lines.append(_line("👁 ", "Impressões", _short_count(cur.impressions),
                       _maybe_delta(cur.impressions, prev.impressions)))

    if best_day and best_day[1].has_data:
        bd, bm = best_day
        lines.append("")
        lines.append(
            f"🏆 *Melhor dia:* {_date_dow(bd)} — "
            f"{int(bm.conversions)} {conv_label.lower()} / {_br_money(bm.spend)} "
            f"(custo {_br_money(bm.cpa) if bm.conversions else '—'})"
        )
    if worst_day and worst_day[1].has_data and worst_day != best_day:
        wd, wm = worst_day
        custo_w = _br_money(wm.cpa) if wm.conversions else "—"
        lines.append(
            f"📉 *Pior dia:* {_date_dow(wd)} — "
            f"{int(wm.conversions)} {conv_label.lower()} / {_br_money(wm.spend)} "
            f"(custo {custo_w})"
        )

    lines.append("")
    lines.append("*Top campanhas* (menor custo/resultado):")
    lines.extend(_format_top(top_cur, conv_label))

    if prev.has_data:
        lines.append("")
        lines.append(_tendencia(cur, prev))
    return "\n".join(lines)


def _tendencia(cur: AccountMetrics, prev: AccountMetrics) -> str:
    if prev.spend == 0 or prev.conversions == 0:
        return "📈 *Tendência:* primeira semana com dados — sem base de comparação."
    spend_pct = (cur.spend - prev.spend) / prev.spend * 100
    conv_pct = (cur.conversions - prev.conversions) / prev.conversions * 100
    estavel = abs(spend_pct) < 5 and abs(conv_pct) < 5
    if estavel:
        return "➡️ *Tendência:* estável."
    if conv_pct > 0 and spend_pct <= conv_pct:
        return f"🚀 *Tendência:* {conv_pct:+.0f}% resultados com {spend_pct:+.0f}% gasto — eficiência subindo."
    if conv_pct < 0 and spend_pct >= 0:
        return f"⚠️ *Tendência:* {conv_pct:+.0f}% resultados com {spend_pct:+.0f}% gasto — eficiência caindo, vale revisar."
    if conv_pct > 0 and spend_pct > 0:
        return "📈 *Tendência:* escala (+gasto, +resultado)."
    return f"📉 *Tendência:* contração ({spend_pct:+.0f}% gasto, {conv_pct:+.0f}% resultados)."
