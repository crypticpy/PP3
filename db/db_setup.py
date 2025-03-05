
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
