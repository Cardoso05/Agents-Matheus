"""Motor de regras determinísticas + sumário de saúde da conta."""

from __future__ import annotations

from typing import Optional

from cerebro.meta_optimizer.config import Config
from cerebro.meta_optimizer.models import CampaignSnapshot


class Action:
    ESCALAR = "ESCALAR"
    MANTER = "MANTER"
    MONITORAR = "MONITORAR"
    REDUZIR = "REDUZIR"
    PAUSAR = "PAUSAR"
    TROCAR_CRIATIVO = "TROCAR_CRIATIVO"
    REATIVAR = "REATIVAR"

    PRIORITY = {
        "PAUSAR": 1,
        "TROCAR_CRIATIVO": 2,
        "REDUZIR": 3,
        "ESCALAR": 4,
        "REATIVAR": 5,
        "MONITORAR": 6,
        "MANTER": 7,
    }

    EMOJI = {
        "ESCALAR": "🟢",
        "MANTER": "⚪",
        "MONITORAR": "🟡",
        "REDUZIR": "🟠",
        "PAUSAR": "🔴",
        "TROCAR_CRIATIVO": "🔵",
        "REATIVAR": "🟣",
    }

    def __init__(self, action_type: str, campaign: str, reason: str, detail: str = ""):
        self.type = action_type
        self.campaign = campaign
        self.reason = reason
        self.detail = detail
        self.priority = self.PRIORITY.get(action_type, 99)
        self.emoji = self.EMOJI.get(action_type, "⚪")


class RulesEngine:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def evaluate(
        self,
        today: list[CampaignSnapshot],
        yesterday: Optional[list[CampaignSnapshot]] = None,
    ) -> list[Action]:
        actions: list[Action] = []
        yesterday_map = {c.name: c for c in yesterday} if yesterday else {}

        active = [
            c for c in today
            if c.results >= self.config.MIN_RESULTADOS
            and c.spend >= self.config.MIN_GASTO
        ]

        if not active:
            return [Action(Action.MONITORAR, "CONTA", "Sem dados suficientes para análise")]

        total_spend = sum(c.spend for c in active)
        total_results = sum(c.results for c in active)
        avg_cpr = total_spend / total_results if total_results > 0 else float("inf")

        for camp in active:
            camp_actions: list[Action] = []

            # REGRA 1: CPR absoluto
            if camp.cpr <= self.config.CPR_EXCELENTE:
                camp_actions.append(Action(
                    Action.ESCALAR, camp.name,
                    f"CPR R$ {camp.cpr:.2f} — excelente",
                    "Aumentar orçamento 20-30%. Não mexer nos criativos.",
                ))
            elif camp.cpr >= self.config.CPR_CRITICO:
                camp_actions.append(Action(
                    Action.PAUSAR, camp.name,
                    f"CPR R$ {camp.cpr:.2f} — crítico (>{self.config.CPR_CRITICO:.0f})",
                    "Pausar campanha. Só reativar com criativos 100% novos.",
                ))
            elif camp.cpr >= self.config.CPR_ATENCAO:
                camp_actions.append(Action(
                    Action.REDUZIR, camp.name,
                    f"CPR R$ {camp.cpr:.2f} — acima do aceitável",
                    "Reduzir orçamento 30-50%. Testar criativos novos.",
                ))

            # REGRA 2: Variação vs período anterior
            if camp.name in yesterday_map:
                prev = yesterday_map[camp.name]
                if prev.cpr > 0 and prev.cpr != float("inf"):
                    variacao = (camp.cpr - prev.cpr) / prev.cpr
                    if variacao >= self.config.VARIACAO_URGENTE:
                        camp_actions.append(Action(
                            Action.TROCAR_CRIATIVO, camp.name,
                            f"CPR subiu {variacao:.0%} vs anterior (R$ {prev.cpr:.2f} → R$ {camp.cpr:.2f})",
                            "Piora forte. Pausar criativo mais caro e subir variação nova.",
                        ))
                    elif variacao >= self.config.VARIACAO_ALERTA:
                        camp_actions.append(Action(
                            Action.MONITORAR, camp.name,
                            f"CPR subiu {variacao:.0%} vs anterior",
                            "Se piorar de novo, trocar criativos.",
                        ))
                    elif variacao <= self.config.VARIACAO_ESCALAR and camp.cpr <= self.config.CPR_BOM:
                        camp_actions.append(Action(
                            Action.ESCALAR, camp.name,
                            f"CPR melhorou {abs(variacao):.0%} vs anterior",
                            "Tendência positiva. Considerar aumentar orçamento.",
                        ))

            # REGRA 3: Frequência
            if camp.frequency >= self.config.FREQUENCIA_FADIGA:
                camp_actions.append(Action(
                    Action.TROCAR_CRIATIVO, camp.name,
                    f"Frequência {camp.frequency:.1f} — fadiga confirmada",
                    "Criativos saturados. Trocar imediatamente.",
                ))
            elif camp.frequency >= self.config.FREQUENCIA_ALERTA:
                camp_actions.append(Action(
                    Action.MONITORAR, camp.name,
                    f"Frequência {camp.frequency:.1f} — fadiga começando",
                    "Preparar criativos novos pra próxima semana.",
                ))

            # REGRA 4: Concentração de budget
            budget_share = camp.spend / total_spend if total_spend > 0 else 0
            if budget_share > self.config.MAX_BUDGET_SHARE and camp.cpr > avg_cpr:
                camp_actions.append(Action(
                    Action.REDUZIR, camp.name,
                    f"Consome {budget_share:.0%} do budget com CPR acima da média",
                    "Redistribuir verba pra campanhas mais eficientes.",
                ))

            # REGRA 5: CPR >2x média da conta
            if camp.cpr > avg_cpr * 2 and avg_cpr > 0:
                camp_actions.append(Action(
                    Action.PAUSAR, camp.name,
                    f"CPR R$ {camp.cpr:.2f} = {camp.cpr/avg_cpr:.1f}x a média (R$ {avg_cpr:.2f})",
                    "Muito acima da média. Pausar e reformular.",
                ))

            if camp_actions:
                camp_actions.sort(key=lambda a: a.priority)
                actions.append(camp_actions[0])
            else:
                actions.append(Action(
                    Action.MANTER, camp.name,
                    f"CPR R$ {camp.cpr:.2f} — dentro da faixa aceitável",
                    "Continuar monitorando.",
                ))

        # Campanhas not_delivering/inativas com gasto
        for camp in today:
            if camp.status.upper() in ("NOT_DELIVERING", "INACTIVE", "PAUSED"):
                if camp.spend > 0 and camp.results < self.config.MIN_RESULTADOS:
                    actions.append(Action(
                        Action.PAUSAR, camp.name,
                        f"Status: {camp.status} com gasto R$ {camp.spend:.2f} e {camp.results} resultados",
                        "Campanha não entrega. Pausar e redistribuir verba.",
                    ))

        actions.sort(key=lambda a: a.priority)
        return actions

    def generate_summary(
        self,
        today: list[CampaignSnapshot],
        yesterday: Optional[list[CampaignSnapshot]] = None,
    ) -> dict:
        # CPR médio = gasto total / resultados totais da conta (mesma base do
        # "Custo/resultado" do relatório principal). Filtro de MIN_* só vale
        # pras regras de ação, não pra média de saúde.
        total_spend = sum(c.spend for c in today)
        total_results = sum(c.results for c in today)
        avg_cpr = total_spend / total_results if total_results > 0 else 0.0

        prev_cpr = None
        if yesterday:
            prev_spend = sum(c.spend for c in yesterday)
            prev_results = sum(c.results for c in yesterday)
            prev_cpr = prev_spend / prev_results if prev_results > 0 else 0.0

        active = [c for c in today if c.results >= self.config.MIN_RESULTADOS]

        ranked = sorted(active, key=lambda c: c.cpr)
        best = ranked[0] if ranked else None
        worst = ranked[-1] if ranked else None

        health = "🟢 SAUDÁVEL"
        if avg_cpr > self.config.CPR_EXCELENTE:
            health = "🟡 ACEITÁVEL"
        if avg_cpr > self.config.CPR_BOM:
            health = "🟠 ATENÇÃO"
        if avg_cpr > self.config.CPR_ATENCAO:
            health = "🔴 CRÍTICO"

        cpr_variation = None
        if prev_cpr and prev_cpr > 0:
            cpr_variation = (avg_cpr - prev_cpr) / prev_cpr

        return {
            "date": today[0].date if today else "",
            "total_spend": total_spend,
            "total_results": total_results,
            "avg_cpr": avg_cpr,
            "prev_cpr": prev_cpr,
            "cpr_variation": cpr_variation,
            "active_count": len(active),
            "best_campaign": best,
            "worst_campaign": worst,
            "health": health,
        }
