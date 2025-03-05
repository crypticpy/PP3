
#!/usr/bin/env python
"""
setup_database.py

This script sets up the PolicyPulse database and populates it with initial data.
It handles first-time setup and updates to existing databases.
"""

import os
import sys
import logging
import argparse
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def get_connection_string():
    """Get the database connection string from environment variables."""
    if 'DATABASE_URL' in os.environ:
        logger.info(f"DATABASE_URL found: {os.environ['DATABASE_URL'][:15]}...")
        return os.environ['DATABASE_URL']
    
    logger.error("DATABASE_URL environment variable not found")
    return None

def test_connection(connection_string):
    """Test the database connection."""
    try:
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                logger.info(f"Successfully connected to PostgreSQL: {version}")
                return True
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return False

def check_existing_schema(connection_string):
    """Check if database schema already exists."""
    try:
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor() as cursor:
                # Check for a sample of key tables
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND 
                    table_name IN ('users', 'legislation', 'sync_metadata')
                """)
                existing_tables = cursor.fetchall()
                
                # Check for enum types
                cursor.execute("""
                    SELECT typname FROM pg_type 
                    WHERE typname IN ('data_source_enum', 'govt_type_enum', 'bill_status_enum')
                """)
                existing_types = cursor.fetchall()
                
                if existing_tables and existing_types:
                    logger.info(f"Existing schema detected with {len(existing_tables)} core tables and {len(existing_types)} enum types")
                    return True
                return False
    except Exception as e:
        logger.error(f"Error checking schema: {e}")
        return False

def setup_database(force=False):
    """Set up the database schema."""
    logger.info("Setting up the PolicyPulse database...")
    
    # Get connection string
    connection_string = get_connection_string()
    if not connection_string:
        return False
    
    # Check if schema already exists
    schema_exists = check_existing_schema(connection_string)
    
    if schema_exists and not force:
        logger.info("Database schema already exists. Use --force to rebuild.")
        return True
    
    # Run the database schema creation
    logger.info("Running database schema creation...")
    from db.db_setup import main as setup_main
    
    try:
        return setup_main()
    except Exception as e:
        logger.error(f"Database schema creation failed: {e}")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Set up the PolicyPulse database")
    parser.add_argument("--force", action="store_true", help="Force schema recreation even if it exists")
    parser.add_argument("--verify-only", action="store_true", help="Only verify the database connection and schema")
    args = parser.parse_args()
    
    connection_string = get_connection_string()
    if not connection_string:
        return False
    
    # First test the connection
    if not test_connection(connection_string):
        return False
    
    # If verify-only flag is set, just check and exit
    if args.verify_only:
        schema_exists = check_existing_schema(connection_string)
        if schema_exists:
            logger.info("Database schema verification successful!")
        else:
            logger.warning("Database schema verification failed - schema missing or incomplete")
        return schema_exists
    
    # Otherwise proceed with setup
    success = setup_database(force=args.force)
    
    if success:
        logger.info("Database setup completed successfully!")
        return True
    else:
        logger.error("Database setup failed. Please check the logs for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
