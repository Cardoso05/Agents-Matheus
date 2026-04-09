"""CLI do Cérebro — interface de testes."""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from cerebro.core.classifier import classificar
from cerebro.core.deterministic import (
    atrasadas,
    bloquear_tarefa,
    cancelar_tarefa,
    concluir_tarefa,
    criar_tarefa,
    delegacoes_pendentes,
    delegar_tarefa_det,
    det_encerrar_foco,
    det_iniciar_foco,
    det_pausar_foco,
    det_retomar_foco,
    det_status_foco,
    eventos_semana,
    iniciar_tarefa,
    pendencias_projeto,
    projetos_parados,
    resumo_atividade,
    resumo_semanal,
    status_geral,
    top_n_do_dia,
)
from cerebro.finance.deterministic import (
    registrar_gasto_rapido,
    registrar_receita_rapida,
    resumo_financeiro,
    contas_vencendo,
    contas_vencidas,
)
from cerebro.db.setup import get_connection, init_db
from cerebro.db.metricas import registrar_metrica, medir_tempo
from cerebro.db.conversas import sessao_ativa, registrar_mensagem


# Mapa de funções determinísticas
DETERMINISTIC_FUNCS = {
    "status_geral": status_geral,
    "top_n_do_dia": top_n_do_dia,
    "atrasadas": atrasadas,
    "delegacoes_pendentes": delegacoes_pendentes,
    "projetos_parados": projetos_parados,
    "pendencias_projeto": pendencias_projeto,
    "criar_tarefa": criar_tarefa,
    "concluir_tarefa": concluir_tarefa,
    "iniciar_tarefa": iniciar_tarefa,
    "bloquear_tarefa": bloquear_tarefa,
    "cancelar_tarefa": cancelar_tarefa,
    "delegar_tarefa_det": delegar_tarefa_det,
    "det_iniciar_foco": det_iniciar_foco,
    "det_encerrar_foco": det_encerrar_foco,
    "det_pausar_foco": det_pausar_foco,
    "det_retomar_foco": det_retomar_foco,
    "det_status_foco": det_status_foco,
    "resumo_atividade": resumo_atividade,
    "resumo_semanal": resumo_semanal,
    "eventos_semana": eventos_semana,
    "registrar_gasto": registrar_gasto_rapido,
    "registrar_receita": registrar_receita_rapida,
    "resumo_financeiro": resumo_financeiro,
    "contas_vencendo": contas_vencendo,
    "contas_vencidas": contas_vencidas,
}


def processar_mensagem(mensagem: str, sessao_id: str | None = None) -> str:
    """Rota principal: classifica e executa."""
    result = classificar(mensagem)

    if result["handler"] == "deterministic":
        func = DETERMINISTIC_FUNCS[result["func"]]
        args = result.get("args", {})
        with medir_tempo() as t:
            response = func(**args)
        try:
            registrar_metrica(
                tipo="deterministic", funcao=result["func"],
                projeto=result.get("args", {}).get("projeto"),
                duracao_ms=t["duracao_ms"],
            )
        except Exception:
            pass
        return response

    elif result["handler"] == "agent":
        try:
            from cerebro.core.agent import AgenteGerente
            agente = AgenteGerente()
            return agente.processar(
                mensagem,
                projeto=result.get("projeto"),
                sessao_id=sessao_id,
            )
        except Exception as e:
            return f"❌ Erro no agente: {e}\n\n(Verifique se ANTHROPIC_API_KEY está configurada no .env)"

    return "❌ Handler desconhecido."


def cli_loop():
    """Loop interativo do CLI com memória de conversa."""
    print("🧠 Cérebro v0.1 — Sistema de Gestão")
    print("Digite 'sair' para encerrar.\n")

    sessao_id = sessao_ativa("cli", "cli_user")

    while True:
        try:
            msg = input("👤 Matheus > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Até mais!")
            break

        if not msg:
            continue
        if msg.lower() in ("sair", "exit", "quit"):
            print("👋 Até mais!")
            break

        # Registrar mensagem do usuário
        try:
            registrar_mensagem(sessao_id, "user", msg, "cli", user_id="cli_user")
        except Exception:
            pass

        response = processar_mensagem(msg, sessao_id=sessao_id)
        print(f"\n🤖 Cérebro:\n{response}\n")

        # Registrar resposta
        try:
            registrar_mensagem(sessao_id, "assistant", response, "cli", user_id="cli_user")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Cérebro — Sistema de Gestão")
    parser.add_argument("--seed", action="store_true", help="Popular banco com dados de exemplo")
    parser.add_argument("--status", action="store_true", help="Mostrar status geral")
    parser.add_argument("--top3", action="store_true", help="Mostrar top 3 do dia")
    parser.add_argument("--atrasadas", action="store_true", help="Mostrar atrasadas")
    parser.add_argument("--semanal", action="store_true", help="Mostrar review semanal")
    parser.add_argument("--init-db", action="store_true", help="Inicializar banco de dados")
    parser.add_argument("--telegram", action="store_true", help="Iniciar bot Telegram")
    parser.add_argument("--process-jobs", action="store_true", help="Processar jobs pendentes")
    parser.add_argument("--create-job", nargs=2, metavar=("TIPO", "INSTRUCOES"), help="Criar job (tipo instrucoes)")
    parser.add_argument("--job-projeto", default=None, help="Projeto para --create-job")
    parser.add_argument("--web", action="store_true", help="Iniciar dashboard web")
    parser.add_argument("--web-host", default="127.0.0.1", help="Host do dashboard (default: 127.0.0.1)")
    parser.add_argument("--web-port", type=int, default=8000, help="Porta do dashboard")

    args = parser.parse_args()

    # Garantir que DB existe
    init_db()

    if args.seed:
        from cerebro.db.seed import seed_all
        seed_all()
        print("✅ Banco populado com dados de exemplo.")
        return

    if args.init_db:
        print("✅ Banco de dados inicializado.")
        return

    if args.status:
        print(status_geral())
        return

    if args.top3:
        print(top_n_do_dia())
        return

    if args.atrasadas:
        print(atrasadas())
        return

    if args.semanal:
        print(resumo_semanal())
        return

    if args.telegram:
        _run_telegram()
        return

    if args.create_job:
        from cerebro.db.jobs import criar_job
        tipo, instrucoes = args.create_job
        job = criar_job(tipo=tipo, instrucoes=instrucoes, projeto=args.job_projeto)
        print(f"✅ Job criado: {job['id']} [{tipo}]")
        if args.job_projeto:
            print(f"   Projeto: {args.job_projeto}")
        print(f"   Instruções: {instrucoes}")
        return

    if args.process_jobs:
        from cerebro.workers.runner import processar_proximo_job
        processou = processar_proximo_job()
        if processou:
            print("✅ Job processado.")
        else:
            print("Nenhum job pendente na fila.")
        return

    if args.web:
        _run_web(args.web_host, args.web_port)
        return

    # Modo interativo
    cli_loop()


def _run_telegram():
    """Inicia o bot Telegram com scheduler integrado."""
    import asyncio
    import logging

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    from cerebro.interfaces.telegram_bot import create_app, enviar_mensagem_proativa
    from cerebro.core.scheduler import criar_scheduler, set_notificar_callback

    app = create_app()

    # Conectar scheduler ao Telegram
    async def notificar_via_telegram(texto: str):
        await enviar_mensagem_proativa(app, texto)

    set_notificar_callback(notificar_via_telegram)

    # Iniciar scheduler DEPOIS que o event loop estiver rodando
    scheduler = criar_scheduler()

    async def post_init(application):
        scheduler.start()

    app.post_init = post_init

    print("🧠 Cérebro Bot + Scheduler iniciados!")
    app.run_polling()


def _run_web(host: str = "127.0.0.1", port: int = 8000):
    """Inicia o dashboard web."""
    import uvicorn
    from cerebro.interfaces.web_api import app

    print(f"🧠 Cérebro Dashboard em http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
