#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Setup da Evolution API v2 na VPS Hetzner — DELMAT
# Uso: sudo bash deploy/setup-evolution.sh
#
# Pré-requisito: DNS A de wpp.cardosomatheus.com.br apontando para o IP
# desta VPS antes de rodar (necessário para o SSL).
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

EVOLUTION_DIR="/opt/evolution-api"
DOMAIN="wpp.cardosomatheus.com.br"
INSTANCE_NAME="delmat-principal"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  📲 Deploy Evolution API v2 — DELMAT"
echo "═══════════════════════════════════════════════════"
echo ""

# ── 1. Instalar Docker (se não instalado) ─────────────────────

echo "🐳 [1/8] Verificando Docker..."
if command -v docker &>/dev/null; then
    echo "   ✅ Docker já instalado ($(docker --version | cut -d' ' -f3))"
else
    echo "   📦 Instalando Docker..."
    apt update -qq
    apt install -y -qq ca-certificates curl gnupg > /dev/null 2>&1

    # Repositório oficial Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list

    apt update -qq
    apt install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null 2>&1

    systemctl enable docker
    systemctl start docker
    echo "   ✅ Docker instalado e iniciado"
fi

# ── 2. Criar diretório ────────────────────────────────────────

echo "📁 [2/8] Preparando diretório..."
mkdir -p "$EVOLUTION_DIR"

# ── 3. Gerar credenciais ──────────────────────────────────────

echo "🔑 [3/8] Gerando credenciais..."
ENV_FILE="$EVOLUTION_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
    echo "   ✅ .env já existe — mantendo credenciais atuais"
    source "$ENV_FILE"
else
    AUTHENTICATION_API_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -hex 16)

    cat > "$ENV_FILE" <<EOF
# Evolution API — Gerado automaticamente em $(date '+%Y-%m-%d %H:%M:%S')
AUTHENTICATION_API_KEY=${AUTHENTICATION_API_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
SERVER_URL=https://${DOMAIN}
EOF

    chmod 600 "$ENV_FILE"
    echo "   ✅ Credenciais geradas e salvas em $ENV_FILE"
fi

# Carrega variáveis
source "$ENV_FILE"

# ── 4. Docker Compose ─────────────────────────────────────────

echo "📋 [4/8] Configurando Docker Compose..."
cp "$SCRIPT_DIR/docker-compose-evolution.yml" "$EVOLUTION_DIR/docker-compose.yml"
echo "   ✅ docker-compose.yml instalado"

# ── 5. Nginx ──────────────────────────────────────────────────

echo "🌐 [5/8] Configurando Nginx..."

# Copiar config (sem SSL primeiro — Certbot vai adicionar)
# Usamos uma versão temporária sem SSL para o Certbot funcionar
cat > /etc/nginx/sites-available/"$DOMAIN" <<'NGINX_TEMP'
server {
    listen 80;
    server_name wpp.cardosomatheus.com.br;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
        client_max_body_size 50M;
    }
}
NGINX_TEMP

ln -sf /etc/nginx/sites-available/"$DOMAIN" /etc/nginx/sites-enabled/

if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "   ✅ Nginx configurado (HTTP temporário)"
else
    echo "   ⚠️  Erro na config do Nginx — verifique: nginx -t"
    exit 1
fi

# ── 6. SSL com Certbot ────────────────────────────────────────

echo "🔒 [6/8] Configurando SSL..."
if [[ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
    echo "   ✅ Certificado SSL já existe"
else
    # Instalar certbot se necessário
    if ! command -v certbot &>/dev/null; then
        apt install -y -qq certbot python3-certbot-nginx > /dev/null 2>&1
    fi

    echo "   📝 Obtendo certificado SSL para $DOMAIN..."
    echo "   ⚠️  IMPORTANTE: O DNS A de $DOMAIN deve estar apontando para este servidor!"
    echo ""

    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect

    echo "   ✅ SSL configurado com auto-renovação"
fi

# Agora substituir pela config completa com security headers
cp "$SCRIPT_DIR/nginx-evolution.conf" /etc/nginx/sites-available/"$DOMAIN"
ln -sf /etc/nginx/sites-available/"$DOMAIN" /etc/nginx/sites-enabled/

if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "   ✅ Nginx atualizado com config final (security headers)"
else
    echo "   ⚠️  Config final do Nginx com erro — mantendo config do Certbot"
fi

# ── 7. Subir containers ──────────────────────────────────────

echo "🚀 [7/8] Subindo containers..."
cd "$EVOLUTION_DIR"
docker compose pull --quiet
docker compose up -d

echo "   ⏳ Aguardando Evolution API iniciar (30s)..."
sleep 30

# Verificar se está rodando
if docker compose ps --format json | grep -q '"running"'; then
    echo "   ✅ Containers rodando"
else
    echo "   ⚠️  Containers com problema. Verificando logs:"
    docker compose logs --tail=20
    exit 1
fi

# ── 8. Criar instância + Health Check ─────────────────────────

echo "📱 [8/8] Criando instância WhatsApp..."

# Aguardar API responder
MAX_RETRIES=10
for i in $(seq 1 $MAX_RETRIES); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
        "http://127.0.0.1:8080/" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" != "000" ]]; then
        break
    fi
    echo "   ⏳ Aguardando API... (tentativa $i/$MAX_RETRIES)"
    sleep 5
done

# Criar instância
RESPONSE=$(curl -s -X POST "http://127.0.0.1:8080/instance/create" \
    -H "apikey: $AUTHENTICATION_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"instanceName\": \"$INSTANCE_NAME\",
        \"integration\": \"WHATSAPP-BAILEYS\",
        \"qrcode\": true
    }" 2>/dev/null || echo '{"error": "Falha na requisição"}')

echo "   📋 Resposta da criação:"
echo "   $RESPONSE" | python3 -m json.tool 2>/dev/null || echo "   $RESPONSE"

# Instalar health check
cp "$SCRIPT_DIR/evolution-health-check.sh" "$EVOLUTION_DIR/health-check.sh"
chmod +x "$EVOLUTION_DIR/health-check.sh"

# Configurar cron (evitar duplicata)
CRON_JOB="*/10 * * * * $EVOLUTION_DIR/health-check.sh >> $EVOLUTION_DIR/health-check.log 2>&1"
(crontab -l 2>/dev/null | grep -v "evolution-api/health-check" ; echo "$CRON_JOB") | crontab -
echo "   ✅ Health check agendado (a cada 10 minutos)"

# ── Resultado ──────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  📲 Evolution API v2 — Deploy Completo!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  🌐 URL:           https://$DOMAIN"
echo "  🔑 API Key:       $AUTHENTICATION_API_KEY"
echo "  📱 Instância:     $INSTANCE_NAME"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PRÓXIMOS PASSOS:"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  1. Obter QR Code para conectar o WhatsApp:"
echo ""
echo "     curl -s https://$DOMAIN/instance/connect/$INSTANCE_NAME \\"
echo "       -H 'apikey: $AUTHENTICATION_API_KEY' | python3 -m json.tool"
echo ""
echo "  2. Verificar conexão:"
echo ""
echo "     curl -s https://$DOMAIN/instance/connectionState/$INSTANCE_NAME \\"
echo "       -H 'apikey: $AUTHENTICATION_API_KEY' | python3 -m json.tool"
echo ""
echo "  3. Teste de envio:"
echo ""
echo "     curl -X POST https://$DOMAIN/message/sendText/$INSTANCE_NAME \\"
echo "       -H 'apikey: $AUTHENTICATION_API_KEY' \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"number\": \"5511999999999\", \"text\": \"Teste DELMAT\"}'"
echo ""
echo "  4. Fornecer ao ERP (HostGator):"
echo "     - URL: https://$DOMAIN"
echo "     - API Key: $AUTHENTICATION_API_KEY"
echo "     - Instance: $INSTANCE_NAME"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  📋 Comandos úteis:"
echo "     docker compose -f $EVOLUTION_DIR/docker-compose.yml logs -f"
echo "     docker compose -f $EVOLUTION_DIR/docker-compose.yml ps"
echo "     docker compose -f $EVOLUTION_DIR/docker-compose.yml restart"
echo ""
