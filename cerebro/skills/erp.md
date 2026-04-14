# Skill: DELMAT ERP

## Sobre
Sistema ERP/CRM desenvolvido pelo Matheus para a DELMAT Engenharia, transformado em produto SaaS.
- Stack: PHP 7.4+, MySQL, Apache, Server-side rendering
- Migrou com sucesso para multi-tenant (database per tenant)
- Hospedado em VPS (migrou de hospedagem compartilhada HostGator)
- Preço: R$1.000 setup + R$100/mês (precisa precificar melhor — está barato pro que entrega)

## Módulos do sistema
- Comercial (oportunidades, clientes, Kanban, CPQ/propostas)
- Operacional (obras, diários, vistorias)
- Financeiro (entradas, saídas, contas a pagar/receber, DRE, fluxo de caixa)
- Compras (RFQ, mapa de preços, ordens de compra, recebimentos, fornecedores)
- RH (funcionários, candidatos, avaliações, Kanban RH)
- Tarefas pessoais, reembolsos, feedbacks, notificações
- Home personalizável com widgets
- Sistema de permissões (Admin, Padrão, Leitura)
- Landing page integrada com formulários que alimentam o CRM

## Pessoas
- **Pai**: stakeholder principal, usa o sistema diariamente
- **Léo (Wordfire)**: primeiro cliente. NÃO RESPONDE sobre pagamento (R$1.000 setup) e verificação de identidade do Google Ads. Cobrar com insistência.

## Status atual
- Multi-tenant funcionando. Wordfire é o primeiro cliente ativo.
- Marketing parado — pendências acumuladas:
  - 3 GIFs tutorial (módulo estoque, etc.) — ~2-3h de trabalho
  - og:image 1200x630 no Canva (~15 min)
  - Número WhatsApp na landing page (~2 min)
  - Subir GIFs e og:image via FTP (~10 min)
  - Testar preview no Facebook Sharing Debugger (~5 min)
  - Arrumar perfil pessoal do Facebook (~10 min)
  - Mapear 5-10 grupos no Facebook (~30 min)
  - Escrever 3 textos de post (~20 min)
  - Configurar Calendly (~15 min)
- Léo não paga e não faz verificação Google Ads — bloqueando campanha Wordfire
- Meta: 5+ clientes para ativar projeto Procurement/Fintech

## Regras específicas
- Módulo financeiro é CRÍTICO — qualquer alteração precisa de teste rigoroso
- Priorizar estabilidade sobre features novas
- Bugs reportados pelo pai = urgência alta (ele usa diariamente)
- GIFs e tutoriais ajudam na adoção — investir tempo nisso
- R$100/mês está barato — precisa montar tabela de precificação

## Projetos derivados (futuro)
- **Procurement/Fintech**: sistema derivado do ERP. Só ativar quando ERP tiver 5+ clientes.
  - Arthur: pesquisando mercado
  - Marcos: precisa receber briefing completo da ideia
  - Depende da base de dados do ERP (empresas cadastradas)
