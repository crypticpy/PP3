
#!/usr/bin/env python
"""
db_verify.py

Verifies the PolicyPulse database setup and structure.
Can also attempt to fix common database issues.
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

def verify_connection():
    """Verify database connection."""
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        logger.error("DATABASE_URL not found. Please make sure the PostgreSQL database is set up correctly in Replit.")
        return False
    
    try:
        conn = psycopg2.connect(db_url)
        logger.info("Successfully connected to database")
        conn.close()
        return True
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to database: {e}")
        return False

def verify_tables():
    """Verify that all required tables exist."""
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        logger.error("DATABASE_URL not found")
        return False
        
    expected_tables = [
        'users', 'user_preferences', 'search_history', 'alert_preferences',
        'legislation', 'legislation_analysis', 'legislation_text', 'legislation_sponsors',
        'amendments', 'legislation_priorities', 'impact_ratings', 'implementation_requirements',
        'alert_history', 'sync_metadata', 'sync_errors'
    ]
    
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            
            if missing_tables:
                logger.error(f"Missing tables: {', '.join(missing_tables)}")
                return False
            else:
                logger.info("All required tables exist")
                return True
    except psycopg2.Error as e:
        logger.error(f"Database error while verifying tables: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def verify_enums():
    """Verify that all required enum types exist."""
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        logger.error("DATABASE_URL not found")
        return False
        
    expected_enums = [
        'data_source_enum', 'govt_type_enum', 'bill_status_enum',
        'impact_level_enum', 'impact_category_enum', 'amendment_status_enum',
        'notification_type_enum', 'sync_status_enum'
    ]
    
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT t.typname
                FROM pg_type t 
                JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typtype = 'e' AND n.nspname = 'public'
            """)
            existing_enums = [row[0] for row in cursor.fetchall()]
            
            missing_enums = [enum for enum in expected_enums if enum not in existing_enums]
            
            if missing_enums:
                logger.error(f"Missing enum types: {', '.join(missing_enums)}")
                return False
            else:
                logger.info("All required enum types exist")
                return True
    except psycopg2.Error as e:
        logger.error(f"Database error while verifying enums: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def attempt_fix():
    """Attempt to fix database issues by applying the schema."""
    from db_setup import create_database
    
    logger.info("Attempting to fix database issues by applying the schema...")
    success = create_database()
    if success:
        logger.info("Database fix attempt completed successfully")
    else:
        logger.error("Database fix attempt failed")
    return success

def main():
    parser = argparse.ArgumentParser(description="Verify PolicyPulse database setup")
    parser.add_argument("--verbose", action="store_true", help="Show detailed verification information")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix database issues")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Perform verification steps
    connection_ok = verify_connection()
    if not connection_ok:
        logger.error("Database connection verification failed")
        if args.fix:
            logger.info("Cannot fix connection issues automatically")
        return False
        
    tables_ok = verify_tables()
    enums_ok = verify_enums()
    
    all_ok = connection_ok and tables_ok and enums_ok
    
    if all_ok:
        logger.info("All database verifications passed")
        return True
    else:
        logger.warning("Some database verifications failed")
        if args.fix:
            logger.info("Attempting to fix database issues...")
            return attempt_fix()
        else:
            logger.info("Run with --fix to attempt automatic fixes")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python
"""
db_verify.py

This script verifies the PolicyPulse database setup by:
1. Connecting to the PostgreSQL database
2. Checking if all required tables exist
3. Checking if initial data is present
"""

import os
import sys
import logging
import argparse
import psycopg2

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

def verify_tables(conn, verbose=False):
    """Verify all required tables exist in the database."""
    required_tables = [
        'users', 'user_preferences', 'search_history', 'alert_preferences',
        'legislation', 'legislation_analysis', 'legislation_text', 'legislation_sponsors',
        'amendments', 'legislation_priorities', 'impact_ratings', 
        'implementation_requirements', 'alert_history', 'sync_metadata', 'sync_errors'
    ]
    
    missing_tables = []
    
    try:
        with conn.cursor() as cur:
            for table in required_tables:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    )
                """, (table,))
                exists = cur.fetchone()[0]
                
                if verbose:
                    status = "✅" if exists else "❌"
                    logger.info(f"{status} Table {table}")
                
                if not exists:
                    missing_tables.append(table)
        
        return missing_tables
    except Exception as e:
        logger.error(f"Error verifying tables: {e}")
        return required_tables  # Assume all tables are missing on error

def verify_initial_data(conn, verbose=False):
    """Verify initial data is present in the database."""
    checks = [
        {
            'name': 'Admin user',
            'query': "SELECT COUNT(*) FROM users WHERE email = 'admin@policypulse.org'",
            'expected': 1
        },
        {
            'name': 'Alert preferences',
            'query': "SELECT COUNT(*) FROM alert_preferences WHERE email = 'admin@policypulse.org'",
            'expected': 1
        },
        {
            'name': 'Initial sync record',
            'query': "SELECT COUNT(*) FROM sync_metadata WHERE sync_type = 'initial'",
            'expected': 1
        }
    ]
    
    failed_checks = []
    
    try:
        with conn.cursor() as cur:
            for check in checks:
                cur.execute(check['query'])
                count = cur.fetchone()[0]
                
                if verbose:
                    status = "✅" if count == check['expected'] else "❌"
                    logger.info(f"{status} {check['name']}: Found {count}, expected {check['expected']}")
                
                if count != check['expected']:
                    failed_checks.append(check['name'])
        
        return failed_checks
    except Exception as e:
        logger.error(f"Error verifying initial data: {e}")
        return [check['name'] for check in checks]  # Assume all checks failed on error

def verify_setup(verbose=False):
    """Verify the database setup."""
    connection_string = get_connection_string()
    
    if not connection_string:
        logger.error("No database connection information found in environment variables")
        return False
    
    try:
        # Connect to the database
        if verbose:
            logger.info("Connecting to the database...")
        
        conn = psycopg2.connect(connection_string)
        
        # Verify tables
        if verbose:
            logger.info("Verifying tables...")
        
        missing_tables = verify_tables(conn, verbose)
        
        if missing_tables:
            logger.error(f"Missing tables: {', '.join(missing_tables)}")
            return False
        elif verbose:
            logger.info("All required tables exist ✅")
        
        # Verify initial data
        if verbose:
            logger.info("Verifying initial data...")
        
        failed_checks = verify_initial_data(conn, verbose)
        
        if failed_checks:
            logger.error(f"Failed data checks: {', '.join(failed_checks)}")
            return False
        elif verbose:
            logger.info("All initial data checks passed ✅")
        
        # All checks passed
        if verbose:
            logger.info("Database verification completed successfully! ✅")
        
        return True
    
    except Exception as e:
        logger.error(f"Error verifying database setup: {e}")
        return False
    
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='Verify PolicyPulse database setup')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    success = verify_setup(args.verbose)
    
    if not args.verbose:
        if success:
            print("Database verification successful")
        else:
            print("Database verification failed")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
