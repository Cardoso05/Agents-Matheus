"""Dashboard Web — Central de Controle (FastAPI)."""

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from cerebro.db.setup import init_db
from cerebro.db import models, jobs as jobs_db
from cerebro.db.metricas import metricas_periodo, custo_periodo
from cerebro.db.conversas import historico_sessao
from cerebro.integrations import calendar
from cerebro.core.config import PROJETOS
from cerebro.core.deterministic import (
    status_geral,
    top_n_do_dia,
    atrasadas,
    resumo_semanal,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="Cérebro - Central de Controle")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

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
        return {"error": "Pendência não encontrada"}
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


@app.get("/api/jobs")
def api_jobs(status: str | None = None, projeto: str | None = None):
    return jobs_db.listar_jobs(status=status, projeto=projeto)


@app.get("/api/jobs/{id}")
def api_job_detail(id: str):
    return jobs_db.get_job(id)


@app.get("/api/metricas")
def api_metricas(dias: int = 7):
    return metricas_periodo(dias=dias)


@app.get("/api/metricas/custos")
def api_custos(dias: int = 30):
    return custo_periodo(dias=dias)


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

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "status": status,
        "top5": top3,
        "atrasadas": atr,
        "metricas": metricas,
        "projetos": PROJETOS,
    })


@app.get("/pendencias", response_class=HTMLResponse)
def page_pendencias(request: Request, projeto: str | None = None, status: str | None = None):
    pendencias = models.listar_pendencias(projeto=projeto, status=status or "pendente")
    return templates.TemplateResponse("pendencias.html", {
        "request": request,
        "pendencias": pendencias,
        "projeto_filtro": projeto,
        "status_filtro": status or "pendente",
        "projetos": PROJETOS,
    })


@app.get("/calendario", response_class=HTMLResponse)
def page_calendario(request: Request):
    eventos = calendar.eventos_da_semana()
    return templates.TemplateResponse("calendario.html", {
        "request": request,
        "eventos": eventos,
    })


@app.get("/jobs", response_class=HTMLResponse)
def page_jobs(request: Request):
    jobs = jobs_db.listar_jobs()
    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "jobs": jobs,
    })


@app.get("/metricas", response_class=HTMLResponse)
def page_metricas(request: Request):
    metricas = metricas_periodo(dias=7)
    custos = custo_periodo(dias=30)
    return templates.TemplateResponse("metricas.html", {
        "request": request,
        "metricas": metricas,
        "custos": custos,
    })
