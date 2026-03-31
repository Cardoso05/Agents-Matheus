"""Agente Gerente — único agente LLM do Cérebro."""

import os

import anthropic

from cerebro.core.config import MODEL, SKILLS_DIR
from cerebro.db import models, jobs as jobs_db

# ── System Prompt Base ──────────────────────────────────────

SYSTEM_PROMPT_BASE = """Você é o Cérebro do Matheus — seu assistente de gestão de projetos.

REGRAS:
- Direto e prático. Zero discurso motivacional.
- Sugira a MENOR ação que destrava o resto.
- Feito > perfeito.
- Se Matheus está se espalhando, avise.
- Sempre mostre IDs de tarefas pra referência.
- Tarefas atrasadas: 🚨
- Respostas em português brasileiro.

PRIORIZAÇÃO DE PROJETOS:
1. 🔴 WIPR — receita rápida
2. 🔴 DELMAT ERP — recorrência
3. 🟡 DELMAT Engenharia — manter rodando
4. 🟡 Gruta Máquinas — manter retainer
5. 🟢 Demais — só se os anteriores estiverem em dia

TOOLS DISPONÍVEIS:
- criar_pendencia: criar tarefas
- concluir_pendencia: marcar como feita
- atualizar_pendencia: modificar campos
- listar_pendencias: consultar tarefas
- delegar_tarefa: delegar pra alguém
- cobrar_delegacao: gerar cobrança de delegação
- registrar_decisao: registrar decisão tomada
- consultar_decisoes: ver decisões passadas
- criar_job: criar job de background (APENAS para trabalho longo/complexo)

IMPORTANTE:
- Nunca invente dados. Se não tem informação, pergunte.
- Não conclua tarefas sem confirmação explícita do Matheus.
- Jobs de background são para trabalho real (revisão, pesquisa, relatório), NÃO para consultas simples.
"""

# ── Tool Definitions ────────────────────────────────────────

TOOLS = [
    {
        "name": "criar_pendencia",
        "description": "Cria uma nova pendência/tarefa no sistema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tarefa": {"type": "string", "description": "Descrição da tarefa"},
                "projeto": {
                    "type": "string",
                    "description": "Slug do projeto (wipr, erp, engenharia, gruta, faculdade)",
                },
                "prioridade": {
                    "type": "integer",
                    "description": "1=urgente a 5=baixa. Default: 3",
                },
                "prazo": {
                    "type": "string",
                    "description": "Data limite no formato YYYY-MM-DD. Opcional.",
                },
                "responsavel": {
                    "type": "string",
                    "description": "Quem é responsável. Default: matheus",
                },
                "notas": {"type": "string", "description": "Notas adicionais. Opcional."},
            },
            "required": ["tarefa", "projeto"],
        },
    },
    {
        "name": "concluir_pendencia",
        "description": "Marca uma pendência como concluída.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID da pendência"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "atualizar_pendencia",
        "description": "Atualiza campos de uma pendência existente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID da pendência"},
                "tarefa": {"type": "string", "description": "Nova descrição"},
                "projeto": {"type": "string", "description": "Novo projeto"},
                "prioridade": {"type": "integer", "description": "Nova prioridade (1-5)"},
                "prazo": {"type": "string", "description": "Novo prazo (YYYY-MM-DD)"},
                "status": {"type": "string", "description": "Novo status (pendente, concluida, cancelada)"},
                "responsavel": {"type": "string", "description": "Novo responsável"},
                "delegado_para": {"type": "string", "description": "Delegar para alguém"},
                "notas": {"type": "string", "description": "Novas notas"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "listar_pendencias",
        "description": "Lista pendências com filtros opcionais.",
        "input_schema": {
            "type": "object",
            "properties": {
                "projeto": {"type": "string", "description": "Filtrar por projeto"},
                "status": {"type": "string", "description": "Filtrar por status (pendente, concluida, cancelada)"},
                "responsavel": {"type": "string", "description": "Filtrar por responsável"},
            },
            "required": [],
        },
    },
    {
        "name": "delegar_tarefa",
        "description": "Delega uma tarefa para outra pessoa e gera mensagem de delegação.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID da pendência"},
                "pessoa": {"type": "string", "description": "Nome da pessoa"},
                "mensagem": {"type": "string", "description": "Mensagem de delegação para enviar"},
            },
            "required": ["id", "pessoa", "mensagem"],
        },
    },
    {
        "name": "cobrar_delegacao",
        "description": "Gera mensagem de cobrança para uma tarefa delegada sem resposta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID da pendência delegada"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "registrar_decisao",
        "description": "Registra uma decisão tomada para um projeto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "projeto": {"type": "string", "description": "Slug do projeto"},
                "decisao": {"type": "string", "description": "Descrição da decisão"},
                "contexto": {"type": "string", "description": "Por que foi decidido"},
                "participantes": {"type": "string", "description": "Quem participou da decisão"},
            },
            "required": ["projeto", "decisao"],
        },
    },
    {
        "name": "consultar_decisoes",
        "description": "Consulta decisões recentes de um projeto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "projeto": {"type": "string", "description": "Slug do projeto"},
                "limite": {"type": "integer", "description": "Número máximo de decisões. Default: 5"},
            },
            "required": ["projeto"],
        },
    },
    {
        "name": "criar_job",
        "description": "Cria um job de background para execução assíncrona por um worker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo: revisao_codigo, pesquisa, geracao_conteudo, analise_dados, auditoria, relatorio",
                },
                "projeto": {"type": "string", "description": "Slug do projeto"},
                "instrucoes": {"type": "string", "description": "Instruções detalhadas para o worker"},
                "escopo": {"type": "object", "description": "Escopo do job (ex: {arquivos: [...]})"},
                "tools_permitidas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tools que o worker pode usar",
                },
                "formato_saida": {
                    "type": "object",
                    "description": "Formato do output (ex: {tipo: 'relatorio_markdown', secoes: [...]})",
                },
            },
            "required": ["tipo", "instrucoes"],
        },
    },
]


# ── Tool Handlers ───────────────────────────────────────────


def _handle_criar_pendencia(tarefa, projeto, prioridade=3, prazo=None, responsavel="matheus", notas=None, **_):
    result = models.criar_pendencia(
        tarefa=tarefa, projeto=projeto, prioridade=prioridade,
        prazo=prazo, responsavel=responsavel, notas=notas,
    )
    return f"✅ Pendência #{result['id']} criada: {tarefa} [{projeto.upper()}]"


def _handle_concluir_pendencia(id, **_):
    result = models.concluir_pendencia(id)
    if result:
        return f"✅ Pendência #{id} concluída: {result['tarefa']}"
    return f"❌ Pendência #{id} não encontrada."


def _handle_atualizar_pendencia(id, **campos):
    result = models.atualizar_pendencia(id, **campos)
    if result:
        return f"✅ Pendência #{id} atualizada."
    return f"❌ Pendência #{id} não encontrada."


def _handle_listar_pendencias(projeto=None, status=None, responsavel=None, **_):
    pendencias = models.listar_pendencias(projeto=projeto, status=status, responsavel=responsavel)
    if not pendencias:
        return "Nenhuma pendência encontrada com esses filtros."
    lines = []
    for p in pendencias:
        prazo_str = f" (prazo: {p['prazo']})" if p.get("prazo") else ""
        atrasado = " 🚨" if p.get("atrasada") else ""
        delegado = f" → {p['delegado_para']}" if p.get("delegado_para") else ""
        lines.append(f"#{p['id']} [{p['projeto'].upper()}] {p['tarefa']}{prazo_str}{delegado}{atrasado}")
    return "\n".join(lines)


def _handle_delegar_tarefa(id, pessoa, mensagem, **_):
    result = models.delegar_tarefa(id, pessoa)
    if result:
        return f"✅ Pendência #{id} delegada para {pessoa}.\nMensagem sugerida:\n\n{mensagem}"
    return f"❌ Pendência #{id} não encontrada."


def _handle_cobrar_delegacao(id, **_):
    pendencia = models.get_pendencia(id)
    if not pendencia:
        return f"❌ Pendência #{id} não encontrada."
    if not pendencia.get("delegado_para"):
        return f"❌ Pendência #{id} não está delegada."
    return (
        f"📋 Pendência #{id}: {pendencia['tarefa']}\n"
        f"Delegada para: {pendencia['delegado_para']}\n"
        f"Criada em: {pendencia['criado_em']}"
    )


def _handle_registrar_decisao(projeto, decisao, contexto=None, participantes=None, **_):
    models.registrar_decisao(
        projeto=projeto, decisao=decisao, contexto=contexto, participantes=participantes,
    )
    return f"✅ Decisão registrada para {projeto.upper()}: {decisao}"


def _handle_consultar_decisoes(projeto, limite=5, **_):
    decisoes = models.consultar_decisoes(projeto, limite=limite)
    if not decisoes:
        return f"Nenhuma decisão registrada para {projeto.upper()}."
    lines = []
    for d in decisoes:
        lines.append(f"[{d['data']}] {d['decisao']}")
    return "\n".join(lines)


def _handle_criar_job(tipo, instrucoes, projeto=None, escopo=None, tools_permitidas=None, formato_saida=None, **_):
    result = jobs_db.criar_job(
        tipo=tipo, projeto=projeto, instrucoes=instrucoes,
        escopo=escopo, tools_permitidas=tools_permitidas,
        formato_saida=formato_saida,
    )
    return f"🔄 Job #{result['id']} criado ({tipo}). Te aviso quando terminar."


TOOL_HANDLERS = {
    "criar_pendencia": _handle_criar_pendencia,
    "concluir_pendencia": _handle_concluir_pendencia,
    "atualizar_pendencia": _handle_atualizar_pendencia,
    "listar_pendencias": _handle_listar_pendencias,
    "delegar_tarefa": _handle_delegar_tarefa,
    "cobrar_delegacao": _handle_cobrar_delegacao,
    "registrar_decisao": _handle_registrar_decisao,
    "consultar_decisoes": _handle_consultar_decisoes,
    "criar_job": _handle_criar_job,
}


# ── Agent Class ─────────────────────────────────────────────


class AgenteGerente:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = MODEL

    def processar(self, mensagem: str, projeto: str | None = None) -> str:
        """Processa mensagem via LLM com tools. Retorna texto final."""
        system_prompt = self._build_prompt(projeto)
        messages = [{"role": "user", "content": mensagem}]

        for _ in range(10):  # Safety limit
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            # Resposta final (sem tool calls)
            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            # Processar tool calls
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                return self._extract_text(response)

        return "⚠️ Limite de iterações atingido. Tente reformular o pedido."

    def _build_prompt(self, projeto: str | None = None) -> str:
        """Monta system prompt com base + skill + pendências + decisões."""
        parts = [SYSTEM_PROMPT_BASE]

        # Skill do projeto
        if projeto:
            skill = self._load_skill(projeto)
            if skill:
                parts.append(f"\n── SKILL DO PROJETO: {projeto.upper()} ──\n{skill}")

        # Pendências atuais
        pendencias = models.listar_pendencias(
            projeto=projeto, status="pendente"
        )
        if pendencias:
            parts.append(f"\n── PENDÊNCIAS ATUAIS ──\n{self._format_pendencias(pendencias)}")
        else:
            parts.append("\n── PENDÊNCIAS ATUAIS ──\nNenhuma pendência pendente.")

        # Decisões recentes
        if projeto:
            decisoes = models.consultar_decisoes(projeto, limite=5)
            if decisoes:
                parts.append(f"\n── DECISÕES RECENTES ──\n{self._format_decisoes(decisoes)}")

        return "\n".join(parts)

    def _load_skill(self, projeto: str) -> str | None:
        """Carrega skill .md do projeto."""
        skill_path = SKILLS_DIR / f"{projeto}.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        # Fallback
        geral_path = SKILLS_DIR / "geral.md"
        if geral_path.exists():
            return geral_path.read_text(encoding="utf-8")
        return None

    def _format_pendencias(self, pendencias: list[dict]) -> str:
        lines = []
        for p in pendencias:
            prazo = f" (prazo: {p['prazo']})" if p.get("prazo") else ""
            atrasada = " 🚨" if p.get("atrasada") else ""
            delegado = f" → {p['delegado_para']}" if p.get("delegado_para") else ""
            lines.append(f"#{p['id']} [{p['projeto'].upper()}] P{p['prioridade']} {p['tarefa']}{prazo}{delegado}{atrasada}")
        return "\n".join(lines)

    def _format_decisoes(self, decisoes: list[dict]) -> str:
        lines = []
        for d in decisoes:
            lines.append(f"[{d['data']}] {d['decisao']}")
        return "\n".join(lines)

    def _extract_text(self, response) -> str:
        texts = []
        for block in response.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else "✅ Feito."

    def _execute_tool(self, name: str, input_data: dict) -> str:
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return f"❌ Tool '{name}' não encontrada."
        try:
            return handler(**input_data)
        except Exception as e:
            return f"❌ Erro ao executar {name}: {e}"
