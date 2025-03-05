
#!/usr/bin/env python
"""
setup_database.py

A simple script to set up the PolicyPulse database in Replit.
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """Main function to set up the database."""
    # Check if DATABASE_URL environment variable is set
    if 'DATABASE_URL' not in os.environ:
        logger.error("DATABASE_URL environment variable not found.")
        logger.error("Please set up a PostgreSQL database in your Replit project.")
        logger.error("Go to 'Database' tab in the left sidebar and create a new PostgreSQL database.")
        return 1
    
    # Execute database setup
    try:
        logger.info("Setting up the PolicyPulse database...")
        
        # Import the setup module from the db package
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from db.db_setup import main as setup_main
        
        # Run the setup
        if setup_main():
            logger.info("Database setup completed successfully!")
            
            # Verify the setup
            from db.db_verify import verify_setup
            if verify_setup(verbose=True):
                logger.info("Database verification passed!")
                return 0
            else:
                logger.error("Database verification failed.")
                return 1
        else:
            logger.error("Database setup failed.")
            return 1
    except Exception as e:
        logger.error(f"Error during database setup: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
