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

from cerebro.core.classifier import classificar, detectar_projeto
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


# Mapa de funções determinísticas (deve ser idêntico ao main.py)
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
    user_id = update.effective_user.id

    if not _is_authorized(user_id):
        await update.message.reply_text(
            f"⛔ Acesso não autorizado.\n\n"
            f"Seu user ID: `{user_id}`\n"
            f"Adicione no .env:\n"
            f"`TELEGRAM_AUTHORIZED_USERS={user_id}`\n"
            f"E reinicie o serviço.",
            parse_mode="Markdown",
        )
        return

    msg = (
        "🧠 Cérebro ativo!\n\n"
        "Mande qualquer mensagem e eu processo.\n"
        "Exemplos:\n"
        "• status geral\n"
        "• o que faço agora?\n"
        "• pendências da WIPR\n"
        "• cria tarefa: fazer GIF pro ERP até sexta"
    )
    if not AUTHORIZED_USERS:
        msg += f"\n\n⚠️ Modo aberto (sem auth). Seu ID: `{user_id}`"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def _safe_reply(message, text: str):
    """Envia mensagem com Markdown, fallback pra texto plano se falhar."""
    chunks = [text[i:i + 4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await message.reply_text(chunk)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /status."""
    if not _is_authorized(update.effective_user.id):
        return
    await _safe_reply(update.message, status_geral())


async def cmd_top3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /top3."""
    if not _is_authorized(update.effective_user.id):
        return
    await _safe_reply(update.message, top_n_do_dia())


async def cmd_atrasadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /atrasadas."""
    if not _is_authorized(update.effective_user.id):
        return
    await _safe_reply(update.message, atrasadas())


async def cmd_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /semanal."""
    if not _is_authorized(update.effective_user.id):
        return
    await _safe_reply(update.message, resumo_semanal())


async def cmd_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do /triggers — mostra status dos triggers condicionais."""
    if not _is_authorized(update.effective_user.id):
        return
    from cerebro.core.trigger_engine import listar_status_triggers
    from cerebro.db.setup import get_connection

    status = listar_status_triggers(get_connection())
    emoji_prio = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}

    linhas = ["🔔 **Triggers Condicionais**\n"]
    for s in status:
        prio = emoji_prio.get(s["prioridade"], "⚪")
        if not s["ativo"]:
            estado = "❌ desativado"
        elif s.get("pausado_ate"):
            estado = f"⏸ pausado até {s['pausado_ate'][:10]}"
        else:
            estado = "✅ ativo"

        ultimo = f"há {_tempo_relativo(s['ultimo_disparo'])}" if s["ultimo_disparo"] else "nunca"
        linhas.append(f"{prio} `{s['id']}` {s['nome']} — {estado} — último: {ultimo}")

    await _safe_reply(update.message, "\n".join(linhas))


def _tempo_relativo(timestamp_str: str) -> str:
    """Converte timestamp ISO em texto relativo (ex: '2 dias')."""
    from cerebro.clock import agora
    try:
        dt = datetime.fromisoformat(timestamp_str)
        delta = agora() - dt
        if delta.days > 0:
            return f"{delta.days} dia(s)"
        horas = int(delta.total_seconds() / 3600)
        if horas > 0:
            return f"{horas}h"
        return f"{int(delta.total_seconds() / 60)} min"
    except (ValueError, TypeError):
        return "?"


async def _interceptar_foco(texto: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Intercepta mensagens durante foco ativo. Retorna True se interceptou."""
    from cerebro.db.models import foco_ativo, get_pendencia
    from cerebro.clock import agora

    foco = foco_ativo()
    if not foco or foco["status"] != "ativo":
        return False

    texto_lower = texto.lower()

    # Sempre deixa passar comandos de foco
    foco_cmds = [
        "encerrar foco", "parar foco", "pausar foco", "sai do foco",
        "saí do foco", "fim do foco", "status foco", "retomar foco",
    ]
    if any(cmd in texto_lower for cmd in foco_cmds):
        return False

    # Sempre deixa passar conclusão/bloqueio da tarefa em foco
    result = classificar(texto)
    task_id = result.get("args", {}).get("id")
    if task_id == foco["pendencia_id"] and result.get("func") in (
        "concluir_tarefa", "bloquear_tarefa", "iniciar_tarefa",
    ):
        return False

    # Detectar troca de projeto
    projeto_msg = detectar_projeto(texto)
    if projeto_msg and projeto_msg != foco.get("projeto"):
        pendencia = get_pendencia(foco["pendencia_id"])
        tarefa_nome = pendencia["tarefa"][:40] if pendencia else "?"
        inicio = datetime.fromisoformat(foco["inicio"])
        minutos = int((agora() - inicio).total_seconds() / 60)
        await _safe_reply(
            update.message,
            f"⚠️ **Modo Foco ativo** ({minutos} min)\n"
            f"Trabalhando em: #{foco['pendencia_id']} {tarefa_nome} [{foco['projeto'].upper()}]\n\n"
            f"Você está mudando para {projeto_msg.upper()}.\n"
            f"Quer continuar? Diz 'encerrar foco' antes ou responda novamente."
        )
        return True

    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler de mensagens de texto genéricas."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Acesso não autorizado.")
        return

    texto = update.message.text
    if not texto:
        return

    # Interceptor de foco — avisa sobre troca de projeto
    interceptado = await _interceptar_foco(texto, update, context)
    if interceptado:
        return

    # Indica que está processando
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    response = await _processar_mensagem(texto, user_id=update.effective_user.id)

    await _safe_reply(update.message, response)


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
    app.add_handler(CommandHandler("triggers", cmd_triggers))

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
