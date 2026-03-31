"""Worker: Revisão de código."""

import json
import os

from cerebro.workers.base_worker import BaseWorker
from cerebro.workers.registry import register_worker


@register_worker
class RevisaoCodigoWorker(BaseWorker):
    tipo = "revisao_codigo"

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        parts = [
            "Você é um revisor de código especializado.",
            "Analise o código fornecido e produza um relatório detalhado.",
            "Responda em português brasileiro.",
            "",
            "FOCO DA REVISÃO:",
            "- Bugs e erros lógicos",
            "- Vulnerabilidades de segurança (SQL injection, XSS, etc.)",
            "- Tratamento de erros",
            "- Validação de inputs",
            "- Boas práticas e padrões",
            "- Performance",
            "",
        ]

        if escopo:
            arquivos = escopo.get("arquivos", [])
            if arquivos:
                parts.append(f"ARQUIVOS PARA REVISAR: {', '.join(arquivos)}")

        secoes = ["resumo", "problemas_criticos", "sugestoes", "proximos_passos"]
        if formato_saida and formato_saida.get("secoes"):
            secoes = formato_saida["secoes"]

        parts.append(f"\nFORMATO: Relatório markdown com seções: {', '.join(secoes)}")

        return "\n".join(parts)

    def _get_tools(self, job: dict) -> list[dict]:
        return [
            {
                "name": "ler_arquivo",
                "description": "Lê o conteúdo de um arquivo do projeto.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Caminho do arquivo"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "listar_arquivos",
                "description": "Lista arquivos em um diretório.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Caminho do diretório"},
                    },
                    "required": ["path"],
                },
            },
        ]

    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        escopo = json.loads(job["escopo"]) if job.get("escopo") else {}
        base_dir = escopo.get("base_dir", ".")

        if name == "ler_arquivo":
            return self._ler_arquivo(input_data["path"], base_dir, escopo)
        elif name == "listar_arquivos":
            return self._listar_arquivos(input_data["path"], base_dir, escopo)
        return f"❌ Tool '{name}' não disponível."

    def _ler_arquivo(self, path: str, base_dir: str, escopo: dict) -> str:
        full_path = os.path.normpath(os.path.join(base_dir, path))
        # Segurança: não permitir sair do base_dir
        if not full_path.startswith(os.path.normpath(base_dir)):
            return "❌ Acesso negado: caminho fora do escopo."
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            if len(content) > 50000:
                content = content[:50000] + "\n\n... (arquivo truncado)"
            return content
        except FileNotFoundError:
            return f"❌ Arquivo não encontrado: {path}"
        except Exception as e:
            return f"❌ Erro ao ler arquivo: {e}"

    def _listar_arquivos(self, path: str, base_dir: str, escopo: dict) -> str:
        full_path = os.path.normpath(os.path.join(base_dir, path))
        if not full_path.startswith(os.path.normpath(base_dir)):
            return "❌ Acesso negado: caminho fora do escopo."
        try:
            entries = []
            for entry in os.scandir(full_path):
                tipo = "dir" if entry.is_dir() else "file"
                entries.append(f"[{tipo}] {entry.name}")
            return "\n".join(sorted(entries)) if entries else "(diretório vazio)"
        except FileNotFoundError:
            return f"❌ Diretório não encontrado: {path}"
        except Exception as e:
            return f"❌ Erro ao listar: {e}"
