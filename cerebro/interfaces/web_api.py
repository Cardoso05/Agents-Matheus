"""Dashboard Web — Central de Controle (FastAPI)."""

import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from cerebro.db.setup import init_db
from cerebro.db import models, jobs as jobs_db
from cerebro.db.metricas import metricas_periodo, custo_periodo, erros_recentes
from cerebro.db.conversas import historico_sessao
from cerebro.db import models_finance
from cerebro.integrations import calendar
from cerebro.core.config import PROJETOS
from cerebro.core.deterministic import (
    status_geral,
    top_n_do_dia,
    atrasadas,
    resumo_semanal,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Cérebro - Central de Controle")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["finbot_url"] = os.getenv("FINBOT_URL", "")

# Garantir DB ao iniciar
init_db()


# ── Pydantic Models ─────────────────────────────────────────


class NovaPendencia(BaseModel):
    tarefa: str
    projeto: str
    prioridade: int = 3
    prazo: str | None = None
    responsavel: str = "matheus"
    notas: str | None = None


class NovoEvento(BaseModel):
    titulo: str
    data: str
    hora: str | None = None
    duracao_minutos: int = 60
    projeto: str | None = None
    notas: str | None = None


class NovoJob(BaseModel):
    tipo: str
    instrucoes: str
    projeto: str | None = None
    escopo: dict | None = None


class NovoLancamento(BaseModel):
    tipo: str
    valor: float
    descricao: str
    categoria: str
    projeto: str = "pessoal"
    data: str | None = None


class NovoCompromisso(BaseModel):
    tipo: str
    descricao: str
    valor: float
    vencimento: str
    projeto: str = "pessoal"
    credor: str | None = None
    parcela_atual: int | None = None
    parcela_total: int | None = None


class Mensagem(BaseModel):
    texto: str


# ── API Endpoints ───────────────────────────────────────────


@app.get("/api/status")
def api_status():
    """Status geral em JSON."""
    from cerebro.db.setup import get_connection
    conn = get_connection()

    rows = conn.execute(
        """SELECT projeto,
                  COUNT(*) as total,
                  SUM(CASE WHEN prazo < date('now') THEN 1 ELSE 0 END) as atrasadas,
                  SUM(CASE WHEN prioridade <= 2 THEN 1 ELSE 0 END) as urgentes
           FROM pendencias WHERE status = 'pendente' GROUP BY projeto"""
    ).fetchall()

    projetos_status = []
    for r in rows:
        info = PROJETOS.get(r["projeto"], {})
        projetos_status.append({
            "slug": r["projeto"],
            "nome": info.get("nome", r["projeto"]),
            "emoji": info.get("emoji", ""),
            "total": r["total"],
            "atrasadas": r["atrasadas"] or 0,
            "urgentes": r["urgentes"] or 0,
        })

    total = sum(p["total"] for p in projetos_status)
    total_atrasadas = sum(p["atrasadas"] for p in projetos_status)

    return {
        "projetos": projetos_status,
        "total": total,
        "total_atrasadas": total_atrasadas,
    }


@app.get("/api/pendencias")
def api_pendencias(
    projeto: str | None = None,
    status: str | None = None,
    responsavel: str | None = None,
):
    return models.listar_pendencias(projeto=projeto, status=status, responsavel=responsavel)


@app.post("/api/pendencias")
def api_criar_pendencia(p: NovaPendencia):
    return models.criar_pendencia(
        tarefa=p.tarefa, projeto=p.projeto, prioridade=p.prioridade,
        prazo=p.prazo, responsavel=p.responsavel, notas=p.notas,
    )


@app.put("/api/pendencias/{id}/concluir")
def api_concluir_pendencia(id: int):
    result = models.concluir_pendencia(id)
    if not result:
        raise HTTPException(status_code=404, detail="Pendência não encontrada")
    return result


@app.delete("/api/pendencias/{id}")
def api_deletar_pendencia(id: int):
    try:
        ok = models.deletar_pendencia(id)
        if not ok:
            raise HTTPException(status_code=404, detail="Pendência não encontrada")
        return {"ok": True, "id": id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/pendencias/{id}")
def api_atualizar_pendencia(id: int, campos: dict):
    result = models.atualizar_pendencia(id, **campos)
    if not result:
        raise HTTPException(status_code=404, detail="Pendência não encontrada")
    return result


@app.get("/api/eventos")
def api_eventos(
    data_inicio: str | None = None,
    data_fim: str | None = None,
    projeto: str | None = None,
):
    return calendar.listar_eventos(data_inicio=data_inicio, data_fim=data_fim, projeto=projeto)


@app.post("/api/eventos")
def api_criar_evento(e: NovoEvento):
    return calendar.criar_evento(
        titulo=e.titulo, data=e.data, hora=e.hora,
        duracao_minutos=e.duracao_minutos, projeto=e.projeto, notas=e.notas,
    )


@app.put("/api/eventos/{id}")
def api_atualizar_evento(id: int, campos: dict):
    result = calendar.atualizar_evento(id, **campos)
    if not result:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return result


@app.delete("/api/eventos/{id}")
def api_deletar_evento(id: int):
    try:
        ok = calendar.deletar_evento(id)
        if not ok:
            raise HTTPException(status_code=404, detail="Evento não encontrado")
        return {"ok": True, "id": id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
def api_jobs(status: str | None = None, projeto: str | None = None):
    return jobs_db.listar_jobs(status=status, projeto=projeto)


@app.get("/api/jobs/{id}")
def api_job_detail(id: str):
    return jobs_db.get_job(id)


@app.post("/api/jobs")
def api_criar_job(j: NovoJob):
    return jobs_db.criar_job(
        tipo=j.tipo, instrucoes=j.instrucoes,
        projeto=j.projeto, escopo=j.escopo,
    )


@app.get("/api/metricas")
def api_metricas(dias: int = 7):
    return metricas_periodo(dias=dias)


@app.get("/api/metricas/custos")
def api_custos(dias: int = 30):
    return custo_periodo(dias=dias)


# ── Finance API ─────────────────────────────────────────────


@app.get("/api/lancamentos")
def api_lancamentos(
    projeto: str | None = None,
    categoria: str | None = None,
    tipo: str | None = None,
    mes: str | None = None,
):
    return models_finance.listar_lancamentos(
        projeto=projeto, categoria=categoria, tipo=tipo, mes=mes,
    )


@app.post("/api/lancamentos")
def api_criar_lancamento(l: NovoLancamento):
    return models_finance.criar_lancamento(
        tipo=l.tipo, valor=l.valor, descricao=l.descricao,
        categoria=l.categoria, projeto=l.projeto, data=l.data,
    )


@app.delete("/api/lancamentos/{id}")
def api_deletar_lancamento(id: int):
    try:
        ok = models_finance.deletar_lancamento(id)
        if not ok:
            raise HTTPException(status_code=404, detail="Lançamento não encontrado")
        return {"ok": True, "id": id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compromissos")
def api_compromissos(
    tipo: str | None = None,
    status: str | None = None,
    projeto: str | None = None,
):
    return models_finance.listar_compromissos(tipo=tipo, status=status, projeto=projeto)


@app.post("/api/compromissos")
def api_criar_compromisso(c: NovoCompromisso):
    return models_finance.criar_compromisso(
        tipo=c.tipo, descricao=c.descricao, valor=c.valor,
        vencimento=c.vencimento, projeto=c.projeto, credor=c.credor,
        parcela_atual=c.parcela_atual, parcela_total=c.parcela_total,
    )


@app.post("/api/mensagem")
def api_mensagem(m: Mensagem):
    from cerebro.main import processar_mensagem
    response = processar_mensagem(m.texto)
    return {"resposta": response}


# ── Dashboard Pages ─────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request):
    try:
        status = api_status()
    except Exception:
        status = {"projetos": [], "total": 0, "total_atrasadas": 0}
    top3 = top_n_do_dia(n=5)
    atr = atrasadas()
    try:
        metricas = metricas_periodo(dias=7)
    except Exception:
        metricas = {"total_interacoes": 0, "custo_total": 0}

    return templates.TemplateResponse(request, "dashboard.html", {
        "status": status,
        "top5": top3,
        "atrasadas": atr,
        "metricas": metricas,
        "projetos": PROJETOS,
    })


@app.get("/pendencias", response_class=HTMLResponse)
def page_pendencias(request: Request, projeto: str | None = None, status: str | None = None):
    pendencias = models.listar_pendencias(projeto=projeto, status=status or "pendente")
    return templates.TemplateResponse(request, "pendencias.html", {
        "pendencias": pendencias,
        "projeto_filtro": projeto,
        "status_filtro": status or "pendente",
        "projetos": PROJETOS,
    })


@app.get("/calendario", response_class=HTMLResponse)
def page_calendario(request: Request):
    eventos = calendar.eventos_da_semana()
    # Dedup por (titulo, data, hora)
    seen = set()
    deduped = []
    for ev in eventos:
        key = (ev.get("titulo"), ev.get("data"), ev.get("hora"))
        if key not in seen:
            seen.add(key)
            deduped.append(ev)
    return templates.TemplateResponse(request, "calendario.html", {
        "eventos": deduped,
        "projetos": PROJETOS,
    })


@app.get("/jobs", response_class=HTMLResponse)
def page_jobs(request: Request):
    jobs = jobs_db.listar_jobs()
    return templates.TemplateResponse(request, "jobs.html", {
        "jobs": jobs,
        "projetos": PROJETOS,
    })


@app.get("/financeiro", response_class=HTMLResponse)
def page_financeiro(request: Request, mes: str | None = None):
    from datetime import datetime as dt
    if mes is None:
        mes = dt.now().strftime("%Y-%m")
    mes_label = dt.strptime(mes, "%Y-%m").strftime("%B %Y").capitalize()

    # Resumo do mês
    from cerebro.db.setup import get_connection
    conn = get_connection()
    row = conn.execute(
        """SELECT
            COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END), 0) as entradas,
            COALESCE(SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END), 0) as saidas
           FROM lancamentos
           WHERE strftime('%Y-%m', data) = ? AND status != 'cancelado'""",
        (mes,),
    ).fetchone()
    entradas = row["entradas"]
    saidas = row["saidas"]

    # A pagar 7d
    a_pagar_row = conn.execute(
        """SELECT COALESCE(SUM(valor), 0) as total FROM compromissos
           WHERE tipo = 'pagar' AND status IN ('aberto', 'vencido')
             AND vencimento BETWEEN date('now') AND date('now', '+7 days')"""
    ).fetchone()

    # A receber
    a_receber_row = conn.execute(
        """SELECT COALESCE(SUM(valor), 0) as total FROM compromissos
           WHERE tipo = 'receber' AND status = 'aberto'"""
    ).fetchone()

    resumo = {
        "entradas": entradas,
        "saidas": saidas,
        "saldo": entradas - saidas,
        "a_pagar_7d": a_pagar_row["total"],
        "a_receber": a_receber_row["total"],
    }

    # Gastos por categoria
    cat_rows = conn.execute(
        """SELECT categoria, SUM(valor) as total, COUNT(*) as qtd
           FROM lancamentos
           WHERE tipo = 'saida' AND strftime('%Y-%m', data) = ? AND status != 'cancelado'
           GROUP BY categoria ORDER BY total DESC""",
        (mes,),
    ).fetchall()

    emojis = {
        "alimentacao": "🍔", "transporte": "🚗", "material": "🔧",
        "servico": "👷", "infra": "💻", "marketing": "📢",
        "assinatura": "📦", "educacao": "📚", "saude": "💊",
        "projeto_receita": "💰", "servico_receita": "🏗️", "outros": "📝",
    }
    categorias_gastos = []
    for c in cat_rows:
        categorias_gastos.append({
            "categoria": c["categoria"],
            "emoji": emojis.get(c["categoria"], "📝"),
            "total": c["total"],
            "pct": (c["total"] / saidas * 100) if saidas > 0 else 0,
            "qtd": c["qtd"],
        })

    # Últimos lançamentos
    lancamentos = models_finance.listar_lancamentos(mes=mes, limite=30)

    return templates.TemplateResponse(request, "financeiro.html", {
        "mes_label": mes_label,
        "resumo": resumo,
        "categorias_gastos": categorias_gastos,
        "lancamentos": lancamentos,
        "projetos": PROJETOS,
    })


@app.get("/metricas", response_class=HTMLResponse)
def page_metricas(request: Request):
    metricas = metricas_periodo(dias=7)
    custos = custo_periodo(dias=30)
    erros = erros_recentes(dias=7)
    return templates.TemplateResponse(request, "metricas.html", {
        "metricas": metricas,
        "custos": custos,
        "erros_recentes": erros,
    })
