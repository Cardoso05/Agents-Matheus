# Sistema de Workers

## Visão Geral

Workers são agentes LLM especializados que executam trabalho longo/complexo em background. Cada tipo de worker tem ferramentas e prompt específicos.

```
Criação do Job (CLI, Web, Agente)
       │
       ▼
  ┌─────────────────┐
  │  Fila (SQLite)   │  status = "pendente"
  └────────┬────────┘
           │  Polling a cada 30s
           ▼
  ┌─────────────────┐
  │  Runner          │  pegar_proximo_job()
  │  (FIFO)          │  status → "executando"
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Worker          │  Loop agentic (Claude + tools)
  │  Especializado   │  max_tool_calls = 30
  └────────┬────────┘
      ┌────┴────┐
    OK         ERRO
      │           │
  concluido    erro
  + resultado  + mensagem
      │           │
  Telegram 📩  Telegram 🚨
```

---

## 1. Lifecycle de um Job

### 1.1 Criação

```python
from cerebro.db.jobs import criar_job

job = criar_job(
    tipo="pesquisa",                    # TipoJob enum (obrigatório)
    instrucoes="Pesquisar CPC do setor de máquinas",  # (obrigatório)
    projeto="gruta",                    # ProjetoSlug (opcional)
    escopo={"keywords": ["CPC", "máquinas"]},  # JSON (opcional)
    tools_permitidas=["buscar_web"],    # Restringe tools (opcional)
    formato_saida={"tipo": "relatorio_markdown", "secoes": [...]},  # (opcional)
    limites={"max_tokens": 50000, "max_tool_calls": 30, "timeout_minutos": 15},
)
# Retorna: {"id": "job_a1b2c3d4", "status": "pendente", ...}
```

**Quem pode criar:**

| Via | Como |
|-----|------|
| Agente | Tool `criar_job` (o agente decide quando precisa de work async) |
| CLI | `python -m cerebro --create-job pesquisa "instruções" --job-projeto gruta` |
| Web | POST `/api/jobs` com `{tipo, instrucoes, projeto}` |
| Seed | `cerebro/db/seed.py` cria jobs de exemplo |

### 1.2 Fila e Polling

- **Scheduler** roda `processar_fila_jobs()` a cada **30 segundos**
- `pegar_proximo_job()` busca o job pendente mais antigo (FIFO)
- Atomicamente marca como `executando` + seta `iniciado_em`
- Se fila vazia, retorna silenciosamente

### 1.3 Seleção do Worker

```python
from cerebro.workers.registry import get_worker

worker = get_worker(job["tipo"])  # Ex: PesquisaWorker()
```

O registry carrega todos os workers no import:

```python
# cerebro/workers/registry.py
_registry = {
    "revisao_codigo": RevisaoCodigoWorker,
    "pesquisa": PesquisaWorker,
    "geracao_conteudo": GeracaoConteudoWorker,
    "analise_dados": AnaliseDadosWorker,
    "auditoria": AuditoriaWorker,
    "relatorio": RelatorioWorker,
}
```

### 1.4 Execução

O `BaseWorker.executar(job)` roda um loop agentic:

```python
# Pseudocódigo
system_prompt = worker._build_system_prompt(instrucoes, escopo, formato)
tools = worker._get_tools(job)
messages = [{"role": "user", "content": instrucoes}]

for _ in range(max_tool_calls):  # default: 30
    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=min(max_tokens, 8192),
        system=system_prompt,
        tools=tools,
        messages=messages,
    )
    
    if response.stop_reason == "end_turn":
        return extract_text(response)  # Resultado final (markdown)
    
    if response.stop_reason == "tool_use":
        # Executar tools, appendar resultados, iterar
        ...

return "⚠️ Worker atingiu limite de iterações."
```

### 1.5 Resultado

```python
# Sucesso
jobs_db.concluir_job(job_id, resultado)
# status → "concluido", resultado = markdown, concluido_em = NOW

# Erro
jobs_db.falhar_job(job_id, f"Erro: {e}")
# status → "erro", erro = mensagem, concluido_em = NOW
```

### 1.6 Notificação

Após conclusão, envia mensagem via Telegram:

```
📋 Job concluído: job_a1b2c3d4
Tipo: pesquisa | Projeto: GRUTA
──
[primeiros 500 chars do resultado]
...
```

---

## 2. Tipos de Worker

### 2.1 Pesquisa (`pesquisa`)

**Propósito:** Pesquisar um tema na web e compilar relatório.

**System Prompt:** Pesquisador que cita fontes, separa fatos de opinião.

**Tools:**
- `buscar_web(query)` — Brave Search API
- `ler_arquivo(path)` — Ler arquivo local (sandbox protegido)

**Seções do Output:**
1. Resumo
2. Dados Principais
3. Fontes
4. Recomendações

**Exemplo:**
```
criar_job("pesquisa", "Pesquisar CPC médio para serviços de CFTV em SP", projeto="engenharia")
```

---

### 2.2 Relatório (`relatorio`)

**Propósito:** Gerar relatório de projeto com métricas e recomendações.

**System Prompt:** Analista de projetos, usa dados concretos, destaca tendências.

**Tools:**
- `status_geral()` — Overview de todos os projetos
- `resumo_semanal()` — Resumo da semana
- `listar_pendencias(projeto, status)` — Tarefas filtradas
- `consultar_decisoes(projeto)` — Decisões recentes

**Seções do Output:**
1. Resumo Executivo
2. Métricas
3. Destaques
4. Riscos
5. Próximos Passos

---

### 2.3 Auditoria (`auditoria`)

**Propósito:** Verificar consistência do sistema — atrasadas, delegações, projetos parados.

**System Prompt:** Auditor de projetos, formato checklist com status (✅ OK | ⚠️ Atenção | ❌ Problema).

**Foco:** Atrasadas sem justificativa, delegações sem resposta, projetos inativos, decisão sem ação.

**Tools:**
- `listar_pendencias()` — Todas as tarefas
- `atrasadas()` — Tarefas atrasadas
- `delegacoes_pendentes(dias)` — Delegações abertas
- `consultar_decisoes()` — Decisões vs ações

---

### 2.4 Geração de Conteúdo (`geracao_conteudo`)

**Propósito:** Gerar documentos profissionais — propostas, emails, textos.

**System Prompt:** Escritor profissional, adapta tom ao contexto.

**Tools:**
- `consultar_decisoes(projeto)` — Contexto das decisões
- `listar_pendencias(projeto)` — Tarefas para referência

**Exemplo:**
```
criar_job("geracao_conteudo", "Escrever proposta comercial para condomínio com 170 câmeras", projeto="engenharia")
```

---

### 2.5 Revisão de Código (`revisao_codigo`)

**Propósito:** Code review com foco em bugs, segurança e boas práticas.

**System Prompt:** Revisor de código, foca em: bugs, vulnerabilidades (SQL injection, XSS), error handling, validação, performance.

**Tools:**
- `ler_arquivo(path)` — Ler arquivo (proteção de path traversal, max 50KB)
- `listar_arquivos(path)` — Listar diretório

**Escopo:** `escopo.arquivos` define quais arquivos revisar.

**Seções do Output:**
1. Resumo
2. Problemas Críticos
3. Sugestões
4. Próximos Passos

---

### 2.6 Análise de Dados (`analise_dados`)

**Propósito:** Analisar métricas, calcular tendências, identificar outliers.

**System Prompt:** Analista de dados, usa tabelas markdown, calcula KPIs.

**Tools:**
- `status_geral()` — Status dos projetos
- `resumo_semanal()` — Dados da semana
- `listar_pendencias()` — Dados de tarefas
- `buscar_web(query)` — Benchmarks externos
- `ler_arquivo(path)` — Dados em arquivo

**Seções do Output:**
1. Resumo
2. Métricas
3. Insights
4. Recomendações

---

## 3. Tabela de Jobs no Banco

```sql
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,      -- job_a1b2c3d4
    tipo            TEXT NOT NULL,          -- TipoJob enum
    projeto         TEXT,                   -- ProjetoSlug (opcional)
    status          TEXT DEFAULT 'pendente', -- pendente → executando → concluido|erro
    instrucoes      TEXT NOT NULL,          -- O que o worker deve fazer
    escopo          TEXT,                   -- JSON: contexto/escopo
    tools_permitidas TEXT,                  -- JSON: restrição de tools
    formato_saida   TEXT,                   -- JSON: formato do output
    limites         TEXT,                   -- JSON: {max_tokens, max_tool_calls, timeout_minutos}
    resultado       TEXT,                   -- Markdown do resultado (se concluido)
    erro            TEXT,                   -- Mensagem de erro (se erro)
    criado_em       DATETIME,
    iniciado_em     DATETIME,
    concluido_em    DATETIME,
    custo_tokens    INTEGER,
    notificar       TEXT DEFAULT 'telegram'
);
```

---

## 4. Transições de Status

```
                                     ┌──────────┐
                    criação           │ pendente │
                                     └────┬─────┘
                                          │  pegar_proximo_job()
                                     ┌────▼─────┐
                                     │executando │
                                     └────┬─────┘
                                     ┌────┴────┐
                                ┌────▼───┐  ┌──▼──┐
                                │concluido│  │ erro │
                                └────────┘  └─────┘
```

**Não há retry automático.** Jobs em `erro` ficam parados. Para reprocessar, crie um novo job.

---

## 5. Funções CRUD

```python
# cerebro/db/jobs.py

criar_job(tipo, instrucoes, projeto?, escopo?, ...) → dict
get_job(id) → dict | None
listar_jobs(status?, projeto?) → list[dict]
pegar_proximo_job() → dict | None    # Atomically: pendente → executando
concluir_job(id, resultado, custo_tokens?) → dict
falhar_job(id, erro) → dict
```

---

## 6. Limites Padrão

| Limite | Valor | Descrição |
|--------|-------|-----------|
| `max_tokens` | 50,000 | Tokens máximos por resposta |
| `max_tool_calls` | 30 | Iterações máximas do loop |
| `timeout_minutos` | 15 | (advisory, não enforced) |
| API max_tokens por call | 8,192 | Truncado via `min(max_tokens, 8192)` |

---

## 7. Segurança

- **Path traversal protegido:** `os.path.normpath()` + validação `startswith(base_dir)`
- **Arquivo max 50KB:** Truncado com aviso se maior
- **Tipo validado:** `validate_enum()` rejeita tipos inválidos na criação
- **Sandbox:** Workers só acessam tools permitidas, não o sistema inteiro

---

## 8. Métricas de Workers

Cada execução registra:

```python
registrar_metrica(
    tipo="worker",
    funcao="pesquisa",        # tipo do job
    projeto="gruta",
    duracao_ms=15000,
    sucesso=True,             # ou False se erro
    erro="mensagem de erro",  # se falhou
)
```

Visível em `/metricas` no painel web.

---

## 9. Exemplos de Uso

### Via Agente (conversa)

```
Matheus: "Preciso de um relatório de performance de todos os projetos"
Agente: [usa tool criar_job] → "✅ Job job_f3a1b2c3 criado (relatorio)"
```

### Via CLI

```bash
# Criar job
python -m cerebro --create-job pesquisa "Pesquisar CPC setor de máquinas" --job-projeto gruta

# Processar manualmente (sem esperar scheduler)
python -m cerebro --process-jobs
```

### Via Web

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"tipo": "auditoria", "instrucoes": "Verificar pendências atrasadas e delegações sem resposta"}'
```

### Resultado no Painel

Acessível em `/jobs` — mostra tipo, status, projeto, resultado formatado, erros.
