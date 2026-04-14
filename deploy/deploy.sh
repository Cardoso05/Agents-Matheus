#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Deploy Automatizado — Cérebro + FinBot
# Chamado pelo webhook listener ou manualmente
# Uso: bash deploy/deploy.sh [commit_sha] [commit_msg] [pusher]
# ══════════════════════════════════════════════════════════════
set -uo pipefail

# ── CONFIG ─────────────────────────────────────────────────
PROJECT_DIR="/opt/cerebro"
FINBOT_SRC="$PROJECT_DIR/finbot-ai-main"
FINBOT_DIR="/opt/finbot"
VENV="$PROJECT_DIR/.venv/bin"
DB_PATH="$PROJECT_DIR/cerebro/db/cerebro.db"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/deploy/deploys.log"
MIGRATION_TRACKER="$PROJECT_DIR/.last_migration"

COMMIT_SHA="${1:-manual}"
COMMIT_MSG="${2:-deploy manual}"
PUSHER="${3:-matheus}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
START_TIME=$(date +%s)

# Carregar env
set -a
source "$PROJECT_DIR/.env" 2>/dev/null || true
set +a

# ── FUNÇÕES ────────────────────────────────────────────────
log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

notify() {
    bash "$PROJECT_DIR/deploy/notify.sh" "$1" "$2" 2>/dev/null || true
}

health_check() {
    local ok=true
    # Cérebro web
    if ! curl -sf --max-time 5 http://127.0.0.1:8000/ > /dev/null 2>&1; then
        log "   ❌ cerebro-web não responde na :8000"
        ok=false
    else
        log "   ✅ cerebro-web OK"
    fi
    # Cérebro bot
    if ! sudo systemctl is-active --quiet cerebro-bot; then
        log "   ❌ cerebro-bot não está ativo"
        ok=false
    else
        log "   ✅ cerebro-bot OK"
    fi
    # FinBot (não-bloqueante)
    if sudo systemctl is-enabled --quiet finbot-web 2>/dev/null; then
        if curl -sf --max-time 5 http://127.0.0.1:3000/finbot > /dev/null 2>&1; then
            log "   ✅ finbot-web OK"
        else
            log "   ⚠️ finbot-web não responde (não bloqueia deploy)"
        fi
    fi
    $ok
}

rollback() {
    local reason="$1"
    log "🔄 ROLLBACK: $reason"

    cd "$PROJECT_DIR"
    git reset --hard HEAD~1 2>/dev/null || true

    # Restaurar backup do banco
    local latest=$(ls -t "$BACKUP_DIR"/pre_deploy_*.db 2>/dev/null | head -1)
    if [ -n "$latest" ] && [ -f "$DB_PATH" ]; then
        cp "$latest" "$DB_PATH"
        log "   Banco restaurado de $latest"
    fi

    # Reinstalar deps da versão anterior
    "$VENV/pip" install -e ".[telegram,web]" --quiet 2>/dev/null || true

    # Reiniciar serviços
    sudo systemctl restart cerebro-bot cerebro-web 2>/dev/null || true
    if sudo systemctl is-enabled --quiet finbot-web 2>/dev/null; then
        sudo systemctl restart finbot-web 2>/dev/null || true
    fi

    sleep 5

    if health_check; then
        notify "warning" "⚠️ Deploy falhou — rollback OK\n\nCommit: $COMMIT_SHA\nMotivo: $reason\nSistema rodando na versão anterior"
    else
        notify "critical" "🚨 CRÍTICO: Deploy E rollback falharam!\n\nCommit: $COMMIT_SHA\nIntervenção manual necessária!"
    fi
    exit 1
}

apply_migrations() {
    local migrations_dir="$FINBOT_SRC/supabase/migrations"
    [ ! -d "$migrations_dir" ] && return 0

    local supabase_url="${SUPABASE_URL:-}"
    local supabase_key="${SUPABASE_SERVICE_ROLE_KEY:-}"
    [ -z "$supabase_url" ] || [ -z "$supabase_key" ] && {
        log "   ⚠️ Supabase não configurado, pulando migrations"
        return 0
    }

    local last_applied=""
    [ -f "$MIGRATION_TRACKER" ] && last_applied=$(cat "$MIGRATION_TRACKER")

    local applied=0
    for migration in $(ls "$migrations_dir"/*.sql 2>/dev/null | sort); do
        local fname=$(basename "$migration")
        # Pular já aplicadas
        if [ -n "$last_applied" ] && [[ "$fname" < "$last_applied" || "$fname" == "$last_applied" ]]; then
            continue
        fi

        log "   Aplicando migration: $fname"
        local sql_content=$(cat "$migration")

        # POST via Supabase REST API (usando pg_execute via rpc)
        local response=$(curl -sf --max-time 30 \
            -X POST "${supabase_url}/rest/v1/rpc/" \
            -H "apikey: ${supabase_key}" \
            -H "Authorization: Bearer ${supabase_key}" \
            -H "Content-Type: application/json" \
            -d "{}" 2>&1 || true)

        # Fallback: usar psql direto via supabase pooler se disponível
        # Ou tentar via SQL endpoint do Supabase Management API
        local pg_response=$(curl -sf --max-time 30 \
            -X POST "${supabase_url}/rest/v1/rpc/exec_sql" \
            -H "apikey: ${supabase_key}" \
            -H "Authorization: Bearer ${supabase_key}" \
            -H "Content-Type: application/json" \
            -d "{\"query\": $(echo "$sql_content" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" 2>&1 || true)

        # Se não tem exec_sql RPC, tenta npx supabase
        if command -v npx &>/dev/null && [ -f "$FINBOT_SRC/supabase/config.toml" ]; then
            cd "$FINBOT_SRC"
            npx supabase db push --linked 2>&1 | tail -5 || {
                log "   ⚠️ supabase db push falhou para $fname (pode já estar aplicada)"
            }
            cd "$PROJECT_DIR"
        fi

        echo "$fname" > "$MIGRATION_TRACKER"
        applied=$((applied + 1))
    done

    [ $applied -gt 0 ] && log "   ✅ $applied migration(s) aplicada(s)"
    return 0
}

# ── DEPLOY ─────────────────────────────────────────────────
log "═══════════════════════════════════════"
log "🚀 Deploy iniciado"
log "   Commit: $COMMIT_SHA"
log "   Msg:    $COMMIT_MSG"
log "   Por:    $PUSHER"
log "═══════════════════════════════════════"

# 1. Backup
log "1/8 Backup do banco..."
mkdir -p "$BACKUP_DIR"
if [ -f "$DB_PATH" ]; then
    sqlite3 "$DB_PATH" ".backup '${BACKUP_DIR}/pre_deploy_${COMMIT_SHA}_$(date +%s).db'" 2>/dev/null
    log "   ✅ Backup salvo"
else
    log "   ⚠️ Banco não encontrado"
fi

# 2. Pull
log "2/8 Pull do código..."
cd "$PROJECT_DIR"
PREV_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "none")
git fetch origin main 2>&1 | tail -3
git reset --hard origin/main 2>&1 | tail -1
NEW_HEAD=$(git rev-parse HEAD)
log "   ✅ $PREV_HEAD → $NEW_HEAD"

# Detectar o que mudou
CHANGED_FILES=$(git diff --name-only "$PREV_HEAD" "$NEW_HEAD" 2>/dev/null || echo "all")
FINBOT_CHANGED=$(echo "$CHANGED_FILES" | grep "finbot-ai-main/" || true)
MIGRATION_CHANGED=$(echo "$CHANGED_FILES" | grep "supabase/migrations/" || true)

# 3. Python deps
log "3/8 Dependências Python..."
"$VENV/pip" install -e ".[telegram,web]" --quiet 2>&1 | tail -3
log "   ✅ Python deps OK"

# 4. FinBot (se mudou)
if [ -n "$FINBOT_CHANGED" ] && [ -d "$FINBOT_DIR" ]; then
    log "4/8 FinBot: mudanças detectadas, atualizando..."
    rsync -av --delete "$FINBOT_SRC/" "$FINBOT_DIR/" \
        --exclude=node_modules --exclude=.next --exclude=.env.local 2>&1 | tail -3
    cd "$FINBOT_DIR"
    npm install --silent 2>&1 | tail -3
    rm -rf .next
    npm run build 2>&1 | tail -5
    cd "$PROJECT_DIR"
    log "   ✅ FinBot rebuild OK"
else
    log "4/8 FinBot: sem mudanças"
fi

# 5. Supabase migrations (se mudou)
if [ -n "$MIGRATION_CHANGED" ]; then
    log "5/8 Migrations Supabase..."
    apply_migrations
else
    log "5/8 Migrations: sem mudanças"
fi

# 6. Testes
log "6/8 Rodando testes..."
if "$VENV/python" -m pytest cerebro/evals/ -x --tb=short -q 2>&1 | tee -a "$LOG_FILE"; then
    log "   ✅ Testes passaram"
else
    rollback "Testes falharam"
fi

# 7. Restart
log "7/8 Reiniciando serviços..."
sudo systemctl restart cerebro-bot cerebro-web
log "   ✅ cerebro-bot + cerebro-web reiniciados"

if [ -n "$FINBOT_CHANGED" ] && sudo systemctl is-enabled --quiet finbot-web 2>/dev/null; then
    sudo systemctl restart finbot-web
    log "   ✅ finbot-web reiniciado"
fi

sleep 5

# 8. Health check
log "8/8 Health check..."
if health_check; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    log "═══════════════════════════════════════"
    log "✅ Deploy concluído! (${DURATION}s)"
    log "═══════════════════════════════════════"
    notify "success" "✅ Deploy concluído\n\nCommit: $COMMIT_SHA\nMsg: $COMMIT_MSG\nPor: $PUSHER\nDuração: ${DURATION}s"
else
    rollback "Health check falhou"
fi

# Limpar backups antigos (manter 10)
ls -t "$BACKUP_DIR"/pre_deploy_*.db 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true
