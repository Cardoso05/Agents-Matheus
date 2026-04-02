"""Testes para enums, validação e integração com models."""

import pytest

from cerebro.core.enums import (
    CATEGORIAS_META,
    EMOJI_CATEGORIA,
    EMOJI_STATUS_COMPROMISSO,
    EMOJI_STATUS_JOB,
    CategoriaFato,
    CategoriaFinanceira,
    ProjetoSlug,
    StatusCompromisso,
    StatusJob,
    StatusLancamento,
    StatusPendencia,
    TipoCompromisso,
    TipoJob,
    TipoLancamento,
    validate_enum,
)
from cerebro.db.setup import init_db, get_test_connection


# ── validate_enum ──────────────────────────────────────────


def test_validate_enum_aceita_valor_valido():
    assert validate_enum("pendente", StatusPendencia, "status") == "pendente"
    assert validate_enum("entrada", TipoLancamento, "tipo") == "entrada"
    assert validate_enum("wipr", ProjetoSlug, "projeto") == "wipr"


def test_validate_enum_rejeita_valor_invalido():
    with pytest.raises(ValueError, match="Valor inválido"):
        validate_enum("invalido", StatusPendencia, "status")


def test_validate_enum_strip_whitespace():
    # Espaços são removidos automaticamente
    assert validate_enum("  pendente  ", StatusPendencia, "status") == "pendente"
    # Mas typo real é rejeitado
    with pytest.raises(ValueError, match="Valor inválido"):
        validate_enum("pendenteee", StatusPendencia, "status")


def test_validate_enum_mostra_valores_validos():
    with pytest.raises(ValueError, match="pendente, concluida, cancelada"):
        validate_enum("xyz", StatusPendencia, "status")


# ── StrEnum compatibilidade com strings ────────────────────


def test_strenum_compara_com_string():
    assert StatusPendencia.PENDENTE == "pendente"
    assert TipoLancamento.SAIDA == "saida"
    assert ProjetoSlug.WIPR == "wipr"
    assert CategoriaFinanceira.ALIMENTACAO == "alimentacao"


def test_strenum_funciona_em_dict():
    d = {"pendente": 1, "concluida": 2}
    assert d[StatusPendencia.PENDENTE] == 1


def test_strenum_funciona_em_fstring():
    assert f"status={StatusPendencia.PENDENTE}" == "status=pendente"


# ── Emojis ─────────────────────────────────────────────────


def test_emoji_categoria_tem_todas():
    for cat in CategoriaFinanceira:
        assert cat in EMOJI_CATEGORIA, f"Categoria {cat} sem emoji"


def test_emoji_status_job_tem_todos():
    for s in StatusJob:
        assert s in EMOJI_STATUS_JOB, f"Status {s} sem emoji"


def test_emoji_status_compromisso_tem_todos():
    for s in StatusCompromisso:
        assert s in EMOJI_STATUS_COMPROMISSO, f"Status {s} sem emoji"


# ── CATEGORIAS_META ────────────────────────────────────────


def test_categorias_meta_tem_todas():
    for cat in CategoriaFinanceira:
        assert cat in CATEGORIAS_META, f"Categoria {cat} sem metadados"


def test_categorias_meta_tem_campos_obrigatorios():
    for cat, meta in CATEGORIAS_META.items():
        assert "tipo" in meta, f"{cat} sem 'tipo'"
        assert "emoji" in meta, f"{cat} sem 'emoji'"
        assert "keywords" in meta, f"{cat} sem 'keywords'"
        assert meta["tipo"] in ("entrada", "saida", "ambos"), f"{cat} tipo inválido: {meta['tipo']}"


# ── Integração com models ─────────────────────────────────


@pytest.fixture
def conn():
    c = get_test_connection()
    init_db(c)
    return c


def test_criar_pendencia_rejeita_projeto_invalido(conn):
    from cerebro.db.models import criar_pendencia
    with pytest.raises(ValueError, match="projeto"):
        criar_pendencia("tarefa teste", "projeto_inexistente", conn=conn)


def test_criar_pendencia_aceita_projeto_valido(conn):
    from cerebro.db.models import criar_pendencia
    result = criar_pendencia("tarefa teste", "wipr", conn=conn)
    assert result["projeto"] == "wipr"


def test_criar_lancamento_rejeita_tipo_invalido(conn):
    from cerebro.db.models_finance import criar_lancamento
    with pytest.raises(ValueError, match="tipo"):
        criar_lancamento("xyz", 100, "desc", "alimentacao", conn=conn)


def test_criar_lancamento_rejeita_categoria_invalida(conn):
    from cerebro.db.models_finance import criar_lancamento
    with pytest.raises(ValueError, match="categoria"):
        criar_lancamento("saida", 100, "desc", "cat_inventada", conn=conn)


def test_criar_lancamento_aceita_valores_validos(conn):
    from cerebro.db.models_finance import criar_lancamento
    result = criar_lancamento("saida", 50.0, "iFood almoço", "alimentacao", conn=conn)
    assert result["tipo"] == "saida"
    assert result["categoria"] == "alimentacao"


def test_criar_compromisso_rejeita_tipo_invalido(conn):
    from cerebro.db.models_finance import criar_compromisso
    with pytest.raises(ValueError, match="tipo"):
        criar_compromisso("invalido", "desc", 100, "2026-01-01", conn=conn)


def test_criar_compromisso_aceita_valores_validos(conn):
    from cerebro.db.models_finance import criar_compromisso
    result = criar_compromisso("pagar", "Internet", 100, "2026-01-01", conn=conn)
    assert result["tipo"] == "pagar"


def test_criar_job_rejeita_tipo_invalido(conn):
    from cerebro.db.jobs import criar_job
    with pytest.raises(ValueError, match="tipo"):
        criar_job("tipo_fake", "instruções", conn=conn)


def test_criar_job_aceita_tipo_valido(conn):
    from cerebro.db.jobs import criar_job
    result = criar_job("pesquisa", "Pesquisar CPC", conn=conn)
    assert result["tipo"] == "pesquisa"


def test_atualizar_pendencia_rejeita_status_invalido(conn):
    from cerebro.db.models import criar_pendencia, atualizar_pendencia
    p = criar_pendencia("tarefa", "wipr", conn=conn)
    with pytest.raises(ValueError, match="status"):
        atualizar_pendencia(p["id"], status="status_fake", conn=conn)


def test_registrar_fato_rejeita_categoria_invalida(conn):
    from cerebro.db.models import registrar_fato
    with pytest.raises(ValueError, match="categoria"):
        registrar_fato("wipr", "categoria_fake", "fato teste", conn=conn)


def test_registrar_fato_aceita_valores_validos(conn):
    from cerebro.db.models import registrar_fato
    result = registrar_fato("wipr", "sobre", "Agência de tráfego", conn=conn)
    assert result["categoria"] == "sobre"


# ── Todos os enums têm membros ────────────────────────────


@pytest.mark.parametrize("enum_class", [
    StatusPendencia, StatusCompromisso, StatusJob, StatusLancamento,
    TipoLancamento, TipoCompromisso, TipoJob, ProjetoSlug,
    CategoriaFato, CategoriaFinanceira,
])
def test_enum_nao_vazio(enum_class):
    assert len(enum_class) > 0, f"{enum_class.__name__} está vazio"
