"""Classe base para workers de background."""

import json
import logging
from abc import ABC, abstractmethod

import anthropic

from cerebro.core.config import MODEL

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Worker base — executa um job com escopo fechado e tools limitadas."""

    tipo: str  # Deve ser definido pela subclasse

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = MODEL

    def executar(self, job: dict) -> str:
        """
        Executa o job e retorna o resultado como string markdown.

        O job contém:
        - instrucoes: str
        - escopo: dict | None (JSON parsed)
        - tools_permitidas: list[str] | None (JSON parsed)
        - formato_saida: dict | None (JSON parsed)
        - limites: dict (JSON parsed)
        """
        instrucoes = job["instrucoes"]
        escopo = json.loads(job["escopo"]) if job.get("escopo") else {}
        formato_saida = json.loads(job["formato_saida"]) if job.get("formato_saida") else {}
        limites = json.loads(job["limites"]) if job.get("limites") else {}

        max_tokens = limites.get("max_tokens", 50000)
        max_tool_calls = limites.get("max_tool_calls", 30)

        system_prompt = self._build_system_prompt(instrucoes, escopo, formato_saida)
        tools = self._get_tools(job)

        messages = [{"role": "user", "content": instrucoes}]
        tool_calls_count = 0

        for _ in range(max_tool_calls):
            kwargs = {
                "model": self.model,
                "max_tokens": min(max_tokens, 8192),
                "system": system_prompt,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls_count += 1
                        if tool_calls_count > max_tool_calls:
                            return self._extract_text(response) or "⚠️ Limite de tool calls atingido."
                        result = self._execute_tool(block.name, block.input, job)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                return self._extract_text(response)

        return "⚠️ Worker atingiu limite de iterações."

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        """Monta system prompt do worker."""
        parts = [
            f"Você é um worker especializado do tipo '{self.tipo}'.",
            "Execute a tarefa descrita abaixo com foco e objetividade.",
            "Responda em português brasileiro.",
        ]

        if escopo:
            parts.append(f"\nESCOPO:\n{json.dumps(escopo, indent=2, ensure_ascii=False)}")

        if formato_saida:
            tipo_saida = formato_saida.get("tipo", "markdown")
            secoes = formato_saida.get("secoes", [])
            parts.append(f"\nFORMATO DE SAÍDA: {tipo_saida}")
            if secoes:
                parts.append("Seções obrigatórias: " + ", ".join(secoes))

        return "\n".join(parts)

    def _get_tools(self, job: dict) -> list[dict]:
        """Retorna tools permitidas para este worker. Pode ser overridden."""
        return []

    @abstractmethod
    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        """Executa uma tool call. Implementado por cada tipo de worker."""
        ...

    @staticmethod
    def _extract_text(response) -> str:
        texts = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(texts) if texts else ""
