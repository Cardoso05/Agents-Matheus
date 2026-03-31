"""Worker: Pesquisa."""

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

    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        # Pesquisa worker na Phase 3 inicial não tem tools externas.
        # Futuro: buscar_web, ler_arquivo
        return f"❌ Tool '{name}' não disponível para pesquisa (ainda)."
