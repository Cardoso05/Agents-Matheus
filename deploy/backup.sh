#!/bin/bash
# Backup diário do banco SQLite do Cérebro
# Mantém últimos 7 dias

set -e

CEREBRO_DIR="/opt/cerebro"
BACKUP_DIR="${CEREBRO_DIR}/backups"
DB_PATH="${CEREBRO_DIR}/cerebro/db/cerebro.db"
DATE=$(date +%Y-%m-%d)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "Banco não encontrado: $DB_PATH"
    exit 0
fi

# Backup usando sqlite3 .backup (safe, não corrompe com WAL)
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$DB_PATH" ".backup '${BACKUP_DIR}/cerebro_${DATE}.db'"
else
    # Fallback: cópia simples
    cp "$DB_PATH" "${BACKUP_DIR}/cerebro_${DATE}.db"
fi

# Comprimir
if command -v gzip &> /dev/null; then
    gzip -f "${BACKUP_DIR}/cerebro_${DATE}.db"
    echo "✅ Backup: ${BACKUP_DIR}/cerebro_${DATE}.db.gz"
else
    echo "✅ Backup: ${BACKUP_DIR}/cerebro_${DATE}.db"
fi

# Limpar backups antigos
find "$BACKUP_DIR" -name "cerebro_*.db*" -mtime +${RETENTION_DAYS} -delete

echo "🗑️  Backups com mais de ${RETENTION_DAYS} dias removidos."
