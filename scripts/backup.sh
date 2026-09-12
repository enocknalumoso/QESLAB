#!/bin/bash
# Daily backup of all QES databases and configs
BACKUP_DIR="/root/qeslab/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting QES backup..."

# 1. SQLite databases
cp -r /root/qeslab/memory/*.db "$BACKUP_DIR/" 2>/dev/null
cp -r /root/qeslab/vault/*.db "$BACKUP_DIR/" 2>/dev/null

# 2. Configs
cp /root/qeslab/.env "$BACKUP_DIR/"
cp /root/qeslab/configs/settings.py "$BACKUP_DIR/"

# 3. Parquet data (optional)
# tar -czf "$BACKUP_DIR/data_raw_$DATE.tar.gz" /root/qeslab/data/raw/*.parquet 2>/dev/null
# tar -czf "$BACKUP_DIR/data_resampled_$DATE.tar.gz" /root/qeslab/data/resampled/*.parquet 2>/dev/null

# 4. Logs (last 7 days)
tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" /root/qeslab/logs/*.log 2>/dev/null

# 5. Create manifest
echo "Backup timestamp: $(date)" > "$BACKUP_DIR/manifest_$DATE.txt"
ls -lh "$BACKUP_DIR"/*.db "$BACKUP_DIR"/*.py "$BACKUP_DIR"/*.env 2>/dev/null >> "$BACKUP_DIR/manifest_$DATE.txt"

# 6. Keep only last 7 backups
cd "$BACKUP_DIR" && ls -t | tail -n +8 | xargs rm -f 2>/dev/null

echo "[$(date)] Backup completed: $BACKUP_DIR"
