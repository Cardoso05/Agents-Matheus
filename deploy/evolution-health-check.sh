#!/usr/bin/env bash
# Health check para Evolution API
# Agendar no crontab: */10 * * * * /opt/evolution-api/health-check.sh >> /opt/evolution-api/health-check.log 2>&1
set -euo pipefail

ENV_FILE="/opt/evolution-api/.env"
COMPOSE_DIR="/opt/evolution-api"
INSTANCE_NAME="delmat-principal"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# Carrega API key do .env
if [[ ! -f "$ENV_FILE" ]]; then
    echo "$LOG_PREFIX ERRO: Arquivo .env não encontrado em $ENV_FILE"
    exit 1
fi
API_KEY=$(grep '^AUTHENTICATION_API_KEY=' "$ENV_FILE" | cut -d'=' -f2)

# Verifica status da API
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    -H "apikey: $API_KEY" \
    "https://wpp.cardosomatheus.com.br/instance/connectionState/$INSTANCE_NAME" 2>/dev/null || echo "000")

if [[ "$HTTP_STATUS" == "200" ]]; then
    echo "$LOG_PREFIX OK — Evolution API respondendo (HTTP $HTTP_STATUS)"
    exit 0
fi

echo "$LOG_PREFIX ALERTA — Evolution API com problema (HTTP $HTTP_STATUS). Reiniciando containers..."

cd "$COMPOSE_DIR"
docker compose restart

# Aguarda 30s e testa novamente
sleep 30
HTTP_STATUS_RETRY=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    -H "apikey: $API_KEY" \
    "https://wpp.cardosomatheus.com.br/instance/connectionState/$INSTANCE_NAME" 2>/dev/null || echo "000")

if [[ "$HTTP_STATUS_RETRY" == "200" ]]; then
    echo "$LOG_PREFIX RECUPERADO — Evolution API voltou após restart (HTTP $HTTP_STATUS_RETRY)"
else
    echo "$LOG_PREFIX CRITICO — Evolution API NÃO recuperou após restart (HTTP $HTTP_STATUS_RETRY)"
    # Notificação via Telegram (se notify.sh existir)
    if [[ -x "/opt/cerebro/deploy/notify.sh" ]]; then
        /opt/cerebro/deploy/notify.sh "🚨 ALERTA: Evolution API DOWN após restart automático. Status: $HTTP_STATUS_RETRY"
    fi
fi
