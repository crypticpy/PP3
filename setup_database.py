
#!/usr/bin/env python
"""
setup_database.py

A comprehensive script to set up and verify the PolicyPulse database in Replit.
"""

import os
import sys
import logging
import time
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if the environment is properly set up."""
    # Check if DATABASE_URL environment variable is set
    if 'DATABASE_URL' not in os.environ:
        logger.error("DATABASE_URL environment variable not found.")
        logger.error("Please set up a PostgreSQL database in your Replit project:")
        logger.error("1. Open the 'Database' tab in the Replit sidebar (left)")
        logger.error("2. Click 'Create a database'")
        logger.error("3. Wait for the database to be created")
        logger.error("4. Run this script again")
        return False
        
    logger.info(f"DATABASE_URL found: {os.environ['DATABASE_URL'][:20]}...")
    return True

def execute_setup():
    """Execute the database setup process."""
    logger.info("Setting up the PolicyPulse database...")
    
    try:
        # Run db_setup.py
        logger.info("Running database schema creation...")
        from db.db_setup import main as setup_main
        
        if not setup_main():
            logger.error("Database schema creation failed")
            return False
            
        logger.info("Database schema created successfully")
        return True
    except Exception as e:
        logger.error(f"Error during database setup: {e}")
        return False

def verify_setup():
    """Verify the database setup."""
    logger.info("Verifying database setup...")
    
    try:
        # Import the verification module
        from app.db_connection import check_database_status
        
        # Check database status
        status = check_database_status()
        
        if not status["connection"]:
            logger.error(f"Could not connect to database: {status['error']}")
            return False
            
        if status["details"].get("missing_tables"):
            logger.error(f"Missing tables: {', '.join(status['details']['missing_tables'])}")
            return False
            
        if not status["details"].get("admin_user_exists", False):
            logger.error("Admin user does not exist")
            return False
            
        logger.info(f"Database verified: {len(status['tables'])} tables found")
        logger.info("All required tables and data present")
        return True
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        return False

def main():
    """Main function to set up and verify the database."""
    parser = argparse.ArgumentParser(description="Set up and verify the PolicyPulse database")
    parser.add_argument("--force", action="store_true", help="Force setup even if verification passes")
    parser.add_argument("--verify-only", action="store_true", help="Only verify the database, don't set it up")
    args = parser.parse_args()
    
    # First, check if the environment is set up correctly
    if not check_environment():
        return 1
    
    # If verify-only flag is set, just verify and exit
    if args.verify_only:
        logger.info("Verification only mode")
        success = verify_setup()
        return 0 if success else 1
    
    # Check if we need to run setup
    if not args.force:
        try:
            from app.db_connection import check_database_status
            status = check_database_status()
            
            # If we can connect and all required tables exist, skip setup
            if (status["connection"] and 
                not status["details"].get("missing_tables") and
                status["details"].get("admin_user_exists", False)):
                logger.info("Database already set up correctly. Use --force to run setup anyway.")
                return 0
        except:
            # If verification fails, continue with setup
            pass
    
    # Run the setup
    if not execute_setup():
        logger.error("Database setup failed. Please check the logs for details.")
        return 1
    
    # Verify setup
    logger.info("Waiting 2 seconds for changes to propagate...")
    time.sleep(2)
    
    if verify_setup():
        logger.info("Database setup and verification completed successfully!")
        logger.info("The PolicyPulse database is ready to use.")
        return 0
    else:
        logger.error("Database verification failed after setup.")
        logger.error("The database might not be fully functional.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
