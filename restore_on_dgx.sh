#!/bin/bash
echo "=== Tax Lien v2 Restore Script ==="

# 1. Check for .env
if [ ! -f .env ]; then
    echo "⚠️  No .env file found!"
    if [ -f .env.sample ]; then
        echo "Creating .env from .env.sample..."
        cp .env.sample .env
        echo "Please edit .env with your secrets before continuing."
        read -p "Press Enter after you have edited .env..."
    else
        echo "Error: neither .env nor .env.sample found."
        exit 1
    fi
fi

# 2. Start Services
echo "Starting Docker containers..."
docker compose up -d --build

echo "Waiting for database to initialize (15s)..."
sleep 15

# 3. Restore Database
if [ -f lienhunter_backup.sql ]; then
    echo "Restoring database from backup..."
    # Get password from .env or default
    DB_PASS=$(grep "MYSQL_PASSWORD" .env | cut -d '=' -f2)
    [ -z "$DB_PASS" ] && DB_PASS="lienpass"
    
    docker exec -i tax_lien_v2-db-1 mysql -u lienuser -p$DB_PASS lienhunter < lienhunter_backup.sql
    echo "✓ Database restored!"
else
    echo "⚠️  lienhunter_backup.sql not found. Skipping DB restore."
fi

echo "=== Restore Complete! ==="
echo "Backend: http://localhost:8001"
echo "Frontend: http://localhost:8083"
