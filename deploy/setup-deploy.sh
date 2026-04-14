#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Setup do Deploy Automatizado — roda UMA VEZ na VPS
# Uso: sudo bash deploy/setup-deploy.sh
# ══════════════════════════════════════════════════════════════
set -e

PROJECT_DIR="/opt/cerebro"
DEPLOY_DIR="$PROJECT_DIR/deploy"

echo "🚀 Configurando deploy automatizado..."
echo "═══════════════════════════════════════"

# ── 1. Gerar webhook secret ───────────────────────────────
if ! grep -q "DEPLOY_WEBHOOK_SECRET" "$PROJECT_DIR/.env" 2>/dev/null; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "" >> "$PROJECT_DIR/.env"
    echo "# Deploy automatizado" >> "$PROJECT_DIR/.env"
    echo "DEPLOY_WEBHOOK_SECRET=$SECRET" >> "$PROJECT_DIR/.env"
    echo "✅ [1/7] Webhook secret gerado"
    echo ""
    echo "   ╔══════════════════════════════════════════════════╗"
    echo "   ║  COPIE ESTE SECRET PARA O GITHUB:                ║"
    echo "   ║  $SECRET  ║"
    echo "   ╚══════════════════════════════════════════════════╝"
    echo ""
    echo "   GitHub → Repo Settings → Webhooks → Add webhook"
    echo "   Payload URL: https://cerebro.cardosomatheus.com.br/webhook/deploy"
    echo "   Content type: application/json"
    echo "   Secret: (cole o secret acima)"
    echo "   Events: Just the push event"
    echo ""
else
    echo "✅ [1/7] Webhook secret já existe"
fi

# ── 2. SSH deploy key ─────────────────────────────────────
DEPLOY_KEY="$HOME/.ssh/deploy_key"
if [ ! -f "$DEPLOY_KEY" ]; then
    mkdir -p "$HOME/.ssh"
    ssh-keygen -t ed25519 -C "cerebro-deploy" -f "$DEPLOY_KEY" -N ""
    echo ""
    echo "✅ [2/7] Deploy key gerada"
    echo ""
    echo "   ╔══════════════════════════════════════════════════╗"
    echo "   ║  ADICIONE ESTA CHAVE NO GITHUB:                  ║"
    echo "   ╚══════════════════════════════════════════════════╝"
    echo ""
    cat "${DEPLOY_KEY}.pub"
    echo ""
    echo "   GitHub → Repo Settings → Deploy keys → Add deploy key"
    echo "   Title: cerebro-vps"
    echo "   Key: (cole a chave pública acima)"
    echo "   Allow write access: NÃO"
    echo ""
else
    echo "✅ [2/7] Deploy key já existe"
fi

# ── 3. SSH config ─────────────────────────────────────────
SSH_CONFIG="$HOME/.ssh/config"
if ! grep -q "deploy_key" "$SSH_CONFIG" 2>/dev/null; then
    cat >> "$SSH_CONFIG" << 'SSHEOF'

Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/deploy_key
    IdentitiesOnly yes
    StrictHostKeyChecking no
SSHEOF
    chmod 600 "$SSH_CONFIG"
    echo "✅ [3/7] SSH config atualizado"
else
    echo "✅ [3/7] SSH config já configurado"
fi

# Trocar remote pra SSH (se estiver HTTPS)
cd "$PROJECT_DIR"
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$CURRENT_REMOTE" == *"https://"* ]]; then
    git remote set-url origin git@github.com:cardoso05/Agents-Matheus.git
    echo "   Remote trocado de HTTPS para SSH"
fi

# ── 4. Sudoers ────────────────────────────────────────────
SUDOERS="/etc/sudoers.d/cerebro-deploy"
if [ ! -f "$SUDOERS" ]; then
    cat > "$SUDOERS" << 'EOF'
# Permite reiniciar serviços sem senha (deploy automatizado)
root ALL=(root) NOPASSWD: /usr/bin/systemctl restart cerebro-bot
root ALL=(root) NOPASSWD: /usr/bin/systemctl restart cerebro-web
root ALL=(root) NOPASSWD: /usr/bin/systemctl restart finbot-web
root ALL=(root) NOPASSWD: /usr/bin/systemctl restart cerebro-deploy
root ALL=(root) NOPASSWD: /usr/bin/systemctl is-active *
root ALL=(root) NOPASSWD: /usr/bin/systemctl is-enabled *
EOF
    chmod 440 "$SUDOERS"
    echo "✅ [4/7] Sudoers configurado"
else
    echo "✅ [4/7] Sudoers já existe"
fi

# ── 5. Tornar scripts executáveis ─────────────────────────
chmod +x "$DEPLOY_DIR/deploy.sh"
chmod +x "$DEPLOY_DIR/notify.sh"
chmod +x "$DEPLOY_DIR/backup.sh"
echo "✅ [5/7] Scripts executáveis"

# ── 6. Instalar serviço ──────────────────────────────────
cp "$DEPLOY_DIR/cerebro-deploy.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable cerebro-deploy
systemctl restart cerebro-deploy
echo "✅ [6/7] Serviço cerebro-deploy ativo"

# ── 7. Atualizar nginx ───────────────────────────────────
cp "$DEPLOY_DIR/nginx.conf" /etc/nginx/sites-available/cerebro
if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "✅ [7/7] Nginx atualizado"
else
    echo "⚠️ [7/7] Nginx config com erro — verifique: nginx -t"
fi

# ── Verificação ───────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════"
echo "🔍 Verificando..."

sleep 2
LISTENER=$(curl -sf --max-time 3 http://127.0.0.1:9000/webhook/health 2>/dev/null || echo "FAIL")
echo "   Listener: $LISTENER"

echo ""
echo "═══════════════════════════════════════"
echo "✅ Deploy automatizado configurado!"
echo ""
echo "📋 AÇÕES MANUAIS NECESSÁRIAS:"
echo ""
echo "1. Adicionar webhook no GitHub:"
echo "   URL: https://cerebro.cardosomatheus.com.br/webhook/deploy"
echo "   Secret: (grep DEPLOY_WEBHOOK_SECRET /opt/cerebro/.env)"
echo ""
echo "2. Adicionar deploy key no GitHub:"
echo "   cat ~/.ssh/deploy_key.pub"
echo ""
echo "3. Testar: faça um push na main e veja o Telegram"
echo ""
echo "Comandos úteis:"
echo "   make deploy-status  — status do listener"
echo "   make deploy-logs    — log de deploys"
echo "   make deploy-manual  — deploy manual"
echo "═══════════════════════════════════════"
