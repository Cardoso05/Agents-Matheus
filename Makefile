.PHONY: install setup start stop restart logs status seed test web telegram backup secure-check update

# ── Setup ────────────────────────────────────────────────────

install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[telegram,web,dev]"
	@echo "✅ Instalado! Agora rode: make setup"

setup:
	@test -f .env || cp .env.example .env
	@echo "📝 Edite o .env com suas chaves:"
	@echo "   nano .env"
	@echo ""
	@echo "Depois rode: make seed && make start"

setup-secure:
	sudo bash deploy/setup.sh

seed:
	.venv/bin/python -m cerebro.main --seed

test:
	.venv/bin/pytest cerebro/evals/ -v

# ── Rodar ────────────────────────────────────────────────────

telegram:
	.venv/bin/python -m cerebro.main --telegram

web:
	.venv/bin/python -m cerebro.main --web

cli:
	.venv/bin/python -m cerebro.main

# ── Systemd (rodar como serviço) ────────────────────────────

start:
	sudo cp deploy/cerebro-bot.service /etc/systemd/system/
	sudo cp deploy/cerebro-web.service /etc/systemd/system/
	sudo cp deploy/cerebro-backup.service /etc/systemd/system/
	sudo cp deploy/cerebro-backup.timer /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable cerebro-bot cerebro-web cerebro-backup.timer
	sudo systemctl start cerebro-bot cerebro-web cerebro-backup.timer
	@echo "✅ Serviços iniciados!"

stop:
	sudo systemctl stop cerebro-bot cerebro-web

restart:
	sudo systemctl restart cerebro-bot cerebro-web

logs:
	sudo journalctl -u cerebro-bot -u cerebro-web -f

status:
	@sudo systemctl status cerebro-bot --no-pager -l
	@echo "---"
	@sudo systemctl status cerebro-web --no-pager -l

# ── Backup ───────────────────────────────────────────────────

backup:
	bash deploy/backup.sh

# ── Segurança ────────────────────────────────────────────────

secure-check:
	@echo "🔒 Verificando segurança..."
	@echo ""
	@echo "1. Usuário dos serviços:"
	@sudo systemctl show cerebro-bot -p User --value 2>/dev/null || echo "   (serviço não instalado)"
	@echo ""
	@echo "2. Permissões do .env:"
	@ls -la /opt/cerebro/.env 2>/dev/null || echo "   (arquivo não encontrado)"
	@echo ""
	@echo "3. Firewall:"
	@sudo ufw status 2>/dev/null || echo "   UFW não instalado"
	@echo ""
	@echo "4. Dashboard bind (deve ser 127.0.0.1):"
	@ss -tlnp 2>/dev/null | grep 8000 || echo "   (porta 8000 não escutando)"
	@echo ""
	@echo "5. Nginx:"
	@sudo systemctl is-active nginx 2>/dev/null || echo "   Nginx não rodando"
	@echo ""
	@echo "6. Basic Auth:"
	@test -f /etc/nginx/.htpasswd_cerebro && echo "   ✅ Arquivo htpasswd existe" || echo "   ⚠️  Sem basic auth"
	@echo ""
	@echo "7. Backups:"
	@ls -la /opt/cerebro/backups/ 2>/dev/null || echo "   (sem backups ainda)"
	@echo ""
	@echo "8. HTTPS:"
	@test -d /etc/letsencrypt/live/ && echo "   ✅ Certificado encontrado" || echo "   ⚠️  Sem HTTPS (rode: sudo certbot --nginx)"

# ── Atualizar ────────────────────────────────────────────────

update:
	git pull
	.venv/bin/pip install -e ".[telegram,web]"
	sudo systemctl restart cerebro-bot cerebro-web
	@echo "✅ Atualizado e reiniciado!"
