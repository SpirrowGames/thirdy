#!/bin/bash
# Thirdy PostgreSQL backup script
# Usage: ./backup.sh [daily|weekly]
# Designed to be called by cron

set -euo pipefail

BACKUP_DIR="/home/sgadmin/backups/thirdy"
DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday

# Database credentials (from .env or defaults)
DB_CONTAINER="thirdy-postgres-1"
DB_USER="${POSTGRES_USER:-thirdy}"
DB_NAME="${POSTGRES_DB:-thirdy}"

# Retention policy
DAILY_KEEP=7
WEEKLY_KEEP=4

# Create directories
mkdir -p "$DAILY_DIR" "$WEEKLY_DIR"

# Perform backup
BACKUP_FILE="$DAILY_DIR/thirdy_${TIMESTAMP}.sql.gz"
echo "[$(date)] Starting backup..."

docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Daily backup created: $BACKUP_FILE ($BACKUP_SIZE)"

# Weekly backup (copy Sunday's daily backup)
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    WEEKLY_FILE="$WEEKLY_DIR/thirdy_weekly_${TIMESTAMP}.sql.gz"
    cp "$BACKUP_FILE" "$WEEKLY_FILE"
    echo "[$(date)] Weekly backup created: $WEEKLY_FILE"
fi

# Cleanup old daily backups
find "$DAILY_DIR" -name "thirdy_*.sql.gz" -mtime +$DAILY_KEEP -delete
DAILY_COUNT=$(find "$DAILY_DIR" -name "thirdy_*.sql.gz" | wc -l)
echo "[$(date)] Daily backups retained: $DAILY_COUNT"

# Cleanup old weekly backups
find "$WEEKLY_DIR" -name "thirdy_weekly_*.sql.gz" -mtime +$((WEEKLY_KEEP * 7)) -delete
WEEKLY_COUNT=$(find "$WEEKLY_DIR" -name "thirdy_weekly_*.sql.gz" | wc -l)
echo "[$(date)] Weekly backups retained: $WEEKLY_COUNT"

echo "[$(date)] Backup complete."
