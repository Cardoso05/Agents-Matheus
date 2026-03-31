"""Worker: Análise de dados — métricas e insights."""

import json
import os

from cerebro.workers.base_worker import BaseWorker
from cerebro.workers.registry import register_worker
from cerebro.db import models
from cerebro.core.deterministic import status_geral, resumo_semanal
from cerebro.integrations.web_search import buscar_web


@register_worker
class AnaliseDadosWorker(BaseWorker):
    tipo = "analise_dados"

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        parts = [
            "Você é um analista de dados e performance.",
            "Analise os dados fornecidos e produza insights acionáveis.",
            "Responda em português brasileiro.",
            "",
            "DIRETRIZES:",
            "- Calcule métricas relevantes (taxas, médias, tendências)",
            "- Compare com benchmarks quando possível",
            "- Identifique outliers e anomalias",
            "- Recomende ações concretas baseadas nos dados",
            "- Use tabelas markdown para dados tabulares",
            "",
        ]

        secoes = ["resumo", "metricas", "insights", "recomendacoes"]
        if formato_saida and formato_saida.get("secoes"):
            secoes = formato_saida["secoes"]

        parts.append(f"FORMATO: Relatório markdown com seções: {', '.join(secoes)}")

        return "\n".join(parts)

    def _get_tools(self, job: dict) -> list[dict]:
        return [
            {
                "name": "status_geral",
                "description": "Visão geral de todos os projetos.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "resumo_semanal",
                "description": "Métricas da semana.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
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
                "name": "buscar_web",
                "description": "Pesquisa na internet para benchmarks e referências.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "ler_arquivo",
                "description": "Lê um arquivo de dados.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
        ]

    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        escopo = json.loads(job["escopo"]) if job.get("escopo") else {}
        base_dir = escopo.get("base_dir", ".")

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
                lines.append(f"#{p['id']} [{p['projeto']}] {p['tarefa']}{prazo} — P{p['prioridade']}")
            return "\n".join(lines)

        elif name == "buscar_web":
            return buscar_web(input_data["query"])

        elif name == "ler_arquivo":
            path = input_data["path"]
            full_path = os.path.normpath(os.path.join(base_dir, path))
            if not full_path.startswith(os.path.normpath(base_dir)):
                return "❌ Acesso negado: caminho fora do escopo."
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) > 50000:
                    content = content[:50000] + "\n... (truncado)"
                return content
            except FileNotFoundError:
                return f"❌ Arquivo não encontrado: {path}"
            except Exception as e:
                return f"❌ Erro: {e}"

        return f"❌ Tool '{name}' não disponível."
