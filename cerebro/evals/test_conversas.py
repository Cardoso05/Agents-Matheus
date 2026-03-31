"""Testes do módulo de conversas."""

import pytest

from cerebro.db.setup import get_test_connection
from cerebro.db.conversas import (
    criar_sessao,
    sessao_ativa,
    registrar_mensagem,
    historico_sessao,
    formatar_historico_para_prompt,
)


@pytest.fixture
def conn():
    return get_test_connection()


class TestCriarSessao:

    def test_cria_id_unico(self):
        s1 = criar_sessao("cli")
        s2 = criar_sessao("cli")
        assert s1 != s2
        assert s1.startswith("sess_")


class TestSessaoAtiva:

    def test_cria_nova_se_nao_existe(self, conn):
        s = sessao_ativa("cli", "user1", conn=conn)
        assert s.startswith("sess_")

    def test_reutiliza_sessao_recente(self, conn):
        s1 = sessao_ativa("cli", "user1", conn=conn)
        registrar_mensagem(s1, "user", "oi", "cli", user_id="user1", conn=conn)

        s2 = sessao_ativa("cli", "user1", conn=conn)
        assert s2 == s1


class TestRegistrarMensagem:

    def test_registra_user(self, conn):
        m = registrar_mensagem("sess_abc", "user", "status geral", "cli", conn=conn)
        assert m["role"] == "user"
        assert m["conteudo"] == "status geral"
        assert m["sessao_id"] == "sess_abc"

    def test_registra_assistant(self, conn):
        m = registrar_mensagem("sess_abc", "assistant", "Tudo ok!", "cli", conn=conn)
        assert m["role"] == "assistant"


class TestHistoricoSessao:

    def test_retorna_em_ordem(self, conn):
        registrar_mensagem("sess_1", "user", "msg1", "cli", conn=conn)
        registrar_mensagem("sess_1", "assistant", "resp1", "cli", conn=conn)
        registrar_mensagem("sess_1", "user", "msg2", "cli", conn=conn)

        hist = historico_sessao("sess_1", conn=conn)
        assert len(hist) == 3
        assert hist[0]["conteudo"] == "msg1"
        assert hist[1]["conteudo"] == "resp1"
        assert hist[2]["conteudo"] == "msg2"

    def test_limite(self, conn):
        for i in range(25):
            registrar_mensagem("sess_big", "user", f"msg{i}", "cli", conn=conn)

        hist = historico_sessao("sess_big", limite=10, conn=conn)
        assert len(hist) == 10

    def test_sessao_vazia(self, conn):
        hist = historico_sessao("sess_inexistente", conn=conn)
        assert hist == []


class TestFormatarHistorico:

    def test_formato_api(self, conn):
        registrar_mensagem("sess_fmt", "user", "oi", "cli", conn=conn)
        registrar_mensagem("sess_fmt", "assistant", "olá!", "cli", conn=conn)

        msgs = formatar_historico_para_prompt("sess_fmt", conn=conn)
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "oi"}
        assert msgs[1] == {"role": "assistant", "content": "olá!"}

    def test_vazio(self, conn):
        msgs = formatar_historico_para_prompt("sess_vazia", conn=conn)
        assert msgs == []
