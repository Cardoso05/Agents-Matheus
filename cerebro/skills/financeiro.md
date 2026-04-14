# Skill: Financeiro

## Sobre
Módulo de controle financeiro pessoal e empresarial do Matheus.
Aceita lançamentos por texto, foto de NF, ou formulário.
Categorização automática por keywords.

## Fluxos financeiros
- **Pessoal**: alimentação, transporte, assinaturas, saúde, educação
- **DELMAT Engenharia**: material, serviço, NFs de obra
- **WIPR**: marketing (Meta Ads), infra
- **ERP**: infra (hosting, APIs)
- **Gruta**: marketing (Meta Ads)

## Receitas conhecidas
- Gruta Máquinas: R$700/mês (retainer)
- ERP Wordfire: R$100/mês (mensalidade)
- DELMAT Engenharia: por projeto (NFs)

## Categorias
- alimentacao, transporte, material, servico, infra
- marketing, assinatura, educacao, saude
- projeto_receita, servico_receita, outros

## Regras
- "gastei X em Y" → registrar como saída, categorizar automaticamente
- "recebi X de Y" → registrar como entrada
- Sempre confirmar categoria inferida se confiança < 0.5
- Separar pessoal de empresarial
- Intelbras, Furukawa, cabo = material de engenharia
- iFood, restaurante = alimentação pessoal
- Meta Ads = marketing (detectar projeto pelo contexto)
