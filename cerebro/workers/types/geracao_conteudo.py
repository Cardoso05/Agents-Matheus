"""Worker: Geração de conteúdo."""

import json

from cerebro.workers.base_worker import BaseWorker
from cerebro.workers.registry import register_worker
from cerebro.db import models


@register_worker
class GeracaoConteudoWorker(BaseWorker):
    tipo = "geracao_conteudo"

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        parts = [
            "Você é um redator profissional.",
            "Gere o conteúdo solicitado de forma clara, direta e profissional.",
            "Responda em português brasileiro.",
            "",
            "DIRETRIZES:",
            "- Adapte o tom ao contexto (proposta comercial, relatório, email, etc.)",
            "- Seja conciso mas completo",
            "- Use formatação markdown quando apropriado",
            "",
        ]

        tipo_saida = "markdown"
        if formato_saida:
            tipo_saida = formato_saida.get("tipo", "markdown")
        parts.append(f"FORMATO DE SAÍDA: {tipo_saida}")

        return "\n".join(parts)

    def _get_tools(self, job: dict) -> list[dict]:
        return [
            {
                "name": "consultar_decisoes",
                "description": "Consulta decisões recentes de um projeto para contexto.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "projeto": {"type": "string", "description": "Slug do projeto"},
                    },
                    "required": ["projeto"],
                },
            },
            {
                "name": "listar_pendencias",
                "description": "Lista pendências de um projeto para referência.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "projeto": {"type": "string", "description": "Slug do projeto"},
                    },
                    "required": ["projeto"],
                },
            },
        ]

    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        if name == "consultar_decisoes":
            decisoes = models.consultar_decisoes(input_data["projeto"])
            if not decisoes:
                return "Nenhuma decisão registrada."
            lines = [f"[{d['data']}] {d['decisao']}" for d in decisoes]
            return "\n".join(lines)

        elif name == "listar_pendencias":
            pendencias = models.listar_pendencias(projeto=input_data["projeto"], status="pendente")
            if not pendencias:
                return "Nenhuma pendência pendente."
            lines = [f"#{p['id']} {p['tarefa']}" for p in pendencias]
            return "\n".join(lines)

        return f"❌ Tool '{name}' não disponível."
