# Cérebro

Sistema pessoal de gestão inteligente que combina um agente Claude com roteamento determinístico, bot Telegram, dashboard web e painel financeiro completo.

```
"Gastei 50 no almoço"        → registra gasto instantaneamente (sem LLM)
"Qual o status do WIPR?"     → busca direto no banco (sem LLM)
"Analisa meu fluxo de caixa" → Claude Sonnet 4 com contexto financeiro
```

## Arquitetura

```
                        Mensagem do usuário
                               │
                    ┌──────────┴──────────┐
                    │   Smart Classifier   │
                    │  (23 padrões regex)  │
                    └──────────┬──────────┘
                         ┌─────┴─────┐
                    Fast Path    Smart Path
                    (SQLite)     (Claude + Tools)
                         │           │
                    Resposta     Resposta
                    instantânea  inteligente
                         │           │
                    ┌────┴───────────┴────┐
                    │     3 Interfaces     │
                    ├─────────────────────┤
                    │  CLI · Telegram · Web │
                    └─────────────────────┘
```

**Fast Path** — 23 padrões determinísticos (tarefas, finanças, calendário) respondem direto do banco sem custo de API.

**Smart Path** — Consultas complexas vão para o Claude Sonnet 4 com 16 ferramentas (criar tarefas, registrar decisões, buscar na web, etc).

## Tech Stack

| Camada | Tecnologia |
|--------|-----------|
| LLM | Claude Sonnet 4 (Anthropic) |
| Backend | Python 3.11+, FastAPI |
| Bot | python-telegram-bot |
| Frontend | Next.js 14, TypeScript, Tailwind, shadcn/ui |
| Banco (Cérebro) | SQLite |
| Banco (FinBot) | Supabase (PostgreSQL + RLS) |
| Infra | Nginx, systemd, Let's Encrypt |
| Deploy | GitHub webhook → testes → restart → Telegram |

## Funcionalidades

### Gestão de Tarefas
- Criar, concluir, atualizar pendências
- Priorização automática e detecção de atrasos
- Delegação com cobrança automática
- Visão por projeto (WIPR, ERP, Engenharia, Gruta, Faculdade)

### Finanças
- `"Gastei 80 no mercado"` → registro instantâneo com categoria
- Categorização em 3 estágios: regras do usuário → regras globais → Claude
- Contas a pagar/receber com alertas de vencimento
- Resumo mensal com comparativo

### FinBot — Dashboard Financeiro
- Upload de extratos (CSV/OFX) com parser Nubank
- Dashboard com KPIs e gráficos (Recharts)
- Simulador de dívidas (Avalanche vs Snowball)
- Orçamento 50-30-20 com feedback visual
- Relatórios mensais com score de saúde (0-100)
- Chat com IA integrado ao contexto financeiro

### Integrações
- **Google Calendar** — sincroniza eventos bidirecional
- **Brave Search** — pesquisa web via agente
- **Supabase** — bridge Cérebro ↔ FinBot (sync de transações)

### Scheduler
- 08:00 — Top 3 tarefas do dia
- 18:00 — Resumo do dia
- Segunda 09:00 — Review semanal

### Workers (Jobs Assíncronos)
- `pesquisa` — Pesquisa web → relatório markdown
- `relatorio` — Relatório mensal com insights IA
- `analise_dados` — Análise de métricas
- `auditoria` — Verificação de consistência
- `geracao_conteudo` — Propostas, emails, textos
- `revisao_codigo` — Code review + auditoria de segurança

## Setup Local

### Pré-requisitos
- Python 3.11+
- Node.js 20+ (para FinBot)

### Instalação

```bash
git clone https://github.com/cardoso05/Agents-Matheus.git
cd Agents-Matheus

# Python
make install        # cria .venv e instala deps
make setup          # copia .env.example → .env

# Configurar chaves no .env (mínimo: ANTHROPIC_API_KEY)
nano .env

# Dados de exemplo
make seed
```

### Executar

```bash
make cli            # modo interativo
make telegram       # bot Telegram
make web            # dashboard em http://localhost:8000
```

### FinBot (opcional)

```bash
cd finbot-ai-main
npm install
cp .env.local.example .env.local
# Configurar Supabase + Claude API no .env.local
npx supabase db push --linked
npm run dev         # http://localhost:3000
```

## Configuração (.env)

| Variável | Obrigatória | Descrição |
|----------|:-----------:|-----------|
| `ANTHROPIC_API_KEY` | sim | Chave da API Claude |
| `TELEGRAM_BOT_TOKEN` | para bot | Token do @BotFather |
| `TELEGRAM_AUTHORIZED_USERS` | para bot | IDs autorizados (vírgula) |
| `BRAVE_API_KEY` | não | Busca web (2000/mês grátis) |
| `GOOGLE_CREDENTIALS_PATH` | não | OAuth2 do Google Calendar |
| `SUPABASE_URL` | não | URL do projeto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | não | Chave service_role |
| `DEPLOY_WEBHOOK_SECRET` | não | Secret do webhook GitHub |
| `CEREBRO_API_KEY` | não | Protege endpoints POST/PUT/DELETE |

## Deploy em Produção

### Setup inicial (VPS Ubuntu)

```bash
ssh root@seu.servidor.com
git clone https://github.com/cardoso05/Agents-Matheus.git /opt/cerebro
cd /opt/cerebro

# Setup completo (Python, Nginx, SSL, firewall, systemd)
sudo bash deploy/setup.sh

# Iniciar serviços
make start
```

### Deploy automatizado

Push na `main` → webhook GitHub → deploy automático:

```
push → HMAC validation → backup DB → git pull → pip install
     → detect FinBot changes (rsync + npm build)
     → detect new Supabase migrations
     → pytest → systemctl restart → health check
     → Telegram notification ✅ ou rollback + 🚨
```

```bash
# Configurar (uma vez)
sudo bash deploy/setup-deploy.sh
# Depois: adicionar webhook + deploy key no GitHub
```

### URLs em produção

```
https://cerebro.cardosomatheus.com.br/           → Dashboard web
https://cerebro.cardosomatheus.com.br/finbot/     → FinBot
https://cerebro.cardosomatheus.com.br/webhook/    → Deploy listener
```

## Estrutura do Projeto

```
cerebro/
├── core/           # Agent + classifier + scheduler
├── db/             # Models + CRUD (SQLite)
├── finance/        # Categorização, determinísticos financeiros
├── integrations/   # Google Calendar, Brave, Supabase
├── interfaces/     # Telegram bot, FastAPI + templates
├── workers/        # Jobs assíncronos (pesquisa, relatórios)
├── skills/         # Contexto por projeto (markdown → Claude)
└── main.py         # CLI entry point

finbot-ai-main/
├── src/app/        # Next.js App Router (auth, dashboard, upload, debts, budget)
├── src/components/ # UI components (shadcn/ui, charts)
├── src/lib/        # AI categorizer, parsers, Supabase clients
└── supabase/       # Migrations SQL

deploy/
├── setup.sh        # Setup inicial do servidor
├── deploy.sh       # Pipeline de deploy automatizado
├── listener.py     # Webhook receiver (FastAPI :9000)
├── notify.sh       # Notificações Telegram
├── nginx.conf      # Reverse proxy + SSL + rate limiting
├── backup.sh       # Backup diário do SQLite
└── *.service       # Systemd units
```

## Comandos Úteis

```bash
# Desenvolvimento
make test           # Rodar testes
make cli            # CLI interativo
make telegram       # Bot Telegram
make web            # Dashboard web

# Produção
make start          # Instalar e iniciar systemd services
make stop           # Parar services
make restart        # Reiniciar bot + web
make logs           # Logs em tempo real
make status         # Status dos serviços + health check
make backup         # Backup manual do banco
make secure-check   # Auditoria de segurança

# Deploy
make deploy-setup   # Configurar webhook listener
make deploy-manual  # Deploy manual
make deploy-logs    # Log de deploys
make deploy-status  # Status do listener
```

## Banco de Dados

### Cérebro (SQLite)

| Tabela | Função |
|--------|--------|
| `pendencias` | Tarefas (projeto, prioridade, prazo, status) |
| `historico` | Audit log de todas as mudanças |
| `delegacoes` | Tarefas delegadas + respostas |
| `decisoes` | Decisões registradas + justificativa |
| `eventos` | Eventos de calendário |
| `lancamentos` | Transações (receita/despesa) |
| `compromissos` | Contas a pagar/receber |
| `jobs` | Fila de jobs assíncronos |
| `conversas` | Histórico de chat por sessão |
| `metricas` | Dados de performance |

### FinBot (Supabase/PostgreSQL)
- 10 tabelas com RLS policies
- 37 categorias de transação (seed)
- Migrations versionadas em `supabase/migrations/`

## Licença

Projeto pessoal de Matheus Cardoso.
