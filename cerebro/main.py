"""CLI do Cérebro — interface de testes."""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from cerebro.core.classifier import classificar
from cerebro.core.deterministic import (
    atrasadas,
    concluir_tarefa,
    criar_tarefa,
    delegacoes_pendentes,
    pendencias_projeto,
    projetos_parados,
    resumo_semanal,
    status_geral,
    top_n_do_dia,
)
from cerebro.db.setup import get_connection, init_db


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
    "resumo_semanal": resumo_semanal,
}


def processar_mensagem(mensagem: str) -> str:
    """Rota principal: classifica e executa."""
    result = classificar(mensagem)

    if result["handler"] == "deterministic":
        func = DETERMINISTIC_FUNCS[result["func"]]
        args = result.get("args", {})
        return func(**args)

    elif result["handler"] == "agent":
        try:
            from cerebro.core.agent import AgenteGerente
            agente = AgenteGerente()
            return agente.processar(mensagem, projeto=result.get("projeto"))
        except Exception as e:
            return f"❌ Erro no agente: {e}\n\n(Verifique se ANTHROPIC_API_KEY está configurada no .env)"

    return "❌ Handler desconhecido."


def cli_loop():
    """Loop interativo do CLI."""
    print("🧠 Cérebro v0.1 — Sistema de Gestão")
    print("Digite 'sair' para encerrar.\n")

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

        response = processar_mensagem(msg)
        print(f"\n🤖 Cérebro:\n{response}\n")


def main():
    parser = argparse.ArgumentParser(description="Cérebro — Sistema de Gestão")
    parser.add_argument("--seed", action="store_true", help="Popular banco com dados de exemplo")
    parser.add_argument("--status", action="store_true", help="Mostrar status geral")
    parser.add_argument("--top3", action="store_true", help="Mostrar top 3 do dia")
    parser.add_argument("--atrasadas", action="store_true", help="Mostrar atrasadas")
    parser.add_argument("--semanal", action="store_true", help="Mostrar review semanal")
    parser.add_argument("--init-db", action="store_true", help="Inicializar banco de dados")

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

    # Modo interativo
    cli_loop()


if __name__ == "__main__":
    main()
