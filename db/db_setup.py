#!/usr/bin/env python
"""
db_setup.py

A Python script to set up and verify the PolicyPulse database using SQLAlchemy.
This script is designed to work in both containerized and non-containerized environments.

In a containerized environment, it assumes:
- The database service is already running and accessible via the DATABASE_URL
- The database may need schema initialization but already exists
- Database credentials are provided via environment variables

This script will:
1. Test the database connection
2. Apply the schema if needed
3. Verify the schema was applied correctly
4. Create an initial admin user if needed

Usage:
  python db_setup.py [--recreate] [--verify-only] [--container-mode]
"""

import os
import sys
import argparse
import logging
import subprocess
from urllib.parse import urlparse
import time
from sqlalchemy import create_engine, text, inspect, MetaData, Table
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError
from dotenv import load_dotenv
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:H6v@3xP!2qL#9zR8@localhost:5432/policypulse")

# Schema file path
SCHEMA_FILE = "policypulse_schema.sql"


def parse_db_url(db_url):
    """Parse database URL into components."""
    parsed = urlparse(db_url)
    return {
        'username': parsed.username,
        'password': parsed.password,
        'hostname': parsed.hostname,
        'port': parsed.port or 5432,
        'db_name': parsed.path[1:] if parsed.path else 'policypulse'
    }


def check_postgres_connection(db_info):
    """Check if PostgreSQL is accessible."""
    try:
        # Create a temporary connection to postgres db to check availability
        engine = create_engine(f"postgresql://{db_info['username']}:{db_info['password']}@{db_info['hostname']}:{db_info['port']}/postgres")
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return False


def check_db_exists(db_info):
    """Check if the specific database exists."""
    try:
        # Connect to postgres database to check if our db exists
        engine = create_engine(f"postgresql://{db_info['username']}:{db_info['password']}@{db_info['hostname']}:{db_info['port']}/postgres")
        with engine.connect() as connection:
            result = connection.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_info['db_name']}'"))
            return result.scalar() is not None
    except Exception as e:
        logger.error(f"Error checking if database exists: {e}")
        return False


def create_database(db_info):
    """Create the database if it doesn't exist."""
    try:
        # Connect to postgres database to create our db
        engine = create_engine(f"postgresql://{db_info['username']}:{db_info['password']}@{db_info['hostname']}:{db_info['port']}/postgres")
        with engine.connect() as connection:
            connection.execute(text("COMMIT"))  # Close any existing transaction
            connection.execute(text(f"CREATE DATABASE {db_info['db_name']}"))
        logger.info(f"Database '{db_info['db_name']}' created successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to create database: {e}")
        return False


def drop_database(db_info):
    """Drop the database."""
    try:
        # Connect to postgres database to drop our db
        engine = create_engine(f"postgresql://{db_info['username']}:{db_info['password']}@{db_info['hostname']}:{db_info['port']}/postgres")
        with engine.connect() as connection:
            # Terminate all connections to the database before dropping
            connection.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{db_info['db_name']}'"))
            connection.execute(text("COMMIT"))  # Close any existing transaction
            connection.execute(text(f"DROP DATABASE IF EXISTS {db_info['db_name']}"))
        logger.info(f"Database '{db_info['db_name']}' dropped successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to drop database: {e}")
        return False


def apply_schema(db_url):
    """Apply the schema to the database."""
    if not Path(SCHEMA_FILE).exists():
        logger.error(f"Schema file '{SCHEMA_FILE}' not found!")
        return False
    
    try:
        # Connect to the database
        engine = create_engine(db_url)
        
        # Read the schema file
        with open(SCHEMA_FILE, 'r') as f:
            schema_sql = f.read()
        
        # Split the schema into separate statements to avoid errors when tables already exist
        # This is especially important in container environments where the schema might be partially applied
        statements = schema_sql.split(';')
        
        failed_statements = []
        with engine.begin() as connection:
            for statement in statements:
                statement = statement.strip()
                if statement:  # Skip empty statements
                    try:
                        connection.execute(text(statement + ';'))
                    except ProgrammingError as e:
                        # Likely the object already exists - log but continue
                        if "already exists" in str(e):
                            logger.info(f"Skipping existing object: {str(e).splitlines()[0] if str(e) else 'unknown'}")
                        else:
                            logger.warning(f"Error executing statement: {str(e).splitlines()[0] if str(e) else 'unknown'}")
                            failed_statements.append(statement[:100] + "..." if len(statement) > 100 else statement)
                    except Exception as e:
                        logger.warning(f"Error executing statement: {e}")
                        failed_statements.append(statement[:100] + "..." if len(statement) > 100 else statement)
        
        if failed_statements:
            logger.warning(f"Failed to execute {len(failed_statements)} statements. First few: {failed_statements[:3]}")
            logger.warning("This may be normal if objects already exist or if there are dependencies.")
            # Don't return False here as some failures are expected in a containerized environment
            
        logger.info("Schema application process completed!")
        return True
    except Exception as e:
        logger.error(f"Failed to apply schema: {e}")
        return False


def verify_schema(db_url):
    """Verify that all expected tables and columns exist."""
    try:
        # Connect to the database
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # List of expected tables
        expected_tables = [
            'users', 'user_preferences', 'search_history', 'alert_preferences',
            'legislation', 'legislation_analysis', 'legislation_text',
            'legislation_sponsors', 'amendments', 'legislation_priorities',
            'impact_ratings', 'implementation_requirements', 'alert_history',
            'sync_metadata', 'sync_errors'
        ]
        
        # Check if all expected tables exist
        existing_tables = inspector.get_table_names()
        missing_tables = [table for table in expected_tables if table not in existing_tables]
        
        if missing_tables:
            logger.error(f"Missing tables: {', '.join(missing_tables)}")
            return False
        
        # Check if extensions are installed
        with engine.connect() as connection:
            pg_trgm = connection.execute(text("SELECT 1 FROM pg_extension WHERE extname='pg_trgm'")).scalar() is not None
            unaccent = connection.execute(text("SELECT 1 FROM pg_extension WHERE extname='unaccent'")).scalar() is not None
            
            if not pg_trgm or not unaccent:
                logger.error(f"Missing extensions: {'pg_trgm' if not pg_trgm else ''} {'unaccent' if not unaccent else ''}")
                return False
        
        logger.info("Schema verification successful!")
        return True
    except Exception as e:
        logger.error(f"Schema verification failed: {e}")
        return False


def create_initial_admin(db_url):
    """Create an initial admin user if it doesn't already exist."""
    try:
        # Connect to the database
        engine = create_engine(db_url)
        
        # Check if admin user exists
        with engine.connect() as connection:
            admin_exists = connection.execute(
                text("SELECT 1 FROM users WHERE email='admin@policypulse.org'")
            ).scalar() is not None
            
            # If admin doesn't exist, create one
            if not admin_exists:
                with connection.begin():
                    connection.execute(
                        text("INSERT INTO users (email, name, role, created_at, updated_at) "
                            "VALUES ('admin@policypulse.org', 'System Administrator', 'admin', NOW(), NOW())")
                    )
                    # Get the inserted user ID
                    user_id = connection.execute(
                        text("SELECT id FROM users WHERE email='admin@policypulse.org'")
                    ).scalar()
                    
                    # Create alert preferences for admin
                    connection.execute(
                        text(f"INSERT INTO alert_preferences (user_id, email, active, health_threshold, local_govt_threshold) "
                            f"VALUES ({user_id}, 'admin@policypulse.org', TRUE, 70, 70)")
                    )
                logger.info("Initial admin user created!")
            else:
                logger.info("Admin user already exists.")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create initial admin: {e}")
        return False


def main():
    """Main function to set up the database."""
    parser = argparse.ArgumentParser(description='Set up the PolicyPulse database')
    parser.add_argument('--recreate', action='store_true', help='Recreate the database if it exists')
    parser.add_argument('--verify-only', action='store_true', help='Only verify the schema without making changes')
    parser.add_argument('--container-mode', action='store_true', help='Run in container mode (assumes DB already exists)')
    args = parser.parse_args()
    
    # Parse database URL
    db_info = parse_db_url(DATABASE_URL)
    
    # In container mode, we assume the database already exists
    container_mode = args.container_mode or 'DOCKER_CONTAINER' in os.environ
    
    # Display environment information
    logger.info(f"Database setup starting in {'container' if container_mode else 'standard'} mode")
    logger.info(f"Database: {db_info['db_name']} at {db_info['hostname']}:{db_info['port']}")
    
    # For container mode, we'll retry the connection a few times since services might be starting up
    max_retries = 5 if container_mode else 1
    retry_count = 0
    
    # Retry loop for database connection
    while retry_count < max_retries:
        if check_postgres_connection(db_info):
            break
        
        retry_count += 1
        if retry_count >= max_retries:
            logger.error("Failed to connect to PostgreSQL after multiple attempts. Please make sure PostgreSQL is running.")
            return False
            
        logger.info(f"Failed to connect to PostgreSQL. Retry {retry_count}/{max_retries} in 5 seconds...")
        time.sleep(5)
    
    # If verify-only mode, just check the schema and exit
    if args.verify_only:
        exists = check_db_exists(db_info)
        if not exists:
            logger.error(f"Database '{db_info['db_name']}' does not exist.")
            return False
        
        return verify_schema(DATABASE_URL)
    
    # In container mode, we don't create or drop the database (handled by Docker)
    # We just apply the schema to the existing database
    if container_mode:
        # Test if we can connect to the specific database
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                logger.info(f"Connected to database '{db_info['db_name']}' successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to database '{db_info['db_name']}': {e}")
            return False
    else:
        # Standard mode - check if database exists
        exists = check_db_exists(db_info)
        
        # Recreate the database if requested
        if exists and args.recreate:
            logger.info(f"Dropping existing database '{db_info['db_name']}'...")
            if not drop_database(db_info):
                return False
            exists = False
        
        # Create the database if it doesn't exist
        if not exists:
            logger.info(f"Creating database '{db_info['db_name']}'...")
            if not create_database(db_info):
                return False
            
            # Wait a moment for the database to be fully created
            time.sleep(1)
    
    # Apply the schema
    logger.info("Applying database schema...")
    if not apply_schema(DATABASE_URL):
        return False
    
    # Verify the schema
    logger.info("Verifying database schema...")
    if not verify_schema(DATABASE_URL):
        return False
    
    # Create initial admin user
    logger.info("Creating initial admin user if needed...")
    if not create_initial_admin(DATABASE_URL):
        return False
    
    logger.info("Database setup completed successfully!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)