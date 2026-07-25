# Meta Ads → WhatsApp — Specs

Automação que puxa métricas da Meta Marketing API, formata um relatório
comparativo e envia via WhatsApp (Evolution API) pra um número fixo.

Vive **dentro do cerebro** como módulo `cerebro.meta_reports`, reaproveitando
o `AsyncIOScheduler` já existente em `cerebro/core/scheduler.py`.

---

## 1. Escopo

- **1 ad account** (configurada via env)
- **1 destinatário** WhatsApp (DM, número fixo via env)
- **2 relatórios automáticos**:
  - **Diário** — D-1 vs D-2 (todo dia 08:30)
  - **Semanal** — últimos 7d vs 7d anteriores (segunda 08:45)
- **Comando manual** no Telegram pra disparar relatório sob demanda
  (`/meta hoje`, `/meta semana`, `/meta resend`)

Fora de escopo nesta v1: múltiplas contas, gráficos/imagens, PDF, painel web,
A/B insights com LLM, alerts em tempo real (CPA estourou etc.).

---

## 2. Arquitetura

```
/opt/cerebro/cerebro/meta_reports/
├── __init__.py
├── meta_client.py       # cliente da Meta Marketing API (httpx)
├── metrics.py           # cálculo + comparação de períodos
├── formatter.py         # render do texto WhatsApp
├── whatsapp.py          # cliente Evolution API
├── jobs.py              # funções chamadas pelo scheduler
├── storage.py           # persistência em SQLite (cache + histórico)
└── SPECS.md             # este arquivo
```

Integração com cerebro existente:

- `cerebro/core/scheduler.py` — adiciona 2 jobs (`meta_diario`, `meta_semanal`)
- `cerebro/db/setup.py` — cria tabelas `meta_snapshots` e `meta_reports`
- `cerebro/interfaces/telegram.py` (ou onde estão os handlers) — comandos `/meta …`
- Sem novo systemd service: roda dentro de `cerebro-bot.service`

---

## 3. Fonte de dados — Meta Marketing API

**Endpoint base:** `https://graph.facebook.com/v21.0/act_<AD_ACCOUNT_ID>/insights`

**Auth:** token de longa duração de System User (Business Manager). Token de
usuário comum **expira em 60 dias** — não usar.

**Campos por chamada:**

```
spend, impressions, reach, clicks, ctr, cpc, cpm, frequency,
actions, action_values, purchase_roas, cost_per_action_type
```

**Granularidade:**

- 1ª chamada: account-level (`level=account`) → totais
- 2ª chamada: campaign-level (`level=campaign`, `limit=50`) → top N por gasto

**Janelas (parâmetro `time_range`, formato `{since,until}` em YYYY-MM-DD,
inclusivo dos dois lados):**

| Relatório | Período atual | Período anterior |
|---|---|---|
| Diário | D-1 (ontem) | D-2 (anteontem) |
| Semanal | D-7 a D-1 (últimos 7 dias completos) | D-14 a D-8 |

> Roda às 8h30 / 8h45 — D-1 já está fechado no fuso de Brasília.
> A Meta atualiza dados retroativamente até ~28d (atribuição), então o número
> de "ontem" pode mexer alguns dias depois. Aceitável pra v1.

**Timezone:** Brasília (mesmo do cerebro, via `cerebro.clock.FUSO`).
A Meta retorna no timezone da ad account — verificar e converter se diferente.

**Rate limit:** ad account tier (200 calls/h por app+user). Cada relatório
diário gasta ~4 calls (2 períodos × 2 níveis). Tranquilo.

---

## 4. Métricas no relatório

### 4.1 Account-level (sempre presente)

| Métrica | Fonte API | Apresentação |
|---|---|---|
| Investido | `spend` | `R$ 432,10` |
| Impressões | `impressions` | `84.2k` |
| Alcance | `reach` | `12.5k` |
| Cliques | `clicks` | `1.230` |
| CTR | `ctr` | `1,46%` |
| CPC | `cpc` | `R$ 0,35` |
| CPM | `cpm` | `R$ 5,13` |
| Conversões | `actions` filtrando `action_type` configurado | `18` |
| CPA | `spend / conversões` | `R$ 24,01` |
| ROAS | `purchase_roas[0].value` | `3,8x` |

**Tipo de conversão a contar** — definir no `.env` qual `action_type` é o
"sucesso" (ex.: `purchase`, `lead`, `complete_registration`, ou um custom
event tipo `offsite_conversion.fb_pixel_purchase`). Default: `purchase`.

### 4.2 Comparação

Cada métrica numérica vem com delta vs período anterior:

- Variação **absoluta**: `+R$ 50,20`
- Variação **percentual**: `+13,1%`
- **Seta** com cor semântica:
  - 📈 verde quando subir é bom (conversões, ROAS, CTR, alcance, impressões, cliques)
  - 📉 vermelho quando subir é ruim (CPA, CPC, CPM, gasto se acima do orçamento)
  - ➡️ se variação ≤ 2% (ruído)

### 4.3 Top campanhas

Top 3 por gasto no período atual. Pra cada uma:
- Nome (truncado em 30 chars)
- Gasto + delta %
- Conversões
- Status (ACTIVE/PAUSED — útil quando uma some)

---

## 5. Formato da mensagem

### 5.1 Diário (D-1 vs D-2)

```
📊 *Relatório Meta Ads — 08/05* (qui)
_Comparado com 07/05 (qua)_

💰 Investido: R$ 432,10  📈 +13,1%
👁  Impressões: 84.2k  📈 +5,4%
🖱  Cliques: 1.230 (CTR 1,46%)  ➡️ +0,8%
🛒 Conversões: 18  📈 +20,0% (+3)
📊 CPA: R$ 24,01  📉 -5,7% _(melhor)_
💸 ROAS: 3,8x  📈 +8,5%

*Top campanhas:*
1. Black Promo — R$ 198 (+22%) | 11 conv ✅
2. Remarketing — R$ 142 (-8%) | 5 conv ✅
3. Awareness BR — R$ 92 (+0%) | 2 conv ⏸

ℹ️ _Atribuição da Meta pode ajustar números nas próximas 24-48h._
```

### 5.2 Semanal (segunda, 08:45)

```
📅 *Semanal Meta Ads — 28/04 a 04/05*
_vs 21/04 a 27/04_

💰 Investido: R$ 3.024,70  📈 +9,2%
🛒 Conversões: 142  📈 +18,3% (+22)
📊 CPA: R$ 21,30  📉 -7,7% _(melhor)_
💸 ROAS médio: 4,1x  📈 +12,0%
🖱  CTR: 1,52%  📈 +4,2%

*Melhor dia:* qua (R$ 482 / 28 conv / ROAS 5,2x)
*Pior dia:* dom (R$ 380 / 12 conv / ROAS 2,1x)

*Top campanhas (semana):*
1. Black Promo — R$ 1.420 | 78 conv | ROAS 4,8x
2. Remarketing — R$ 890 | 41 conv | ROAS 4,1x
3. Awareness BR — R$ 412 | 11 conv | ROAS 1,2x ⚠

📈 *Tendência:* +18% conv com +9% gasto → eficiência subindo.
```

A "tendência" é uma frase determinística simples (não LLM):
- conv ↑ + gasto ↓ ou ≈ → "eficiência subindo"
- conv ↓ + gasto ↑ → "eficiência caindo, vale revisar"
- ambos no mesmo sentido → "escala" (positiva ou negativa)
- variação <5% nos dois → "estável"

> Formatação WhatsApp: `*negrito*`, `_itálico_`, sem markdown headers.

---

## 6. Envio — Evolution API

Já está rodando em `127.0.0.1:8080` (container Docker, domínio
`wpp.cardosomatheus.com.br`).

**Endpoint:**
```
POST http://127.0.0.1:8080/message/sendText/{INSTANCE_NAME}
Headers: apikey: <AUTHENTICATION_API_KEY>
Body: { "number": "5511999999999", "text": "..." }
```

**Variáveis novas no `/opt/cerebro/.env`:**
```
META_AD_ACCOUNT_ID=act_xxxxxxxxxxxxxx
META_ACCESS_TOKEN=EAAB...
META_CONVERSION_ACTION_TYPE=purchase
META_REPORT_TIMEZONE=America/Sao_Paulo

EVOLUTION_API_URL=http://127.0.0.1:8080
EVOLUTION_API_KEY=<mesma do .env do compose>
EVOLUTION_INSTANCE=<nome da instância>
META_REPORT_WHATSAPP_NUMBER=5511999999999
```

(`EVOLUTION_API_KEY` é o `AUTHENTICATION_API_KEY` que já está em
`/opt/evolution-api/.env`.)

**Tratamento de erro:**
- Falha na Meta API → log + notifica via Telegram do cerebro (canal já existe)
  com mensagem curta: `⚠️ Falhou relatório Meta: <erro>`. Não envia WhatsApp.
- Falha no envio WhatsApp → grava o relatório no SQLite (com `status=failed`)
  e notifica Telegram. `/meta resend` re-tenta.
- WhatsApp limita ~4096 chars por msg — relatório fica bem abaixo, sem split.

---

## 7. Persistência

Duas tabelas novas no SQLite do cerebro (`/opt/cerebro/cerebro.db` —
verificar caminho real em `cerebro/db/setup.py`):

```sql
CREATE TABLE IF NOT EXISTS meta_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,            -- ISO timestamp da chamada
    period_start TEXT NOT NULL,          -- YYYY-MM-DD
    period_end TEXT NOT NULL,            -- YYYY-MM-DD
    level TEXT NOT NULL,                 -- 'account' | 'campaign'
    payload_json TEXT NOT NULL,          -- resposta crua da Meta (debug + replay)
    UNIQUE(period_start, period_end, level, fetched_at)
);

CREATE TABLE IF NOT EXISTS meta_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                  -- 'daily' | 'weekly' | 'manual'
    generated_at TEXT NOT NULL,
    period_label TEXT NOT NULL,          -- ex: '2026-05-08'
    text_message TEXT NOT NULL,          -- conteúdo enviado (ou que seria enviado)
    sent_status TEXT NOT NULL,           -- 'sent' | 'failed' | 'skipped'
    sent_at TEXT,
    error TEXT
);
```

**Por que guardar:**
- Re-envio sem refazer chamada à Meta
- Histórico/auditoria
- Base pra futuras evoluções (gráficos, comparações de longo prazo, eval)

---

## 8. Scheduler

Em `cerebro/core/scheduler.py`, na função `criar_scheduler()`:

```python
from cerebro.meta_reports.jobs import enviar_meta_diario, enviar_meta_semanal

scheduler.add_job(
    enviar_meta_diario, "cron",
    hour=8, minute=30, id="meta_diario",
)
scheduler.add_job(
    enviar_meta_semanal, "cron",
    day_of_week="mon", hour=8, minute=45, id="meta_semanal",
)
```

Os jobs são `async def`, conforme padrão dos outros do cerebro.

---

## 9. Comandos Telegram

Adicionar handlers em `cerebro/interfaces/telegram.py` (ou onde os outros
comandos vivem):

| Comando | Ação |
|---|---|
| `/meta hoje` | Gera relatório diário agora (D-1 vs D-2), envia WhatsApp e ecoa no Telegram |
| `/meta semana` | Gera relatório semanal agora |
| `/meta resend` | Reenvia o último `meta_reports` com `sent_status='failed'` |
| `/meta preview` | Gera o texto mas NÃO envia no WhatsApp — só ecoa no Telegram (debug) |

Restrição: só responde pro chat ID do dono (já existe esse padrão no cerebro).

---

## 10. Tratamento de casos especiais

- **Sem gasto no período** → manda mensagem curta: `📊 Sem atividade na conta no
  dia 08/05. Campanhas pausadas?` em vez do relatório cheio.
- **Sem dado no período anterior** (ex.: conta começou ontem) → omite a coluna
  de comparação, mostra só os números absolutos com nota `_primeira semana_`.
- **Divisão por zero** (CTR/CPA quando 0 cliques/conv) → mostra `—` no lugar.
- **Token expirado** → erro categorizado como `auth_error`, mensagem específica
  no Telegram pra renovar token: `🔑 Token Meta expirou — renovar em
  business.facebook.com`.
- **Job atrasou (server desligado)** → APScheduler `misfire_grace_time=3600`
  pra rodar quando voltar; se passar de 1h, pula e loga.

---

## 11. Roadmap de implementação

1. **`storage.py`** — schemas + funções `salvar_snapshot`, `salvar_report`,
   `ultimo_failed`. Migration aplicada no `db/setup.py`.
2. **`meta_client.py`** — `fetch_insights(level, since, until)`, retry com
   backoff em 429/5xx, parsing pra dict tipado.
3. **`metrics.py`** — `comparar(periodo_atual, periodo_anterior)` retorna
   estrutura com abs/delta/seta; `top_n_campanhas(n=3)`.
4. **`formatter.py`** — `render_daily(...)`, `render_weekly(...)`,
   `render_empty(...)`. Funções puras, testáveis.
5. **`whatsapp.py`** — `enviar_texto(numero, texto)`, raise em erro HTTP.
6. **`jobs.py`** — orquestra: fetch → snapshot → render → send → save report.
7. **Wiring scheduler** + handlers Telegram.
8. **Eval** em `cerebro/evals/test_meta_reports.py` — fixtures com payloads
   reais salvos, garante que formatter não regrida.

Cada passo é um commit pequeno. Um deploy via webhook do cerebro ao final.

---

## 12. Pendências antes de codar

Coisas que precisam vir do usuário:

- [ ] **Meta Ad Account ID** (`act_…`)
- [ ] **Token de System User** com escopos `ads_read`, `business_management`
      (gerar em business.facebook.com → Configurações → System Users)
- [ ] Confirmar **action_type da conversão principal** (`purchase`?
      `lead`? evento custom?)
- [ ] **Número WhatsApp destino** (formato `55DDDNNNNNNNNN`, sem `+`)
- [ ] **Nome da instância Evolution** já criada (ou criar uma nova dedicada
      pra automações? recomendo separar da instância pessoal)
- [ ] Confirmar timezone da ad account na Meta (deve ser Brasília)
- [ ] Quer ROAS calculado em cima de `purchase_roas` (Meta) ou de
      `action_values / spend` (manual, mais flexível)?
