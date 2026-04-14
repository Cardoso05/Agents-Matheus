# FinBot AI

Sistema web de organização financeira pessoal com IA. Upload de extratos bancários (CSV/OFX), categorização automática por IA, dashboard interativo e plano de quitação de dívidas.

## Stack

- **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui
- **Backend:** Next.js API Routes + Supabase (Auth, DB, Storage)
- **IA:** Claude API (Anthropic) — categorização, chat, relatórios
- **Gráficos:** Recharts
- **Ícones:** lucide-react

## Funcionalidades implementadas

### Módulo 0-2: Setup + Auth + Layout
- [x] Projeto Next.js 14 com App Router
- [x] Supabase Auth (email/senha + Google OAuth)
- [x] Páginas de login e signup
- [x] Sidebar responsiva (desktop) + bottom nav (mobile)
- [x] Topbar com avatar e notificações
- [x] Middleware de proteção de rotas
- [x] Landing page pública

### Módulo 1: Banco de Dados
- [x] Schema completo com 10 tabelas (profiles, accounts, transactions, categories, debts, etc.)
- [x] RLS policies em todas as tabelas
- [x] 37 categorias padrão brasileiras (seed)
- [x] Triggers de updated_at e auto-create profile

### Módulo 3: Upload e Parsing
- [x] Dropzone com drag & drop (PDF, CSV, OFX, imagens)
- [x] Parser CSV (Nubank, genérico com detecção automática de banco)
- [x] Parser OFX/QFX
- [x] Parser PDF (stub — requer pdf-parse)
- [x] Deduplicação por hash (external_id)
- [x] Preview table antes de confirmar importação

### Módulo 4: Categorização por IA
- [x] Pipeline 3 etapas: regras do usuário → regras globais → Claude API
- [x] Categorização automática após upload
- [x] Categorização automática ao abrir página de lançamentos
- [x] Botão manual "Categorizar com IA"
- [x] Edição inline de categoria (cria regra de aprendizado)
- [x] 30+ keywords globais para categorização sem IA

### Módulo 5: Dashboard
- [x] 4 KPI cards (Renda, Gastos, Saldo, Dívida Total) com variação %
- [x] Gráfico de barras: Receita vs Gastos (6 meses)
- [x] Gráfico pizza: Top 8 categorias de despesa
- [x] Lista de últimos 10 lançamentos

### Módulo 6: Dívidas e Plano de Quitação
- [x] CRUD de dívidas com modal de criação
- [x] Cards com barra de progresso (pago/total)
- [x] Simulador interativo com slider de valor extra
- [x] Comparação Avalanche vs Bola de Neve
- [x] Cálculo de plano de quitação mês a mês

### Módulo 7: Chat com IA
- [x] Widget flutuante com botão no canto inferior direito
- [x] Streaming de resposta (SSE)
- [x] Contexto financeiro real do usuário (renda, gastos, dívidas, transações)
- [x] Renderização de Markdown (títulos, negrito, listas, código)

### Módulo 8: Open Finance
- [x] Estrutura de integração Pluggy (client, connect, callback, sync, webhook)
- [ ] Testes com conta Pluggy real (requer credenciais)

### Módulo 9: Relatórios e Alertas
- [x] Geração de relatório mensal com IA
- [x] Health score (0-100)
- [x] Seções: Destaques, Preocupações, Melhorias, Recomendações
- [x] Fallback inteligente sem API key
- [ ] Sistema de alertas automáticos (overspend, risk, due_date)
- [ ] Cron/edge function para alertas diários

### Módulo 10: Orçamento
- [x] Regra 50-30-20 automática sobre renda média
- [x] Barras de progresso por categoria (verde/amarelo/vermelho)
- [x] Edição manual de limites por categoria (com persistência)
- [x] Botão de reset para 50-30-20

## Setup

### Pré-requisitos

- Node.js 20+
- Conta no [Supabase](https://supabase.com)
- API key do [Anthropic](https://console.anthropic.com) (para funcionalidades de IA)

### Instalação

```bash
# Clonar e instalar
cd finbot-ai
npm install

# Configurar variáveis de ambiente
cp .env.local.example .env.local
# Editar .env.local com suas chaves

# Linkar Supabase
npx supabase link --project-ref SEU_PROJECT_REF

# Aplicar migrations
npx supabase db reset --linked
# ou
npx supabase db push

# Iniciar dev server
npm run dev
```

### Variáveis de ambiente

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx
ANTHROPIC_API_KEY=xxx
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### Configuração do Supabase

1. No painel Supabase, vá em **Authentication → Providers → Email**
2. Desabilite **"Confirm email"** para desenvolvimento
3. No **SQL Editor**, rode (se signup der erro 500):

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, avatar_url)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    NEW.raw_user_meta_data->>'avatar_url'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
GRANT INSERT ON public.profiles TO supabase_auth_admin;
```

## Comandos úteis

```bash
npm run dev          # Dev server
npm run build        # Build de produção
npm run lint         # Linting
npx supabase db push # Aplicar migrations
```

## Próximos passos

- [ ] Parsers específicos para Itaú, Inter, Bradesco, C6, BB, Santander
- [ ] Upload de fotos de extratos (OCR via Claude Vision)
- [ ] Sistema de alertas automáticos com edge functions
- [ ] Integração real com Pluggy (Open Finance)
- [ ] Tela de configurações (perfil, método de quitação preferido, tema)
- [ ] Onboarding guiado para novos usuários
- [ ] Exportação de relatórios em PDF
- [ ] Notificações push (web)
- [ ] Testes automatizados (unit + e2e)
- [ ] Deploy na Vercel

## Estrutura do projeto

```
src/
├── app/
│   ├── (auth)/          # Login, signup
│   ├── (dashboard)/     # Todas as páginas autenticadas
│   │   ├── dashboard/   # KPIs + gráficos
│   │   ├── transactions/# Lista de lançamentos
│   │   ├── upload/      # Upload de extratos
│   │   ├── debts/       # Mapa de dívidas
│   │   ├── budget/      # Orçamento 50-30-20
│   │   ├── reports/     # Relatórios mensais
│   │   └── settings/    # Configurações
│   └── api/             # API routes
├── components/
│   ├── ui/              # shadcn/ui
│   ├── dashboard/       # KPI cards, gráficos
│   ├── upload/          # Dropzone, preview
│   ├── debts/           # Simulador, comparação
│   ├── chat/            # Widget, mensagens
│   └── layout/          # Sidebar, topbar, mobile nav
├── lib/
│   ├── ai/              # Categorização, chat, relatórios
│   ├── parsers/         # CSV, OFX, PDF
│   ├── supabase/        # Clients + middleware
│   ├── constants/       # Categorias, bancos
│   └── utils/           # Moeda, data, dedup
└── types/               # TypeScript types
```
