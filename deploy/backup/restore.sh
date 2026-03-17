#!/bin/bash
# Thirdy PostgreSQL restore script
# Usage: ./restore.sh <backup_file.sql.gz>

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh /home/sgadmin/backups/thirdy/daily/ 2>/dev/null || echo "  No daily backups"
    ls -lh /home/sgadmin/backups/thirdy/weekly/ 2>/dev/null || echo "  No weekly backups"
    exit 1
fi

BACKUP_FILE="$1"
DB_CONTAINER="thirdy-postgres-1"
DB_USER="${POSTGRES_USER:-thirdy}"
DB_NAME="${POSTGRES_DB:-thirdy}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will drop and recreate the database '$DB_NAME'."
echo "Backup file: $BACKUP_FILE"
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo "[$(date)] Stopping API and worker..."
cd /home/sgadmin/services/thirdy
docker compose stop api worker

echo "[$(date)] Restoring database..."
# Drop and recreate
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE ${DB_NAME};"

# Restore
gunzip -c "$BACKUP_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" "$DB_NAME"

echo "[$(date)] Restarting services..."
docker compose up -d api worker

echo "[$(date)] Restore complete."
