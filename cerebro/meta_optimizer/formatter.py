"""Formatação WhatsApp do bloco de análise (anexado ao relatório do meta_reports)."""

from __future__ import annotations

from cerebro.meta_optimizer.config import Config
from cerebro.meta_optimizer.rules import Action


class WhatsAppFormatter:
    @staticmethod
    def format_daily(summary: dict, actions: list[Action]) -> str:
        lines: list[str] = []
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚡ *ANÁLISE AUTOMÁTICA*")
        lines.append("")
        lines.append(f"🏥 *Saúde da conta:* {summary['health']}")
        lines.append(f"📊 *CPR médio:* R$ {summary['avg_cpr']:.2f}")

        if summary["cpr_variation"] is not None:
            direction = "📈" if summary["cpr_variation"] > 0 else "📉"
            label = "_(pior)_" if summary["cpr_variation"] > 0 else "_(melhor)_"
            lines.append(f"   {direction} {abs(summary['cpr_variation']):.1%} vs anterior {label}")

        lines.append("")

        if summary["best_campaign"]:
            b = summary["best_campaign"]
            lines.append(f"✅ *Melhor:* {b.name}")
            lines.append(f"   CPR R$ {b.cpr:.2f} — {b.results} conversas")
        if summary["worst_campaign"] and summary["worst_campaign"] is not summary["best_campaign"]:
            w = summary["worst_campaign"]
            lines.append(f"⚠️ *Pior:* {w.name}")
            lines.append(f"   CPR R$ {w.cpr:.2f} — {w.results} conversas")
        lines.append("")

        urgent = [a for a in actions if a.priority <= 4]
        if urgent:
            lines.append("⚡ *AÇÕES:*")
            lines.append("")
            for a in urgent:
                lines.append(f"{a.emoji} *{a.type}* — {a.campaign}")
                lines.append(f"   _{a.reason}_")
                if a.detail:
                    lines.append(f"   → {a.detail}")
                lines.append("")

        monitor = [a for a in actions if a.priority > 4 and a.type != Action.MANTER]
        if monitor:
            lines.append("👀 *Monitorar:*")
            for a in monitor:
                lines.append(f"   • {a.campaign}: _{a.reason}_")
            lines.append("")

        return "\n".join(lines).rstrip()

    @staticmethod
    def format_weekly(summary: dict, actions: list[Action], trend: list[dict]) -> str:
        lines: list[str] = []
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 *ANÁLISE SEMANAL*")
        lines.append("")
        lines.append(f"🏥 *Saúde:* {summary['health']}")
        lines.append(f"📊 *CPR médio:* R$ {summary['avg_cpr']:.2f}")
        lines.append(f"💬 *Conversas:* {summary['total_results']}")
        lines.append(f"💰 *Gasto:* R$ {summary['total_spend']:.2f}")
        lines.append("")

        if trend:
            lines.append("📈 *Tendência (últimos 7 dias):*")
            for day in reversed(trend[:7]):
                cpr = day["cpr"] or 0.0
                if cpr <= Config.CPR_EXCELENTE:
                    dot = "🟢"
                elif cpr <= Config.CPR_BOM:
                    dot = "🟡"
                elif cpr <= Config.CPR_ATENCAO:
                    dot = "🟠"
                else:
                    dot = "🔴"
                lines.append(f"   {day['date']}: {dot} R$ {cpr:.2f} — {day['results']} conv")
            lines.append("")

        urgent = [a for a in actions if a.type != Action.MANTER]
        if urgent:
            lines.append("⚡ *AÇÕES DA SEMANA:*")
            lines.append("")
            for a in urgent:
                lines.append(f"{a.emoji} *{a.type}* — {a.campaign}")
                lines.append(f"   _{a.reason}_")
                lines.append("")

        return "\n".join(lines).rstrip()
