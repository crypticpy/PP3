#!/usr/bin/env python
"""
db_setup.py

This script sets up the PolicyPulse database by:
1. Connecting to the PostgreSQL database
2. Creating the schema if it doesn't exist
3. Setting up initial data
"""

import os
import sys
import logging
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def get_connection_string():
    """Get the database connection string from environment variables."""
    # For Replit PostgreSQL integration
    if 'DATABASE_URL' in os.environ:
        return os.environ['DATABASE_URL']

    # For local development or explicit configuration
    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', 'postgres')
    dbname = os.environ.get('DB_NAME', 'policypulse')

    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

def execute_sql_file(conn, filepath):
    """Execute SQL commands from a file."""
    try:
        with open(filepath, 'r') as f:
            sql_script = f.read()

        with conn.cursor() as cur:
            cur.execute(sql_script)

        conn.commit()
        logger.info(f"Successfully executed SQL script: {filepath}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error executing SQL script {filepath}: {e}")
        return False

def main():
    """Main function to set up the database."""
    logger.info("Starting database setup...")

    connection_string = get_connection_string()

    if not connection_string:
        logger.error("No database connection information found in environment variables")
        return False

    try:
        # Connect to the database
        logger.info("Connecting to the database...")
        conn = psycopg2.connect(connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        # Execute the schema script
        schema_path = os.path.join(os.path.dirname(__file__), 'policypulse_schema.sql')

        if not os.path.exists(schema_path):
            logger.error(f"Schema file not found: {schema_path}")
            return False

        logger.info("Creating database schema...")
        if execute_sql_file(conn, schema_path):
            logger.info("Database setup completed successfully!")
            return True
        else:
            logger.error("Database setup failed")
            return False

    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        return False
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)