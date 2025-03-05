#!/bin/bash
# PolicyPulse Database Installation Script
# This script sets up the PostgreSQL database for the PolicyPulse application

set -e  # Exit immediately if any command exits with a non-zero status

# Database configuration
DB_USER="admin"
DB_PASSWORD="H6v@3xP!2qL#9zR8"
DB_NAME="policypulse"
DB_HOST="localhost"
DB_PORT="5432"
SCHEMA_FILE="policypulse_schema.sql"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}PolicyPulse Database Installation${NC}"
echo "==============================="

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}PostgreSQL is not installed. Please install PostgreSQL first.${NC}"
    exit 1
fi

echo -e "${YELLOW}Checking PostgreSQL connection...${NC}"
if ! pg_isready -h $DB_HOST -p $DB_PORT > /dev/null 2>&1; then
    echo -e "${RED}PostgreSQL server is not running on $DB_HOST:$DB_PORT${NC}"
    echo "Please ensure PostgreSQL is running and try again."
    exit 1
fi

echo -e "${GREEN}PostgreSQL server is running.${NC}"

# Check if the database already exists
DB_EXISTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" postgres 2>/dev/null || echo "0")

if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${YELLOW}Database '$DB_NAME' already exists.${NC}"
    read -p "Do you want to drop and recreate it? (y/n): " RECREATE
    if [ "$RECREATE" = "y" ] || [ "$RECREATE" = "Y" ]; then
        echo -e "${YELLOW}Dropping database '$DB_NAME'...${NC}"
        PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "DROP DATABASE $DB_NAME" postgres
        echo -e "${GREEN}Database dropped.${NC}"
    else
        echo -e "${YELLOW}Proceeding with existing database. Some errors may occur if schema objects already exist.${NC}"
    fi
fi

# Create the database if it doesn't exist
if [ "$DB_EXISTS" != "1" ] || [ "$RECREATE" = "y" ] || [ "$RECREATE" = "Y" ]; then
    echo -e "${YELLOW}Creating database '$DB_NAME'...${NC}"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME" postgres
    echo -e "${GREEN}Database created.${NC}"
fi

# Apply schema
echo -e "${YELLOW}Applying database schema...${NC}"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $SCHEMA_FILE

# Check if schema was applied successfully
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Database schema applied successfully!${NC}"
else
    echo -e "${RED}Error applying database schema.${NC}"
    exit 1
fi

# Create .env file with database configuration
echo -e "${YELLOW}Creating .env file with database configuration...${NC}"
cat > .env << EOF
# PolicyPulse Database Configuration
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME

# LegiScan API Configuration
LEGISCAN_API_KEY=your_legiscan_api_key_here

# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Email Notification Settings
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_FROM=notifications@policypulse.org
EOF

echo -e "${GREEN}Environment file created.${NC}"
echo -e "${YELLOW}NOTE: Please edit the .env file to add your LegiScan and OpenAI API keys.${NC}"

echo -e "${GREEN}PolicyPulse database setup completed successfully!${NC}"
echo -e "${YELLOW}You can now run the application with the following connection string:${NC}"
echo -e "postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"

exit 0