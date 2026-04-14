#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Notificação Telegram — chamado pelo deploy.sh
# Uso: bash notify.sh <status> <message>
# Status: success | warning | critical
# ══════════════════════════════════════════════════════════════

STATUS="${1:-info}"
MESSAGE="${2:-Deploy update}"

# Carregar env
set -a
source /opt/cerebro/.env 2>/dev/null || true
set +a

BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_AUTHORIZED_USERS%%,*}"  # Primeiro user ID

if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "Telegram não configurado (BOT_TOKEN ou CHAT_ID vazio)"
    exit 0
fi

case "$STATUS" in
    success)  EMOJI="✅" ;;
    warning)  EMOJI="⚠️" ;;
    critical) EMOJI="🚨" ;;
    *)        EMOJI="📦" ;;
esac

curl -sf --max-time 10 \
    -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d chat_id="$CHAT_ID" \
    -d parse_mode="Markdown" \
    -d text="${EMOJI} *Deploy Cérebro*

${MESSAGE}" > /dev/null 2>&1 || true
