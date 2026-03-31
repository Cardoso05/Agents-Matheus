"""Configuração central do Cérebro."""

import os
from pathlib import Path

# Diretórios
ROOT_DIR = Path(__file__).parent.parent
SKILLS_DIR = ROOT_DIR / "skills"
DB_PATH = ROOT_DIR / "db" / "cerebro.db"

# Modelo LLM
MODEL = "claude-sonnet-4-20250514"

# Projetos e prioridades
PROJETOS = {
    "wipr": {"nome": "WIPR", "prioridade": 1, "emoji": "\U0001f534"},
    "erp": {"nome": "DELMAT ERP", "prioridade": 2, "emoji": "\U0001f534"},
    "engenharia": {"nome": "DELMAT Engenharia", "prioridade": 3, "emoji": "\U0001f7e1"},
    "gruta": {"nome": "Gruta Máquinas", "prioridade": 4, "emoji": "\U0001f7e1"},
    "faculdade": {"nome": "Faculdade", "prioridade": 5, "emoji": "\U0001f7e2"},
}

# Aliases para detecção flexível de projeto
PROJETO_ALIASES = {
    # WIPR
    "wipr": "wipr",
    "wi": "wipr",
    "tráfego": "wipr",
    "trafego": "wipr",
    # ERP
    "erp": "erp",
    "delmat erp": "erp",
    # Engenharia
    "engenharia": "engenharia",
    "eng": "engenharia",
    "delmat eng": "engenharia",
    "delmat engenharia": "engenharia",
    "vibropac": "engenharia",
    "igreja universal": "engenharia",
    "fr instalações": "engenharia",
    "fr instalacoes": "engenharia",
    "cml": "engenharia",
    "planova": "engenharia",
    # Gruta
    "gruta": "gruta",
    "gruta máquinas": "gruta",
    "gruta maquinas": "gruta",
    # Faculdade
    "faculdade": "faculdade",
    "facu": "faculdade",
}

# Ordem de prioridade para sorting
PRIORIDADE_PROJETO_ORDER = ["wipr", "erp", "engenharia", "gruta", "faculdade"]
