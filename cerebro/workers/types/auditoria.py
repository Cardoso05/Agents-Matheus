"""Worker: Auditoria — verifica consistência e pendências."""

from cerebro.workers.base_worker import BaseWorker
from cerebro.workers.registry import register_worker
from cerebro.db import models
from cerebro.core.deterministic import atrasadas, delegacoes_pendentes


@register_worker
class AuditoriaWorker(BaseWorker):
    tipo = "auditoria"

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        parts = [
            "Você é um auditor de gestão de projetos.",
            "Verifique a consistência dos dados e identifique problemas.",
            "Responda em português brasileiro.",
            "",
            "FOCO DA AUDITORIA:",
            "- Pendências atrasadas sem justificativa",
            "- Delegações sem resposta",
            "- Projetos sem atividade recente",
            "- Decisões registradas vs. ações tomadas",
            "- Prazos inconsistentes ou irrealistas",
            "",
            "FORMATO: Checklist com status (✅ OK | ⚠️ Atenção | ❌ Problema)",
        ]

        return "\n".join(parts)

    def _get_tools(self, job: dict) -> list[dict]:
        return [
            {
                "name": "listar_pendencias",
                "description": "Lista pendências com filtros.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "projeto": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": [],
                },
            },
            {
                "name": "atrasadas",
                "description": "Retorna todas as pendências atrasadas.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "delegacoes_pendentes",
                "description": "Retorna delegações sem resposta.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dias": {"type": "integer", "description": "Dias sem resposta. Default: 3"},
                    },
                    "required": [],
                },
            },
            {
                "name": "consultar_decisoes",
                "description": "Consulta decisões de um projeto.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "projeto": {"type": "string"},
                    },
                    "required": ["projeto"],
                },
            },
        ]

    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        if name == "listar_pendencias":
            pendencias = models.listar_pendencias(
                projeto=input_data.get("projeto"),
                status=input_data.get("status"),
            )
            if not pendencias:
                return "Nenhuma pendência encontrada."
            lines = []
            for p in pendencias:
                prazo = f" (prazo: {p['prazo']})" if p.get("prazo") else ""
                delegado = f" → {p['delegado_para']}" if p.get("delegado_para") else ""
                lines.append(f"#{p['id']} [{p['projeto']}] {p['tarefa']}{prazo}{delegado}")
            return "\n".join(lines)

        elif name == "atrasadas":
            return atrasadas()

        elif name == "delegacoes_pendentes":
            dias = input_data.get("dias", 3)
            return delegacoes_pendentes(dias=dias)

        elif name == "consultar_decisoes":
            decisoes = models.consultar_decisoes(input_data["projeto"])
            if not decisoes:
                return "Nenhuma decisão registrada."
            return "\n".join(f"[{d['data']}] {d['decisao']}" for d in decisoes)

        return f"❌ Tool '{name}' não disponível."
