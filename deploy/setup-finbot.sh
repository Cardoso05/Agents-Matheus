#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Setup FinBot AI na VPS
# Roda como root na VPS do Cérebro
# ══════════════════════════════════════════════════════════════
set -e

echo "🚀 Setup FinBot AI"
echo "═══════════════════"

# ── 1. Instalar Node.js 20 (se não tiver) ────────────────────
if ! command -v node &> /dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 20 ]]; then
    echo "📦 Instalando Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    echo "✅ Node.js $(node -v) instalado"
else
    echo "✅ Node.js $(node -v) já instalado"
fi

# ── 2. Copiar projeto pra /opt/finbot ─────────────────────────
echo "📁 Copiando projeto..."
if [ -d "/opt/finbot" ]; then
    echo "   /opt/finbot já existe, atualizando..."
    rm -rf /opt/finbot/.next
    cp -r /opt/cerebro/finbot-ai-main/* /opt/finbot/
    cp -r /opt/cerebro/finbot-ai-main/.eslintrc.json /opt/finbot/ 2>/dev/null || true
    cp -r /opt/cerebro/finbot-ai-main/.gitignore /opt/finbot/ 2>/dev/null || true
else
    echo "   Criando /opt/finbot..."
    cp -r /opt/cerebro/finbot-ai-main /opt/finbot
fi
echo "✅ Projeto em /opt/finbot"

# ── 3. Configurar .env.local ──────────────────────────────────
if [ ! -f "/opt/finbot/.env.local" ]; then
    echo ""
    echo "⚠️  Arquivo .env.local não encontrado!"
    echo "   Criando a partir do exemplo..."
    cp /opt/finbot/.env.local.example /opt/finbot/.env.local
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "📝 AÇÃO NECESSÁRIA: edite /opt/finbot/.env.local"
    echo "   nano /opt/finbot/.env.local"
    echo ""
    echo "   Preencha:"
    echo "   NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co"
    echo "   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ..."
    echo "   SUPABASE_SERVICE_ROLE_KEY=eyJ..."
    echo "   ANTHROPIC_API_KEY=sk-ant-..."
    echo "   NEXT_PUBLIC_APP_URL=http://SEU_IP/finbot"
    echo "═══════════════════════════════════════════════════"
    echo ""
    read -p "Pressione ENTER depois de configurar o .env.local..."
fi

# ── 4. Instalar dependências ──────────────────────────────────
echo "📦 Instalando dependências npm..."
cd /opt/finbot
npm install --production=false 2>&1 | tail -3
echo "✅ Dependências instaladas"

# ── 5. Build de produção ──────────────────────────────────────
echo "🔨 Buildando Next.js (pode demorar 1-2 min)..."
npm run build 2>&1 | tail -5
echo "✅ Build completo"

# ── 6. Instalar serviço systemd ───────────────────────────────
echo "⚙️  Configurando serviço systemd..."
cp /opt/cerebro/deploy/finbot-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable finbot-web
systemctl restart finbot-web
echo "✅ Serviço finbot-web ativo"

# ── 7. Atualizar nginx ────────────────────────────────────────
echo "🌐 Atualizando nginx..."
cp /opt/cerebro/deploy/nginx.conf /etc/nginx/sites-available/cerebro
nginx -t && systemctl reload nginx
echo "✅ Nginx atualizado"

# ── 8. Verificar ──────────────────────────────────────────────
echo ""
echo "🔍 Verificando serviços..."
sleep 3

CEREBRO_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ 2>/dev/null || echo "FAIL")
FINBOT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/ 2>/dev/null || echo "FAIL")

echo "   Cérebro (porta 8000): $CEREBRO_STATUS"
echo "   FinBot  (porta 3000): $FINBOT_STATUS"

echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ Setup completo!"
echo ""
echo "   Cérebro Dashboard: http://SEU_IP/"
echo "   FinBot Dashboard:  http://SEU_IP/finbot/"
echo ""
echo "   Gerenciar serviços:"
echo "   sudo systemctl status finbot-web"
echo "   sudo systemctl restart finbot-web"
echo "   sudo journalctl -u finbot-web -f"
echo ""
echo "   Logs:"
echo "   sudo journalctl -u finbot-web --no-pager -n 30"
echo "   sudo journalctl -u cerebro-web --no-pager -n 30"
echo "═══════════════════════════════════════════════════"
