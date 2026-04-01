# FinBot AI

## Comandos
- `npm run dev` — inicia dev server
- `npm run build` — build de produção
- `npm run lint` — linting
- `npx supabase db push` — aplica migrations
- `npx supabase gen types typescript --local > src/types/database.ts` — gera types

## Convenções
- App Router (Next.js 14) — tudo em `src/app/`
- Server Components por padrão, `"use client"` só quando necessário
- Validação com Zod em todas as APIs
- Supabase RLS ativo — nunca usar service_role no client
- Formatação de moeda: sempre BRL com `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })`
- Datas: `date-fns` com locale `pt-BR`
- Componentes UI: shadcn/ui — instalar com `npx shadcn@latest add [component]`
- Gráficos: Recharts
- Ícones: lucide-react

## Estrutura de módulos (ordem de desenvolvimento)
1. Setup + Auth + Layout (Módulo 0-2)
2. Upload + Parsing (Módulo 3)
3. Categorização IA (Módulo 4)
4. Dashboard (Módulo 5)
5. Dívidas + Plano (Módulo 6)
6. Chat IA (Módulo 7)
7. Open Finance (Módulo 8)
8. Relatórios + Alertas (Módulo 9)
9. Orçamento (Módulo 10)

## Ambiente
- Node 20+
- Supabase CLI instalado
- Variáveis em `.env.local` (ver `.env.local.example`)
