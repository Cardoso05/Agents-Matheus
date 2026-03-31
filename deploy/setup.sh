#!/bin/bash
# Setup seguro do Cérebro na VPS
# Uso: bash deploy/setup.sh

set -e

CEREBRO_DIR="/opt/cerebro"
CEREBRO_USER="cerebro"

echo "🧠 Instalando Cérebro (com segurança)..."
echo ""

# ── 1. Dependências do sistema ──────────────────────────────

echo "📦 [1/8] Instalando dependências do sistema..."
sudo apt update -qq
sudo apt install -y -qq python3 python3-venv python3-pip git nginx sqlite3 ufw > /dev/null 2>&1
echo "   ✅ Python, Nginx, UFW, SQLite instalados"

# ── 2. Usuário dedicado ────────────────────────────────────

echo "👤 [2/8] Configurando usuário dedicado..."
if ! id "$CEREBRO_USER" &>/dev/null; then
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$CEREBRO_USER"
    echo "   ✅ Usuário '$CEREBRO_USER' criado (sem shell, sem home)"
else
    echo "   ✅ Usuário '$CEREBRO_USER' já existe"
fi

# ── 3. Clonar/atualizar repositório ────────────────────────

echo "📥 [3/8] Preparando código..."
if [ -d "$CEREBRO_DIR/.git" ]; then
    cd "$CEREBRO_DIR"
    git pull --quiet
    echo "   ✅ Repositório atualizado"
else
    sudo mkdir -p "$CEREBRO_DIR"
    sudo chown "$(whoami)" "$CEREBRO_DIR"
    git clone --quiet https://github.com/cardoso05/Agents-Matheus.git "$CEREBRO_DIR"
    echo "   ✅ Repositório clonado"
fi

cd "$CEREBRO_DIR"

# Criar venv e instalar
echo "   📦 Instalando dependências Python..."
python3 -m venv .venv
.venv/bin/pip install --quiet -e ".[telegram,web]"
echo "   ✅ Dependências instaladas"

# ── 4. Configurar .env ─────────────────────────────────────

echo "🔑 [4/8] Configurando ambiente..."
if [ ! -f .env ]; then
    cp .env.example .env

    echo ""
    echo "   ⚠️  CONFIGURE O .env AGORA:"
    echo ""
    echo "      sudo nano $CEREBRO_DIR/.env"
    echo ""
    echo "   Preencha pelo menos:"
    echo "   - ANTHROPIC_API_KEY=sk-ant-..."
    echo "   - TELEGRAM_BOT_TOKEN=..."
    echo "   - TELEGRAM_AUTHORIZED_USERS=seu_id"
    echo ""
    read -p "   Pressione ENTER após editar o .env (ou Ctrl+C para sair)..." _
fi

# Proteger .env (só o dono pode ler)
sudo chown "$CEREBRO_USER":"$CEREBRO_USER" .env
sudo chmod 600 .env
echo "   ✅ .env protegido (permissão 600, owner: $CEREBRO_USER)"

# ── 5. Permissões corretas ─────────────────────────────────

echo "🔒 [5/8] Configurando permissões..."
sudo chown -R "$CEREBRO_USER":"$CEREBRO_USER" "$CEREBRO_DIR"
# Manter acesso de leitura pro admin
sudo chmod -R o-rwx "$CEREBRO_DIR"
# O DB precisa de escrita
sudo mkdir -p "$CEREBRO_DIR/cerebro/db"
sudo mkdir -p "$CEREBRO_DIR/backups"
sudo chown -R "$CEREBRO_USER":"$CEREBRO_USER" "$CEREBRO_DIR/cerebro/db" "$CEREBRO_DIR/backups"
echo "   ✅ Permissões configuradas"

# Inicializar banco
sudo -u "$CEREBRO_USER" "$CEREBRO_DIR/.venv/bin/python" -m cerebro.main --init-db
echo "   ✅ Banco de dados inicializado"

# ── 6. Firewall (UFW) ──────────────────────────────────────

echo "🛡️  [6/8] Configurando firewall..."
sudo ufw --force reset > /dev/null 2>&1
sudo ufw default deny incoming > /dev/null 2>&1
sudo ufw default allow outgoing > /dev/null 2>&1
sudo ufw allow ssh > /dev/null 2>&1
sudo ufw allow 80/tcp > /dev/null 2>&1
sudo ufw allow 443/tcp > /dev/null 2>&1
sudo ufw --force enable > /dev/null 2>&1
echo "   ✅ Firewall ativo: SSH(22) + HTTP(80) + HTTPS(443)"
echo "   ⛔ Porta 8000 NÃO exposta (dashboard só via Nginx)"

# ── 7. Nginx + Basic Auth ──────────────────────────────────

echo "🌐 [7/8] Configurando Nginx..."

# Gerar senha para basic auth
if [ ! -f /etc/nginx/.htpasswd_cerebro ]; then
    echo ""
    echo "   Defina a senha do dashboard web:"
    read -s -p "   Senha: " DASH_PASS
    echo ""
    echo "matheus:$(openssl passwd -6 "$DASH_PASS")" | sudo tee /etc/nginx/.htpasswd_cerebro > /dev/null
    sudo chmod 640 /etc/nginx/.htpasswd_cerebro
    echo "   ✅ Basic Auth configurado (user: matheus)"
else
    echo "   ✅ Basic Auth já configurado"
fi

# Instalar config nginx
sudo cp "$CEREBRO_DIR/deploy/nginx.conf" /etc/nginx/sites-available/cerebro
sudo ln -sf /etc/nginx/sites-available/cerebro /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

if sudo nginx -t 2>/dev/null; then
    sudo systemctl reload nginx
    echo "   ✅ Nginx configurado e rodando"
else
    echo "   ⚠️  Nginx config com erro — verifique: sudo nginx -t"
fi

# ── 8. Serviços systemd ────────────────────────────────────

echo "⚙️  [8/8] Instalando serviços..."

# Bot + Scheduler
sudo cp "$CEREBRO_DIR/deploy/cerebro-bot.service" /etc/systemd/system/
sudo cp "$CEREBRO_DIR/deploy/cerebro-web.service" /etc/systemd/system/
sudo cp "$CEREBRO_DIR/deploy/cerebro-backup.service" /etc/systemd/system/
sudo cp "$CEREBRO_DIR/deploy/cerebro-backup.timer" /etc/systemd/system/

# Tornar backup executável
sudo chmod +x "$CEREBRO_DIR/deploy/backup.sh"

sudo systemctl daemon-reload
sudo systemctl enable cerebro-bot cerebro-web cerebro-backup.timer
sudo systemctl start cerebro-bot cerebro-web cerebro-backup.timer

echo "   ✅ Serviços instalados e iniciados"
echo "   ✅ Backup diário às 02:00 ativado"

# ── Resultado ───────────────────────────────────────────────

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "════════════════════════════════════════════════════════"
echo "  🧠 Cérebro instalado com segurança!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  📱 Telegram: mande 'status geral' pro seu bot"
echo "  🌐 Dashboard: http://$IP  (user: matheus)"
echo ""
echo "  Comandos:"
echo "    make logs        — ver logs"
echo "    make status      — checar serviços"
echo "    make restart     — reiniciar"
echo "    make backup      — backup manual"
echo "    make secure-check — verificar segurança"
echo "    make update      — atualizar código"
echo ""
echo "  HTTPS (opcional):"
echo "    sudo apt install certbot python3-certbot-nginx"
echo "    sudo certbot --nginx -d SEU_DOMINIO"
echo ""
echo "════════════════════════════════════════════════════════"
