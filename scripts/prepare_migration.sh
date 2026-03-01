#!/bin/bash

# Configuration
DB_CONTAINER="tax_lien_v2-db-1"
DB_USER="lienuser"
DB_PASS="lienpass" # Default, will try to read from .env
DB_NAME="lienhunter"
BACKUP_FILE="lienhunter_backup.sql"
ARCHIVE_FILE="tax_lien_v2_migration.tar.gz"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Tax Lien v2 Migration Helper ===${NC}"
echo "This script prepares your project for migration to the DGX."

# 1. Database Backup
echo -e "\n${YELLOW}[1/4] Backing up database...${NC}"

# Check if container is running
if [ "$(docker ps -q -f name=$DB_CONTAINER)" ]; then
    echo "Found running database container: $DB_CONTAINER"
    
    # Try to read password from .env if it exists
    if [ -f .env ]; then
        echo "Reading credentials from .env..."
        # Extract password (rudimentary)
        ENV_PASS=$(grep "MYSQL_PASSWORD" .env | cut -d '=' -f2)
        if [ ! -z "$ENV_PASS" ]; then
            DB_PASS=$ENV_PASS
        fi
    fi

    # Run dump inside container
    echo "Running mysqldump (safe for running databases)..."
    docker exec $DB_CONTAINER mysqldump -u $DB_USER -p$DB_PASS $DB_NAME > $BACKUP_FILE
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Database backup successful: $BACKUP_FILE${NC}"
    else
        echo -e "${RED}✗ Database backup failed! Check credentials or container state.${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Database container '$DB_CONTAINER' is not running! Cannot dump data.${NC}"
    echo "Please start the project first: docker-compose up -d db"
    exit 1
fi

# 2. Archive Codebase
echo -e "\n${YELLOW}[2/4] Creating project archive...${NC}"
echo "Excluding: node_modules, venv, .git, .env, __pycache__, and build artifacts"

tar --exclude='./node_modules' \
    --exclude='./frontend/node_modules' \
    --exclude='./frontend/dist' \
    --exclude='./scripts/venv' \
    --exclude='./backend/app/__pycache__' \
    --exclude='./.git' \
    --exclude='./.env' \
    --exclude='./.DS_Store' \
    --exclude="./$ARCHIVE_FILE" \
    --exclude="./$BACKUP_FILE" \
    -czf $ARCHIVE_FILE .

echo -e "${GREEN}✓ Archive created: $ARCHIVE_FILE ($(du -h $ARCHIVE_FILE | cut -f1))${NC}"

# 3. Create Restore Script
echo -e "\n${YELLOW}[3/4] Generating restore script for DGX...${NC}"
cat > restore_on_dgx.sh << 'EOF'
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
docker-compose up -d --build

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
echo "Frontend: http://localhost:8082"
EOF
chmod +x restore_on_dgx.sh

echo -e "${GREEN}✓ Created restore_on_dgx.sh${NC}"

# 4. Instructions
echo -e "\n${YELLOW}[4/4] Migration Instructions${NC}"
echo "Run this command to copy everything to the DGX:"
echo -e "${GREEN}scp $ARCHIVE_FILE $BACKUP_FILE restore_on_dgx.sh user@192.168.100.133:~/tax_lien_v2/${NC}"
echo ""
echo "Then on the DGX:"
echo "1. ssh user@192.168.100.133"
echo "2. mkdir -p ~/tax_lien_v2 && cd ~/tax_lien_v2"
echo "3. tar -xzf $ARCHIVE_FILE"
echo "4. ./restore_on_dgx.sh"
