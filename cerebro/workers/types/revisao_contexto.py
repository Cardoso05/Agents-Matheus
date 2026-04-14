"""Worker: Revisão de Contexto — atualiza fatos_projeto automaticamente."""

from cerebro.workers.base_worker import BaseWorker
from cerebro.workers.registry import register_worker
from cerebro.db import models


@register_worker
class RevisaoContextoWorker(BaseWorker):
    tipo = "revisao_contexto"

    def _build_system_prompt(self, instrucoes: str, escopo: dict, formato_saida: dict) -> str:
        return "\n".join([
            "Você é um revisor de contexto do sistema Cérebro.",
            "Sua função é manter os fatos dos projetos atualizados.",
            "",
            "REGRAS:",
            "- Primeiro use `listar_fatos` para ver os fatos atuais.",
            "- Compare com as conversas recentes fornecidas nas instruções.",
            "- Use `consultar_decisoes` e `listar_pendencias` para contexto adicional.",
            "- Desative fatos claramente DESATUALIZADOS ou CONTRADITOS pelas conversas.",
            "- Adicione fatos NOVOS e PERMANENTES que emergem das conversas.",
            "- NÃO duplique fatos que já existem (mesmo com redação diferente).",
            "- NÃO adicione status temporários (ex: 'reunião marcada para quinta').",
            "- Só registre fatos que você pode justificar com base nas conversas.",
            "- Categorias válidas: sobre, meta, restricao, processo, contato.",
            "",
            "FORMATO DE SAÍDA: Resumo markdown das alterações feitas.",
            "Se nenhuma alteração foi necessária, diga explicitamente.",
        ])

    def _get_tools(self, job: dict) -> list[dict]:
        projeto = job.get("projeto", "")
        return [
            {
                "name": "listar_fatos",
                "description": f"Lista todos os fatos ativos do projeto '{projeto}'.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "consultar_decisoes",
                "description": f"Consulta decisões recentes do projeto '{projeto}'.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limite": {"type": "integer", "description": "Máximo de decisões. Default: 10"},
                    },
                    "required": [],
                },
            },
            {
                "name": "listar_pendencias",
                "description": f"Lista pendências do projeto '{projeto}'.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Filtro de status. Default: pendente"},
                    },
                    "required": [],
                },
            },
            {
                "name": "registrar_fato",
                "description": "Registra um novo fato permanente sobre o projeto.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "categoria": {"type": "string", "description": "sobre, meta, restricao, processo, contato"},
                        "fato": {"type": "string", "description": "O fato a registrar"},
                    },
                    "required": ["categoria", "fato"],
                },
            },
            {
                "name": "desativar_fato",
                "description": "Desativa um fato desatualizado pelo ID.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "ID do fato a desativar"},
                    },
                    "required": ["id"],
                },
            },
        ]

    def _execute_tool(self, name: str, input_data: dict, job: dict) -> str:
        projeto = job.get("projeto", "")

        if name == "listar_fatos":
            fatos = models.listar_fatos(projeto)
            if not fatos:
                return "Nenhum fato registrado para este projeto."
            lines = []
            for f in fatos:
                lines.append(f"#{f['id']} [{f['categoria']}] {f['fato']}")
            return "\n".join(lines)

        elif name == "consultar_decisoes":
            limite = input_data.get("limite", 10)
            decisoes = models.consultar_decisoes(projeto, limite=limite)
            if not decisoes:
                return "Nenhuma decisão registrada."
            return "\n".join(f"[{d['data']}] {d['decisao']}" for d in decisoes)

        elif name == "listar_pendencias":
            status = input_data.get("status", "pendente")
            pendencias = models.listar_pendencias(projeto=projeto, status=status)
            if not pendencias:
                return "Nenhuma pendência encontrada."
            lines = []
            for p in pendencias:
                prazo = f" (prazo: {p['prazo']})" if p.get("prazo") else ""
                lines.append(f"#{p['id']} P{p['prioridade']} {p['tarefa']}{prazo}")
            return "\n".join(lines)

        elif name == "registrar_fato":
            result = models.registrar_fato(
                projeto=projeto,
                categoria=input_data["categoria"],
                fato=input_data["fato"],
            )
            return f"Fato #{result['id']} registrado: [{result['categoria']}] {result['fato']}"

        elif name == "desativar_fato":
            ok = models.desativar_fato(input_data["id"])
            if ok:
                return f"Fato #{input_data['id']} desativado com sucesso."
            return f"Fato #{input_data['id']} não encontrado ou já desativado."

        return f"Tool '{name}' não disponível."
