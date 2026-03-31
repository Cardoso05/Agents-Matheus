.PHONY: install setup start stop restart logs status seed test web telegram

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
	sudo systemctl daemon-reload
	sudo systemctl enable cerebro-bot cerebro-web
	sudo systemctl start cerebro-bot cerebro-web
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

# ── Atualizar ────────────────────────────────────────────────

update:
	git pull
	.venv/bin/pip install -e ".[telegram,web]"
	sudo systemctl restart cerebro-bot cerebro-web
	@echo "✅ Atualizado e reiniciado!"
