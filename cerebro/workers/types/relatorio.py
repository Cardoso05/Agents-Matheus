"""Worker: Geração de relatórios."""

from cerebro.workers.base_worker import BaseWorker
from cerebro.workers.registry import register_worker
from cerebro.db import models
from cerebro.core.deterministic import status_geral, resumo_semanal


@register_worker
class RelatorioWorker(BaseWorker):
    tipo = "relatorio"

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        parts = [
            "Você é um analista de gestão de projetos.",
            "Gere relatórios claros, com métricas e recomendações acionáveis.",
            "Responda em português brasileiro.",
            "",
            "DIRETRIZES:",
            "- Use dados concretos (números, datas, porcentagens)",
            "- Destaque tendências (melhorando/piorando)",
            "- Inclua recomendações práticas",
            "- Formato markdown estruturado",
            "",
        ]

        secoes = ["resumo_executivo", "metricas", "destaques", "riscos", "proximos_passos"]
        if formato_saida and formato_saida.get("secoes"):
            secoes = formato_saida["secoes"]

        parts.append(f"SEÇÕES: {', '.join(secoes)}")

        return "\n".join(parts)

    def _get_tools(self, job: dict) -> list[dict]:
        return [
            {
                "name": "status_geral",
                "description": "Retorna visão geral de todos os projetos com contagens.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "resumo_semanal",
                "description": "Retorna métricas da semana (criadas vs concluídas).",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
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
                "name": "consultar_decisoes",
                "description": "Consulta decisões recentes de um projeto.",
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
        if name == "status_geral":
            return status_geral()

        elif name == "resumo_semanal":
            return resumo_semanal()

        elif name == "listar_pendencias":
            pendencias = models.listar_pendencias(
                projeto=input_data.get("projeto"),
                status=input_data.get("status"),
            )
            if not pendencias:
                return "Nenhuma pendência encontrada."
            lines = []
            for p in pendencias:
                prazo = f" (prazo: {p['prazo']})" if p.get("prazo") else ""
                lines.append(f"#{p['id']} [{p['projeto'].upper()}] {p['tarefa']}{prazo}")
            return "\n".join(lines)

        elif name == "consultar_decisoes":
            decisoes = models.consultar_decisoes(input_data["projeto"])
            if not decisoes:
                return "Nenhuma decisão registrada."
            lines = [f"[{d['data']}] {d['decisao']}" for d in decisoes]
            return "\n".join(lines)

        return f"❌ Tool '{name}' não disponível."
