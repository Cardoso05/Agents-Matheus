"""Worker: Pesquisa."""

import json
import os

from cerebro.workers.base_worker import BaseWorker
from cerebro.workers.registry import register_worker


@register_worker
class PesquisaWorker(BaseWorker):
    tipo = "pesquisa"

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        parts = [
            "Você é um pesquisador especializado.",
            "Pesquise o tema solicitado e produza um resumo estruturado com fontes.",
            "Responda em português brasileiro.",
            "",
            "DIRETRIZES:",
            "- Cite fontes e dados concretos sempre que possível",
            "- Separe fatos de opiniões",
            "- Inclua métricas e benchmarks quando relevante",
            "- Destaque insights acionáveis",
            "",
        ]

        secoes = ["resumo", "dados_principais", "fontes", "recomendacoes"]
        if formato_saida and formato_saida.get("secoes"):
            secoes = formato_saida["secoes"]

        parts.append(f"FORMATO: Relatório markdown com seções: {', '.join(secoes)}")

        return "\n".join(parts)

    def _get_tools(self, job: dict) -> list[dict]:
        return [
            {
                "name": "buscar_web",
                "description": "Pesquisa na internet.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Termo de busca"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "ler_arquivo",
                "description": "Lê um arquivo local para referência.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Caminho do arquivo"},
                    },
                    "required": ["path"],
                },
            },
        ]

    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        if name == "buscar_web":
            from cerebro.integrations.web_search import buscar_web
            return buscar_web(input_data["query"])

        elif name == "ler_arquivo":
            escopo = json.loads(job["escopo"]) if job.get("escopo") else {}
            base_dir = escopo.get("base_dir", ".")
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
