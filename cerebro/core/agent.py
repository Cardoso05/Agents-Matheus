"""Agente Gerente — único agente LLM do Cérebro."""

import os
import time

import anthropic

from cerebro.core.config import MODEL, SKILLS_DIR
from cerebro.db import models, jobs as jobs_db
from cerebro.db.metricas import registrar_metrica
from cerebro.db.conversas import formatar_historico_para_prompt
from cerebro.integrations import calendar, web_search

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
- registrar_fato: registrar fato/informação sobre um projeto
- listar_stakeholders: ver pessoas envolvidas em um projeto
- criar_job: criar job de background (APENAS para trabalho longo/complexo)
- consultar_jobs: ver status dos jobs de background
- criar_evento_calendar: agendar evento no calendário
- listar_eventos_calendar: ver agenda do dia/semana
- buscar_web: pesquisar na internet
- ler_arquivo: ler conteúdo de um arquivo

IMPORTANTE:
- Nunca invente dados. Se não tem informação, pergunte.
- Não conclua tarefas sem confirmação explícita do Matheus.
- Jobs de background são para trabalho real (revisão, pesquisa, relatório), NÃO para consultas simples.
- Use buscar_web para pesquisas rápidas. Para pesquisas complexas, crie um job de pesquisa.
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
    {
        "name": "consultar_jobs",
        "description": "Consulta status dos jobs de background.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filtrar por status: pendente, executando, concluido, erro",
                },
                "projeto": {"type": "string", "description": "Filtrar por projeto"},
            },
            "required": [],
        },
    },
    {
        "name": "registrar_fato",
        "description": "Registra um fato/informação permanente sobre um projeto na memória.",
        "input_schema": {
            "type": "object",
            "properties": {
                "projeto": {"type": "string", "description": "Slug do projeto"},
                "categoria": {
                    "type": "string",
                    "description": "Categoria: sobre, regra, meta, restricao",
                },
                "fato": {"type": "string", "description": "O fato a registrar"},
            },
            "required": ["projeto", "fato"],
        },
    },
    {
        "name": "listar_stakeholders",
        "description": "Lista pessoas/stakeholders envolvidos em um projeto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "projeto": {"type": "string", "description": "Slug do projeto"},
            },
            "required": ["projeto"],
        },
    },
    {
        "name": "criar_evento_calendar",
        "description": "Cria um evento no calendário.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título do evento"},
                "data": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
                "hora": {"type": "string", "description": "Hora no formato HH:MM. Opcional."},
                "duracao_minutos": {
                    "type": "integer",
                    "description": "Duração em minutos. Default: 60",
                },
                "projeto": {"type": "string", "description": "Projeto relacionado. Opcional."},
                "notas": {"type": "string", "description": "Notas adicionais. Opcional."},
            },
            "required": ["titulo", "data"],
        },
    },
    {
        "name": "listar_eventos_calendar",
        "description": "Lista eventos do calendário. Sem parâmetros retorna eventos de hoje.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_inicio": {"type": "string", "description": "Data início (YYYY-MM-DD)"},
                "data_fim": {"type": "string", "description": "Data fim (YYYY-MM-DD)"},
                "semana": {
                    "type": "boolean",
                    "description": "Se true, retorna eventos da semana inteira",
                },
            },
            "required": [],
        },
    },
    {
        "name": "buscar_web",
        "description": "Pesquisa na internet. Use para consultas rápidas de informação.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca"},
                "num_results": {
                    "type": "integer",
                    "description": "Número de resultados. Default: 5",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "ler_arquivo",
        "description": "Lê o conteúdo de um arquivo do sistema de arquivos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Caminho do arquivo"},
            },
            "required": ["path"],
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


def _handle_consultar_jobs(status=None, projeto=None, **_):
    jobs = jobs_db.listar_jobs(status=status, projeto=projeto)
    if not jobs:
        return "Nenhum job encontrado."
    lines = []
    for j in jobs:
        emoji = {"pendente": "⏳", "executando": "🔄", "concluido": "✅", "erro": "❌"}.get(j["status"], "❓")
        proj = f" [{j['projeto'].upper()}]" if j.get("projeto") else ""
        lines.append(f"{emoji} #{j['id']} ({j['tipo']}){proj} — {j['status']}")
        if j["status"] == "concluido" and j.get("resultado"):
            resumo = j["resultado"][:200]
            lines.append(f"   {resumo}{'...' if len(j['resultado']) > 200 else ''}")
        if j["status"] == "erro" and j.get("erro"):
            lines.append(f"   Erro: {j['erro'][:200]}")
    return "\n".join(lines)


def _handle_registrar_fato(projeto, fato, categoria="sobre", **_):
    models.registrar_fato(projeto=projeto, categoria=categoria, fato=fato)
    return f"✅ Fato registrado para {projeto.upper()}: {fato}"


def _handle_listar_stakeholders(projeto, **_):
    stakeholders = models.listar_stakeholders(projeto)
    if not stakeholders:
        return f"Nenhum stakeholder registrado para {projeto.upper()}."
    lines = []
    for s in stakeholders:
        contato = f" ({s['contato']})" if s.get("contato") else ""
        notas = f" — {s['notas']}" if s.get("notas") else ""
        lines.append(f"• **{s['nome']}** [{s['papel']}]{contato}{notas}")
    return "\n".join(lines)


def _handle_criar_evento_calendar(titulo, data, hora=None, duracao_minutos=60, projeto=None, notas=None, **_):
    evento = calendar.criar_evento(
        titulo=titulo, data=data, hora=hora,
        duracao_minutos=duracao_minutos, projeto=projeto, notas=notas,
    )
    hora_str = f" às {hora}" if hora else ""
    return f"📅 Evento #{evento['id']} criado: {titulo} em {data}{hora_str}"


def _handle_listar_eventos_calendar(data_inicio=None, data_fim=None, semana=False, **_):
    if semana:
        eventos = calendar.eventos_da_semana()
    elif data_inicio:
        eventos = calendar.listar_eventos(data_inicio=data_inicio, data_fim=data_fim)
    else:
        eventos = calendar.eventos_do_dia()
    return calendar.formatar_eventos(eventos)


def _handle_buscar_web(query, num_results=5, **_):
    return web_search.buscar_web(query, num_results=num_results)


def _handle_ler_arquivo(path, **_):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 50000:
            content = content[:50000] + "\n\n... (arquivo truncado)"
        return content
    except FileNotFoundError:
        return f"❌ Arquivo não encontrado: {path}"
    except UnicodeDecodeError:
        return f"❌ Arquivo não é texto: {path}"
    except Exception as e:
        return f"❌ Erro ao ler arquivo: {e}"


TOOL_HANDLERS = {
    "criar_pendencia": _handle_criar_pendencia,
    "concluir_pendencia": _handle_concluir_pendencia,
    "atualizar_pendencia": _handle_atualizar_pendencia,
    "listar_pendencias": _handle_listar_pendencias,
    "delegar_tarefa": _handle_delegar_tarefa,
    "cobrar_delegacao": _handle_cobrar_delegacao,
    "registrar_decisao": _handle_registrar_decisao,
    "consultar_decisoes": _handle_consultar_decisoes,
    "registrar_fato": _handle_registrar_fato,
    "listar_stakeholders": _handle_listar_stakeholders,
    "criar_job": _handle_criar_job,
    "consultar_jobs": _handle_consultar_jobs,
    "criar_evento_calendar": _handle_criar_evento_calendar,
    "listar_eventos_calendar": _handle_listar_eventos_calendar,
    "buscar_web": _handle_buscar_web,
    "ler_arquivo": _handle_ler_arquivo,
}


# ── Agent Class ─────────────────────────────────────────────


class AgenteGerente:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = MODEL

    def processar(self, mensagem: str, projeto: str | None = None, sessao_id: str | None = None) -> str:
        """Processa mensagem via LLM com tools. Retorna texto final."""
        system_prompt = self._build_prompt(projeto)

        # Injetar histórico de conversa se disponível
        messages = []
        if sessao_id:
            historico = formatar_historico_para_prompt(sessao_id, limite=10)
            messages.extend(historico)
        messages.append({"role": "user", "content": mensagem})

        inicio = time.monotonic()
        total_input = 0
        total_output = 0

        try:
            for _ in range(10):  # Safety limit
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )

                # Acumular tokens
                if hasattr(response, "usage"):
                    total_input += response.usage.input_tokens
                    total_output += response.usage.output_tokens

                # Resposta final (sem tool calls)
                if response.stop_reason == "end_turn":
                    resultado = self._extract_text(response)
                    self._registrar_metricas(projeto, total_input, total_output, inicio, True)
                    return resultado

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
                    resultado = self._extract_text(response)
                    self._registrar_metricas(projeto, total_input, total_output, inicio, True)
                    return resultado

            self._registrar_metricas(projeto, total_input, total_output, inicio, False, "limite_iteracoes")
            return "⚠️ Limite de iterações atingido. Tente reformular o pedido."

        except Exception as e:
            self._registrar_metricas(projeto, total_input, total_output, inicio, False, str(e))
            raise

    def _registrar_metricas(self, projeto, tokens_in, tokens_out, inicio, sucesso, erro=None):
        """Registra métricas da interação."""
        try:
            duracao_ms = int((time.monotonic() - inicio) * 1000)
            registrar_metrica(
                tipo="agent", funcao="processar", projeto=projeto,
                tokens_input=tokens_in, tokens_output=tokens_out,
                duracao_ms=duracao_ms, sucesso=sucesso, erro=erro,
            )
        except Exception:
            pass  # Não falhar por causa de métricas

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
