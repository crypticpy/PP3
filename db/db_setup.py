
#!/usr/bin/env python
"""
db_setup.py

Sets up the PolicyPulse database by creating the required tables
and structures based on the schema defined in policypulse_schema.sql.
"""

import os
import sys
import logging
import argparse
import psycopg2
from psycopg2 import sql

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def create_database():
    """
    Create the database using the SQL schema file.
    """
    # Get database connection details from environment variables
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        logger.error("DATABASE_URL not found. Please make sure the PostgreSQL database is set up correctly in Replit.")
        sys.exit(1)
        
    logger.info("Attempting to set up database using schema...")
    
    # Read the schema file
    schema_path = os.path.join(os.path.dirname(__file__), 'policypulse_schema.sql')
    try:
        with open(schema_path, 'r') as file:
            schema_sql = file.read()
    except FileNotFoundError:
        logger.error(f"Schema file not found at {schema_path}")
        sys.exit(1)
        
    # Connect to the database and apply the schema
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        with conn.cursor() as cursor:
            logger.info("Executing schema SQL...")
            cursor.execute(schema_sql)
        logger.info("Database schema successfully applied")
        return True
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verify_database():
    """
    Verify that the database has been set up correctly.
    """
    # Get database connection details
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        logger.error("DATABASE_URL not found")
        return False
        
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cursor:
            # Check if primary tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN (
                    'users', 'legislation', 'legislation_analysis', 
                    'legislation_priorities', 'sync_metadata'
                )
            """)
            tables = cursor.fetchall()
            if len(tables) < 5:
                logger.warning(f"Some expected tables are missing. Found: {[t[0] for t in tables]}")
                return False
                
            # Check if admin user exists
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()[0]
            if admin_count == 0:
                logger.warning("No admin user found")
                return False
                
            logger.info("Database structure verified successfully")
            return True
    except psycopg2.Error as e:
        logger.error(f"Database verification error: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up the PolicyPulse database")
    parser.add_argument("--recreate", action="store_true", help="Recreate the database (warning: this will delete existing data)")
    parser.add_argument("--verify", action="store_true", help="Verify database structure only")
    
    args = parser.parse_args()
    
    if args.verify:
        success = verify_database()
        sys.exit(0 if success else 1)
    
    # Create the database
    success = create_database()
    
    if success and verify_database():
        logger.info("Database setup completed successfully!")
        sys.exit(0)
    else:
        logger.error("Database setup failed")
        sys.exit(1)
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
