"""Trigger Engine — avalia triggers condicionais e notifica quando relevante."""

import json
import logging
from datetime import datetime

from cerebro.core.triggers import TRIGGERS, TriggerDef

logger = logging.getLogger(__name__)

MAX_NOTIFICACOES_POR_CICLO = 3


class TriggerEngine:
    """Avalia triggers condicionais e retorna mensagens de notificação."""

    def __init__(self, conn, check_silencio: bool = True):
        self.conn = conn
        self.check_silencio = check_silencio

    def avaliar_todos(self) -> list[str]:
        """Avalia todos os triggers ativos. Retorna lista de mensagens."""
        mensagens = []

        # Ordenar por prioridade: alta primeiro
        ordem = {"alta": 0, "media": 1, "baixa": 2}
        triggers_ordenados = sorted(TRIGGERS.values(), key=lambda t: ordem.get(t.prioridade, 9))

        for trigger in triggers_ordenados:
            try:
                if not self._esta_ativo(trigger):
                    continue
                if self.check_silencio and self._em_silencio(trigger):
                    continue
                if self._em_cooldown(trigger):
                    continue

                resultado = trigger.avaliar(self.conn)

                if resultado:
                    msg = trigger.formatar(resultado)
                    self._registrar_disparo(trigger.id, resultado)
                    mensagens.append(msg)
                    logger.info(f"Trigger {trigger.id} disparou: {trigger.nome}")

            except Exception as e:
                logger.error(f"Erro ao avaliar trigger {trigger.id}: {e}", exc_info=True)

        # Anti-spam: max N por ciclo
        if len(mensagens) > MAX_NOTIFICACOES_POR_CICLO:
            extras = len(mensagens) - MAX_NOTIFICACOES_POR_CICLO
            mensagens = mensagens[:MAX_NOTIFICACOES_POR_CICLO]
            mensagens.append(f"📋 +{extras} alerta(s) adicional(is). Use /triggers para ver todos.")

        return mensagens

    def _esta_ativo(self, trigger: TriggerDef) -> bool:
        """Verifica se o trigger está ativo (não desativado nem pausado)."""
        row = self.conn.execute(
            "SELECT ativo, pausado_ate FROM trigger_config WHERE id = ?",
            (trigger.id,),
        ).fetchone()

        if not row:
            return True  # Sem config = ativo por padrão

        if not row["ativo"]:
            return False

        if row["pausado_ate"]:
            try:
                pausado_ate = datetime.fromisoformat(row["pausado_ate"])
                if datetime.now() < pausado_ate:
                    return False
            except ValueError:
                pass

        return True

    def _em_silencio(self, trigger: TriggerDef) -> bool:
        """Verifica se estamos no horário de silêncio (ex: 22h-8h)."""
        hora = datetime.now().hour
        inicio = trigger.silencio_inicio
        fim = trigger.silencio_fim

        if inicio > fim:  # Cruza meia-noite (ex: 22 a 8)
            return hora >= inicio or hora < fim
        return inicio <= hora < fim

    def _em_cooldown(self, trigger: TriggerDef) -> bool:
        """Verifica se o trigger já disparou dentro do período de cooldown."""
        # Verificar cooldown customizado
        config = self.conn.execute(
            "SELECT cooldown_horas FROM trigger_config WHERE id = ?",
            (trigger.id,),
        ).fetchone()
        cooldown = (config["cooldown_horas"] if config and config["cooldown_horas"] else trigger.cooldown_horas)

        row = self.conn.execute(
            """SELECT timestamp FROM trigger_log
               WHERE trigger_id = ? AND notificado = 1
               ORDER BY timestamp DESC LIMIT 1""",
            (trigger.id,),
        ).fetchone()

        if not row:
            return False

        try:
            ultimo = datetime.fromisoformat(row["timestamp"])
            horas_desde = (datetime.now() - ultimo).total_seconds() / 3600
            return horas_desde < cooldown
        except (ValueError, TypeError):
            return False

    def _registrar_disparo(self, trigger_id: str, dados: list[dict]):
        """Registra o disparo no log para controle de cooldown."""
        self.conn.execute(
            "INSERT INTO trigger_log (trigger_id, dados) VALUES (?, ?)",
            (trigger_id, json.dumps(dados, default=str, ensure_ascii=False)),
        )
        self.conn.commit()


# ── Helpers para consulta externa ─────────────────────────────


def listar_status_triggers(conn) -> list[dict]:
    """Retorna status de todos os triggers para exibição."""
    resultado = []
    for trigger in TRIGGERS.values():
        # Status ativo/pausado
        config = conn.execute(
            "SELECT ativo, pausado_ate, cooldown_horas FROM trigger_config WHERE id = ?",
            (trigger.id,),
        ).fetchone()

        ativo = True
        pausado_ate = None
        cooldown_custom = None
        if config:
            ativo = bool(config["ativo"])
            pausado_ate = config["pausado_ate"]
            cooldown_custom = config["cooldown_horas"]

        # Último disparo
        ultimo = conn.execute(
            "SELECT timestamp FROM trigger_log WHERE trigger_id = ? ORDER BY timestamp DESC LIMIT 1",
            (trigger.id,),
        ).fetchone()

        resultado.append({
            "id": trigger.id,
            "nome": trigger.nome,
            "descricao": trigger.descricao,
            "prioridade": trigger.prioridade,
            "cooldown_horas": cooldown_custom or trigger.cooldown_horas,
            "ativo": ativo,
            "pausado_ate": pausado_ate,
            "ultimo_disparo": ultimo["timestamp"] if ultimo else None,
        })

    return sorted(resultado, key=lambda t: t["id"])


def toggle_trigger(conn, trigger_id: str, ativo: bool) -> bool:
    """Ativa ou desativa um trigger."""
    if trigger_id not in TRIGGERS:
        return False
    conn.execute(
        """INSERT INTO trigger_config (id, ativo) VALUES (?, ?)
           ON CONFLICT(id) DO UPDATE SET ativo = ?""",
        (trigger_id, int(ativo), int(ativo)),
    )
    conn.commit()
    return True


def pausar_trigger(conn, trigger_id: str, dias: int = 7) -> bool:
    """Pausa um trigger por N dias."""
    if trigger_id not in TRIGGERS:
        return False
    from datetime import timedelta
    pausado_ate = (datetime.now() + timedelta(days=dias)).isoformat()
    conn.execute(
        """INSERT INTO trigger_config (id, pausado_ate) VALUES (?, ?)
           ON CONFLICT(id) DO UPDATE SET pausado_ate = ?""",
        (trigger_id, pausado_ate, pausado_ate),
    )
    conn.commit()
    return True
