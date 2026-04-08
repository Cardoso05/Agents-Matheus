"""Testes para o sistema de triggers condicionais."""

import json
from datetime import datetime, timedelta

import pytest

from cerebro.db.setup import get_test_connection
from cerebro.core.triggers import TRIGGERS
from cerebro.core.trigger_engine import (
    TriggerEngine, listar_status_triggers, toggle_trigger, pausar_trigger,
)


@pytest.fixture
def conn():
    """Conexão de teste com banco em memória."""
    c = get_test_connection()
    return c


def _inserir_pendencia(conn, **kw):
    defaults = {
        "tarefa": "Tarefa teste",
        "projeto": "wipr",
        "prioridade": 3,
        "status": "pendente",
        "responsavel": "matheus",
    }
    defaults.update(kw)
    conn.execute(
        """INSERT INTO pendencias (tarefa, projeto, prioridade, status, responsavel,
           delegado_para, prazo, criado_em, atualizado_em, concluido_em)
           VALUES (:tarefa, :projeto, :prioridade, :status, :responsavel,
           :delegado_para, :prazo, :criado_em, :atualizado_em, :concluido_em)""",
        {
            "delegado_para": defaults.get("delegado_para"),
            "prazo": defaults.get("prazo"),
            "criado_em": defaults.get("criado_em", datetime.now().isoformat()),
            "atualizado_em": defaults.get("atualizado_em", datetime.now().isoformat()),
            "concluido_em": defaults.get("concluido_em"),
            **{k: v for k, v in defaults.items() if k not in ("delegado_para", "prazo", "criado_em", "atualizado_em", "concluido_em")},
        },
    )
    conn.commit()


class TestTriggerRegistry:
    def test_todos_13_triggers_registrados(self):
        assert len(TRIGGERS) == 13

    def test_ids_esperados(self):
        ids = set(TRIGGERS.keys())
        esperados = {f"T{n:02d}" for n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]}
        assert ids == esperados

    def test_todos_tem_avaliar_e_formatar(self):
        for tid, t in TRIGGERS.items():
            assert callable(t.avaliar), f"{tid} sem avaliar"
            assert callable(t.formatar), f"{tid} sem formatar"

    def test_prioridades_validas(self):
        for tid, t in TRIGGERS.items():
            assert t.prioridade in ("alta", "media", "baixa"), f"{tid}: {t.prioridade}"


class TestTriggerT05TarefasSemPrazo:
    def test_nao_dispara_sem_dados(self, conn):
        result = TRIGGERS["T05"].avaliar(conn)
        assert result is None

    def test_nao_dispara_com_2_sem_prazo(self, conn):
        _inserir_pendencia(conn, tarefa="T1", projeto="wipr")
        _inserir_pendencia(conn, tarefa="T2", projeto="wipr")
        result = TRIGGERS["T05"].avaliar(conn)
        assert result is None

    def test_dispara_com_3_sem_prazo(self, conn):
        for i in range(3):
            _inserir_pendencia(conn, tarefa=f"T{i}", projeto="wipr")
        result = TRIGGERS["T05"].avaliar(conn)
        assert result is not None
        assert result[0]["projeto"] == "wipr"
        assert result[0]["sem_prazo"] == 3

    def test_formatar(self, conn):
        dados = [{"projeto": "wipr", "sem_prazo": 5}]
        msg = TRIGGERS["T05"].formatar(dados)
        assert "WIPR" in msg
        assert "5 tarefas sem prazo" in msg


class TestTriggerT08P1P2Paradas:
    def test_nao_dispara_p3(self, conn):
        antigo = (datetime.now() - timedelta(days=5)).isoformat()
        _inserir_pendencia(conn, prioridade=3, atualizado_em=antigo)
        result = TRIGGERS["T08"].avaliar(conn)
        assert result is None

    def test_dispara_p1_parada(self, conn):
        antigo = (datetime.now() - timedelta(days=4)).isoformat()
        _inserir_pendencia(conn, tarefa="Urgente", prioridade=1, atualizado_em=antigo)
        result = TRIGGERS["T08"].avaliar(conn)
        assert result is not None
        assert result[0]["prioridade"] == 1


class TestTriggerT06DelegacaoEnvelhecendo:
    def test_nao_dispara_sem_delegacao(self, conn):
        _inserir_pendencia(conn)
        result = TRIGGERS["T06"].avaliar(conn)
        assert result is None

    def test_dispara_delegacao_velha(self, conn):
        antigo = (datetime.now() - timedelta(days=6)).isoformat()
        _inserir_pendencia(conn, delegado_para="Pai", atualizado_em=antigo)
        result = TRIGGERS["T06"].avaliar(conn)
        assert result is not None
        assert result[0]["delegado_para"] == "Pai"


class TestTriggerT10SemanaSemConcluir:
    def test_nao_dispara_com_conclusao_recente(self, conn):
        ontem = (datetime.now() - timedelta(days=1)).isoformat()
        _inserir_pendencia(conn, status="concluida", concluido_em=ontem)
        result = TRIGGERS["T10"].avaliar(conn)
        assert result is None

    def test_dispara_sem_conclusao_5_dias(self, conn):
        antigo = (datetime.now() - timedelta(days=6)).isoformat()
        _inserir_pendencia(conn, status="concluida", concluido_em=antigo)
        _inserir_pendencia(conn, tarefa="Pendente")  # pendente pra contar
        result = TRIGGERS["T10"].avaliar(conn)
        assert result is not None
        assert result[0]["dias"] >= 5


class TestTriggerEngine:
    def test_engine_sem_dados_nao_notifica(self, conn):
        engine = TriggerEngine(conn, check_silencio=False)
        msgs = engine.avaliar_todos()
        assert msgs == []

    def test_cooldown_impede_repeticao(self, conn):
        # Criar dados que disparam T05
        for i in range(3):
            _inserir_pendencia(conn, tarefa=f"T{i}", projeto="erp")
        engine = TriggerEngine(conn, check_silencio=False)

        msgs1 = engine.avaliar_todos()
        t05_disparou = any("sem prazo" in m.lower() for m in msgs1)
        assert t05_disparou

        # Segunda avaliação - cooldown deve impedir
        msgs2 = engine.avaliar_todos()
        t05_disparou2 = any("sem prazo" in m.lower() for m in msgs2)
        assert not t05_disparou2

    def test_trigger_desativado_nao_dispara(self, conn):
        for i in range(3):
            _inserir_pendencia(conn, tarefa=f"T{i}", projeto="erp")
        toggle_trigger(conn, "T05", False)
        engine = TriggerEngine(conn, check_silencio=False)
        msgs = engine.avaliar_todos()
        t05_disparou = any("sem prazo" in m.lower() for m in msgs)
        assert not t05_disparou

    def test_trigger_pausado_nao_dispara(self, conn):
        for i in range(3):
            _inserir_pendencia(conn, tarefa=f"T{i}", projeto="erp")
        pausar_trigger(conn, "T05", dias=7)
        engine = TriggerEngine(conn, check_silencio=False)
        msgs = engine.avaliar_todos()
        t05_disparou = any("sem prazo" in m.lower() for m in msgs)
        assert not t05_disparou

    def test_antispam_max_3(self, conn):
        # Criar dados que disparam vários triggers
        antigo = (datetime.now() - timedelta(days=10)).isoformat()
        for i in range(20):
            _inserir_pendencia(
                conn, tarefa=f"Definir algo {i}", projeto="wipr",
                prioridade=1, atualizado_em=antigo, criado_em=antigo,
            )
        engine = TriggerEngine(conn, check_silencio=False)
        msgs = engine.avaliar_todos()
        # Deve ter no máximo MAX + 1 (o resumo)
        assert len(msgs) <= 4


class TestHelpers:
    def test_listar_status(self, conn):
        status = listar_status_triggers(conn)
        assert len(status) == 13
        assert all("id" in s for s in status)
        assert all("nome" in s for s in status)

    def test_toggle_trigger(self, conn):
        assert toggle_trigger(conn, "T05", False)
        status = listar_status_triggers(conn)
        t05 = next(s for s in status if s["id"] == "T05")
        assert not t05["ativo"]

    def test_toggle_inexistente(self, conn):
        assert not toggle_trigger(conn, "T99", True)

    def test_pausar_trigger(self, conn):
        assert pausar_trigger(conn, "T05", dias=7)
        status = listar_status_triggers(conn)
        t05 = next(s for s in status if s["id"] == "T05")
        assert t05["pausado_ate"] is not None
