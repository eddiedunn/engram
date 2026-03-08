#!/bin/bash
BACKUP_DIR="/opt/engram/backups"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/engram-$DATE.sql.gz"

# Create backup from rootless postgres container
podman exec postgres pg_dump -U engram engram | gzip > "$BACKUP_FILE"

# Check if backup file was created and is not empty
if [ -s "$BACKUP_FILE" ]; then
    echo "Backup successful: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
    # Keep last 7 days
    find "$BACKUP_DIR" -name "engram-*.sql.gz" -mtime +7 -delete
    exit 0
else
    echo "Backup failed - file is empty or missing" >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi
