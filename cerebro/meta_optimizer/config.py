"""Thresholds e parâmetros do optimizer.

Valores calibrados pra conta Gruta Máquinas (campanhas de conversa iniciada).
"""

from __future__ import annotations


class Config:
    # CPR (Custo Por Resultado) em BRL — faixas de saúde
    CPR_EXCELENTE = 2.50
    CPR_BOM = 4.00
    CPR_ATENCAO = 5.50
    CPR_CRITICO = 7.00

    # Variação CPR vs período anterior (fração: 0.20 = +20%)
    VARIACAO_ALERTA = 0.20
    VARIACAO_URGENTE = 0.30
    VARIACAO_ESCALAR = -0.15

    # Frequência média de impressões/usuário
    FREQUENCIA_ALERTA = 3.0
    FREQUENCIA_FADIGA = 4.0

    # Filtros pra entrar na análise
    MIN_RESULTADOS = 3
    MIN_GASTO = 10.0

    # Concentração: campanha consome >30% do budget total
    MAX_BUDGET_SHARE = 0.30

    # Quantos dias consecutivos de piora ativam alerta de tendência
    DIAS_PIORA_CONSECUTIVA = 2
