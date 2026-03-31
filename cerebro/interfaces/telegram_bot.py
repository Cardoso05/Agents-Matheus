"""Bot Telegram — interface principal do Cérebro."""

import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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
from cerebro.db.setup import init_db

logger = logging.getLogger(__name__)

# IDs autorizados (apenas Matheus)
AUTHORIZED_USERS: set[int] = set()


def _load_authorized_users():
    """Carrega IDs autorizados do env."""
    ids = os.getenv("TELEGRAM_AUTHORIZED_USERS", "")
    for uid in ids.split(","):
        uid = uid.strip()
        if uid.isdigit():
            AUTHORIZED_USERS.add(int(uid))


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


def _is_authorized(user_id: int) -> bool:
    """Verifica se o usuário está autorizado."""
    if not AUTHORIZED_USERS:
        return True  # Se não configurou, aceita todos (dev mode)
    return user_id in AUTHORIZED_USERS


async def _processar_mensagem(texto: str, user_id: int | None = None) -> str:
    """Rota principal: classifica e executa com memória de conversa."""
    from cerebro.db.conversas import sessao_ativa, registrar_mensagem as reg_msg
    from cerebro.db.metricas import registrar_metrica, medir_tempo

    result = classificar(texto)
    sessao_id = None

    # Obter/criar sessão para contexto
    if user_id is not None:
        sessao_id = sessao_ativa("telegram", str(user_id))
        try:
            reg_msg(sessao_id, "user", texto, "telegram", user_id=str(user_id),
                    projeto=result.get("projeto"), classificacao=result["handler"])
        except Exception:
            pass

    if result["handler"] == "deterministic":
        func = DETERMINISTIC_FUNCS[result["func"]]
        args = result.get("args", {})
        with medir_tempo() as t:
            response = func(**args)
        try:
            registrar_metrica(tipo="deterministic", funcao=result["func"],
                              duracao_ms=t["duracao_ms"])
        except Exception:
            pass
    elif result["handler"] == "agent":
        try:
            from cerebro.core.agent import AgenteGerente
            agente = AgenteGerente()
            response = agente.processar(texto, projeto=result.get("projeto"), sessao_id=sessao_id)
        except Exception as e:
            logger.error(f"Erro no agente: {e}", exc_info=True)
            response = f"❌ Erro no agente: {e}"
    else:
        response = "❌ Handler desconhecido."

    # Registrar resposta na conversa
    if sessao_id:
        try:
            reg_msg(sessao_id, "assistant", response, "telegram", user_id=str(user_id))
        except Exception:
            pass

    return response


# ── Handlers ────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /start."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Acesso não autorizado.")
        return
    await update.message.reply_text(
        "🧠 Cérebro ativo!\n\n"
        "Mande qualquer mensagem e eu processo.\n"
        "Exemplos:\n"
        "• status geral\n"
        "• o que faço agora?\n"
        "• pendências da WIPR\n"
        "• cria tarefa: fazer GIF pro ERP até sexta"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /status."""
    if not _is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(status_geral(), parse_mode="Markdown")


async def cmd_top3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /top3."""
    if not _is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(top_n_do_dia(), parse_mode="Markdown")


async def cmd_atrasadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /atrasadas."""
    if not _is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(atrasadas(), parse_mode="Markdown")


async def cmd_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /semanal."""
    if not _is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(resumo_semanal(), parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler de mensagens de texto genéricas."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Acesso não autorizado.")
        return

    texto = update.message.text
    if not texto:
        return

    # Indica que está processando
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    response = await _processar_mensagem(texto, user_id=update.effective_user.id)

    # Telegram tem limite de 4096 chars por mensagem
    if len(response) <= 4096:
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        # Divide em chunks
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i:i + 4096], parse_mode="Markdown")


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handler global de erros."""
    logger.error(f"Erro no bot: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("❌ Ocorreu um erro interno. Tente novamente.")


# ── Envio proativo de mensagens ─────────────────────────────


async def enviar_mensagem_proativa(app: Application, texto: str):
    """Envia mensagem proativa para todos os usuários autorizados."""
    for user_id in AUTHORIZED_USERS:
        try:
            if len(texto) <= 4096:
                await app.bot.send_message(chat_id=user_id, text=texto, parse_mode="Markdown")
            else:
                for i in range(0, len(texto), 4096):
                    await app.bot.send_message(chat_id=user_id, text=texto[i:i + 4096], parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem proativa para {user_id}: {e}")


# ── Setup e run ─────────────────────────────────────────────


def create_app() -> Application:
    """Cria e configura a Application do Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado no .env")

    _load_authorized_users()
    init_db()

    app = Application.builder().token(token).build()

    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("top3", cmd_top3))
    app.add_handler(CommandHandler("atrasadas", cmd_atrasadas))
    app.add_handler(CommandHandler("semanal", cmd_semanal))

    # Mensagens de texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Erros
    app.add_error_handler(handle_error)

    return app


def run_bot():
    """Inicia o bot em polling mode."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    app = create_app()
    logger.info("🧠 Cérebro Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
