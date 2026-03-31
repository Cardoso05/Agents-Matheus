#!/bin/bash
# Setup automático do Cérebro na VPS
# Uso: curl -sL <url>/setup.sh | bash
# Ou:  bash deploy/setup.sh

set -e

echo "🧠 Instalando Cérebro..."

# 1. Verificar Python
if ! command -v python3.11 &> /dev/null && ! python3 --version 2>&1 | grep -q "3.1[1-9]"; then
    echo "📦 Instalando Python 3.11..."
    sudo apt update
    sudo apt install -y python3.11 python3.11-venv python3-pip git
fi

# 2. Clonar ou atualizar
if [ -d /opt/cerebro/.git ]; then
    echo "📥 Atualizando repositório..."
    cd /opt/cerebro
    git pull
else
    echo "📥 Clonando repositório..."
    sudo mkdir -p /opt/cerebro
    sudo chown $(whoami) /opt/cerebro
    git clone https://github.com/cardoso05/Agents-Matheus.git /opt/cerebro
fi

cd /opt/cerebro

# 3. Criar venv e instalar
echo "📦 Instalando dependências..."
python3 -m venv .venv
.venv/bin/pip install --quiet -e ".[telegram,web]"

# 4. Configurar .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  CONFIGURE O .env ANTES DE CONTINUAR!"
    echo ""
    echo "   nano /opt/cerebro/.env"
    echo ""
    echo "   Preencha pelo menos:"
    echo "   - ANTHROPIC_API_KEY"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_AUTHORIZED_USERS"
    echo ""
    echo "Depois rode:"
    echo "   cd /opt/cerebro && make seed && make start"
    exit 0
fi

# 5. Inicializar banco
echo "🗄️  Inicializando banco de dados..."
.venv/bin/python -m cerebro.main --init-db

# 6. Instalar serviços
echo "⚙️  Configurando serviços systemd..."
sudo cp deploy/cerebro-bot.service /etc/systemd/system/
sudo cp deploy/cerebro-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cerebro-bot cerebro-web

echo ""
echo "✅ Cérebro instalado!"
echo ""
echo "Comandos úteis:"
echo "  make seed      — Popular banco com dados de exemplo"
echo "  make start     — Iniciar bot + dashboard"
echo "  make stop      — Parar tudo"
echo "  make logs      — Ver logs em tempo real"
echo "  make update    — Atualizar código e reiniciar"
echo ""
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
