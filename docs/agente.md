# Como o Agente Funciona

## Visão Geral

O Cérebro usa uma arquitetura de **roteamento híbrido**: mensagens simples vão para funções determinísticas (instantâneo, sem custo de API), mensagens complexas vão para o agente Claude com ferramentas.

```
Mensagem do Matheus
       │
       ▼
  ┌─────────────┐
  │  Classifier  │  23 padrões regex
  │              │  + detecção de projeto
  └──────┬──────┘
    ┌────┴────┐
    │         │
 FAST PATH  SMART PATH
 (SQLite)   (Claude + Tools)
    │         │
 Resposta   Resposta
 instantânea  inteligente
```

---

## 1. Fluxo Completo

### 1.1 Entrada

A mensagem pode chegar de 3 interfaces:

| Interface | Entry Point | Sessão |
|-----------|-------------|--------|
| **CLI** | `cerebro/main.py` → `cli_loop()` | `sessao_ativa("cli", "cli_user")` |
| **Telegram** | `cerebro/interfaces/telegram_bot.py` → `handle_message()` | `sessao_ativa("telegram", user_id)` |
| **Web API** | `cerebro/interfaces/web_api.py` → `POST /api/mensagem` | `sessao_ativa("web", "web_user")` |

### 1.2 Classificação (`cerebro/core/classifier.py`)

A função `classificar(mensagem)` retorna um de dois resultados:

```python
# Fast path
{"handler": "deterministic", "func": "status_geral", "args": {}}

# Smart path
{"handler": "agent", "projeto": "wipr"}
```

### 1.3 Execução

```python
result = classificar(texto)
if result["handler"] == "deterministic":
    func = DETERMINISTIC_FUNCS[result["func"]]
    response = func(**result.get("args", {}))
elif result["handler"] == "agent":
    agente = AgenteGerente()
    response = agente.processar(texto, projeto=result.get("projeto"))
```

### 1.4 Saída

- Registra métrica (`registrar_metrica`)
- Salva no histórico (`registrar_mensagem`)
- Envia resposta pela interface

---

## 2. Classifier — 23 Padrões Determinísticos

O classifier testa a mensagem **na ordem abaixo**. O primeiro match ganha.

| # | Padrão | Exemplo | Função |
|---|--------|---------|--------|
| 0 | Só nome de projeto | "WIPR?" | `pendencias_projeto(projeto)` |
| 1 | Resumo financeiro | "quanto gastei", "finanças" | `resumo_financeiro()` |
| 1b | Contas vencidas | "conta vencida", "inadimplente" | `contas_vencidas()` |
| 1c | Contas a vencer | "contas a pagar", "boleto" | `contas_vencendo()` |
| 2 | Status geral | "status geral", "como tá tudo" | `status_geral()` |
| 2b | Atrasadas | "atrasadas", "em atraso" | `atrasadas()` |
| 3 | Prioridade do dia | "o que faço", "top 3" | `top_n_do_dia()` |
| 4 | Concluir tarefa | "fiz #42", "concluí #7" | `concluir_tarefa(id)` |
| 5 | Criar tarefa simples | "cria tarefa: design pra wipr" | `criar_tarefa(tarefa, projeto)` |
| 6 | Review semanal | "resumo semanal" | `resumo_semanal()` |
| 7 | Delegações | "delegações", "quem tá devendo" | `delegacoes_pendentes()` |
| 8 | Agenda | "agenda da semana", "calendário" | `eventos_semana()` |
| 9 | Gasto rápido | "gastei 50 no almoço" | `registrar_gasto(valor, desc)` |
| 10 | Receita rápida | "recebi 700 da Gruta" | `registrar_receita(valor, desc)` |
| 14 | Query simples de projeto | "pendências do ERP" (sem ação) | `pendencias_projeto(projeto)` |
| 15 | **Fallback** | Qualquer outra coisa | **→ Agente LLM** |

### Helper: `_is_simple_query()`

Retorna `False` se a mensagem contém verbos de ação (anota, registra, manda, cria, pesquisa, sugere...). Isso evita que "cria tarefa pro ERP" seja roteado como query simples.

### Helper: `detectar_projeto()`

Usa `PROJETO_ALIASES` para detectar projeto mencionado:
- "wi" → wipr, "eng" → engenharia, "facu" → faculdade, etc.

---

## 3. Agente LLM — Smart Path

### 3.1 Composição do Prompt

A função `_build_prompt(projeto)` monta o system prompt com:

```
1. SYSTEM_PROMPT_BASE (regras, priorização, lista de tools, instruções)
2. ── SKILL DO PROJETO: WIPR ──  (arquivo .md carregado de cerebro/skills/)
3. ── PENDÊNCIAS ATUAIS ──  (banco: tarefas pendentes do projeto)
4. ── DECISÕES RECENTES ──  (banco: últimas 5 decisões do projeto)
5. ── FATOS DO PROJETO ──  (banco: fatos ativos do projeto)
6. ── CONTEXTO GERAL ──  (banco: fatos do projeto "geral")
```

### 3.2 Skills

Arquivos `.md` em `cerebro/skills/` carregados por projeto:
- `wipr.md` → contexto da agência WIPR
- `erp.md` → contexto do ERP DELMAT
- `engenharia.md` → contexto da engenharia
- `gruta.md` → contexto da Gruta Máquinas
- `faculdade.md` → contexto acadêmico
- `financeiro.md` → regras financeiras
- `geral.md` → contexto pessoal (fallback)

Se não existe skill pro projeto, carrega `geral.md` como fallback.

### 3.3 Fatos (Memória Estruturada)

Tabela `fatos_projeto` no banco:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| projeto | TEXT | Slug do projeto |
| categoria | TEXT | sobre, regra, meta, restricao |
| fato | TEXT | O fato em si |
| ativo | BOOL | Se aparece no prompt |

Fatos ativos do projeto são injetados no prompt. Fatos do projeto "geral" são sempre incluídos.

### 3.4 Loop de Tool Use

```
para cada iteração (max 10):
  1. Enviar mensagens → Claude Sonnet 4 (com tools)
  2. Se stop_reason == "end_turn":
       → Extrair texto, retornar
  3. Se stop_reason == "tool_use":
       → Executar cada tool call
       → Appendar resultados como tool_result
       → Volta pro passo 1
```

**Modelo:** `claude-sonnet-4-20250514`
**Max tokens:** 2048 por resposta
**Max iterações:** 10

---

## 4. Ferramentas do Agente (21 tools)

### Gestão de Tarefas

| Tool | Descrição | Params Obrigatórios |
|------|-----------|---------------------|
| `criar_pendencia` | Cria tarefa | tarefa, projeto |
| `concluir_pendencia` | Marca como feita | id |
| `atualizar_pendencia` | Modifica campos | id + campos |
| `listar_pendencias` | Consulta com filtros | — |
| `delegar_tarefa` | Delega pra alguém | id, pessoa, mensagem |
| `cobrar_delegacao` | Gera cobrança | id |

### Memória & Contexto

| Tool | Descrição | Params Obrigatórios |
|------|-----------|---------------------|
| `registrar_decisao` | Registra decisão | projeto, decisao |
| `consultar_decisoes` | Ver decisões | projeto |
| `registrar_fato` | Registra fato | projeto, fato |
| `listar_stakeholders` | Pessoas envolvidas | projeto |

### Finanças

| Tool | Descrição | Params Obrigatórios |
|------|-----------|---------------------|
| `registrar_lancamento` | Gasto ou receita | tipo, valor, descricao, categoria |
| `listar_lancamentos` | Consulta financeira | — |
| `resumo_financeiro` | Entradas vs saídas | — |
| `registrar_compromisso` | Conta a pagar/receber | tipo, descricao, valor, vencimento |
| `listar_compromissos` | Ver compromissos | — |

### Calendário & Utilidades

| Tool | Descrição | Params Obrigatórios |
|------|-----------|---------------------|
| `criar_evento_calendar` | Agendar evento | titulo, data |
| `listar_eventos_calendar` | Ver agenda | — |
| `criar_job` | Job de background | tipo, instrucoes |
| `consultar_jobs` | Status dos jobs | — |
| `buscar_web` | Pesquisa internet | query |
| `ler_arquivo` | Ler arquivo | path |

---

## 5. System Prompt — Regras do Agente

```
REGRAS:
- Direto e prático. Zero discurso motivacional.
- Sugira a MENOR ação que destrava o resto.
- Feito > perfeito.
- Se Matheus está se espalhando, avise.
- Sempre mostre IDs de tarefas pra referência.
- Tarefas atrasadas: 🚨
- Respostas em português brasileiro.

DURAÇÃO:
- Pendências NÃO têm duração — nunca pergunte "quanto tempo vai levar?"
- Eventos usam 60 minutos como padrão.

PENDÊNCIA vs EVENTO:
- Sem horário → criar_pendencia APENAS
- Com data+hora → criar_evento_calendar APENAS
- Evento com preparação → ambos
- Na dúvida → criar_pendencia
```

---

## 6. Validação (Enums)

Todos os valores são validados via `StrEnum` em `cerebro/core/enums.py`:

| Conceito | Enum | Valores |
|----------|------|---------|
| Status tarefa | `StatusPendencia` | pendente, concluida, cancelada |
| Status compromisso | `StatusCompromisso` | aberto, pago, vencido, cancelado |
| Status job | `StatusJob` | pendente, executando, concluido, erro |
| Tipo lancamento | `TipoLancamento` | entrada, saida |
| Tipo compromisso | `TipoCompromisso` | pagar, receber |
| Tipo job | `TipoJob` | revisao_codigo, pesquisa, geracao_conteudo, analise_dados, auditoria, relatorio |
| Projeto | `ProjetoSlug` | wipr, erp, engenharia, gruta, faculdade, geral, pessoal |
| Categoria financeira | `CategoriaFinanceira` | alimentacao, transporte, material, servico, infra, marketing, assinatura, educacao, saude, projeto_receita, servico_receita, outros |
| Categoria fato | `CategoriaFato` | sobre, regra, meta, restricao |

Valor inválido → `ValueError` com mensagem indicando valores válidos.

---

## 7. Scheduler — Notificações Proativas

O scheduler roda junto com o bot Telegram via APScheduler:

| Horário | Função | O que faz |
|---------|--------|-----------|
| 08:00 diário | `cobranca_matinal` | Top 3 tarefas + atrasadas |
| 10:00 diário | `verificar_delegacoes` | Delegações sem resposta (>3 dias) |
| 12:00, 18:00 | `verificar_atrasadas` | Alerta de tarefas atrasadas |
| Seg 09:00 | `verificar_projetos_parados` | Projetos sem ação (>5 dias) |
| Seg/Qui/Sex 16:00 | `pre_faculdade` | Pendências da faculdade |
| 20:00 diário | `contas_vencendo_amanha` | Contas vencendo amanhã |
| 09:00 diário | `contas_vencidas_alerta` | Contas vencidas |
| Dom 19:00 | `resumo_financeiro_semanal` | Resumo financeiro da semana |
| Dom 20:00 | `review_semanal_llm` | Review semanal com IA |
| A cada 30s | `processar_fila_jobs` | Processa jobs pendentes |

---

## 8. Banco de Dados

SQLite em `cerebro/db/cerebro.db`:

| Tabela | Propósito |
|--------|-----------|
| `pendencias` | Tarefas (tarefa, projeto, prioridade, prazo, status) |
| `historico` | Audit log de mudanças |
| `delegacoes` | Registro de delegações |
| `decisoes` | Decisões registradas + contexto |
| `fatos_projeto` | Memória estruturada por projeto |
| `stakeholders` | Pessoas por projeto |
| `resumo_projeto` | Resumo atual de cada projeto |
| `eventos` | Calendário |
| `lancamentos` | Transações financeiras |
| `compromissos` | Contas a pagar/receber |
| `jobs` | Fila de jobs de background |
| `conversas` | Histórico de chat |
| `metricas` | Dados de performance |
| `categorias` | Categorias financeiras |
| `regras_categorizacao` | Regras custom de categorização |

---

## 9. Métricas

Toda interação registra uma métrica:

```python
registrar_metrica(
    tipo="deterministic" | "agent" | "worker",
    funcao="status_geral" | "processar" | "pesquisa",
    projeto="wipr",
    duracao_ms=150,
    tokens_input=500,
    tokens_output=200,
    custo=0.003,
    sucesso=True,
    erro=None,
)
```

Visível no painel web em `/metricas`.

---

## 10. Painel Web (`/contexto`)

Página para gerenciar o contexto do agente:

- **Skills**: Editar arquivos `.md` diretamente pelo browser
- **Fatos**: CRUD de memória estruturada (com toggle ativo/inativo)
- **Stakeholders**: CRUD de pessoas por projeto

Acessível em `https://cerebro.cardosomatheus.com.br/contexto`
