
#!/usr/bin/env python
"""
run.py

Main entry point for the PolicyPulse application.
Initializes the database and starts the API server.
"""

import os
import sys
import logging
import subprocess
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def check_database_url():
    """Check if DATABASE_URL is set."""
    if not os.environ.get("DATABASE_URL"):
        logger.error("DATABASE_URL environment variable is not set!")
        logger.error("Please set up a PostgreSQL database in Replit first.")
        return False
    return True

def verify_database():
    """Verify database setup by running the verification script."""
    logger.info("Verifying database setup...")
    result = subprocess.run(["python", "db/db_verify.py"], capture_output=True)
    
    if result.returncode != 0:
        logger.warning("Database verification failed. Attempting to set up the database...")
        setup_result = subprocess.run(["python", "db/db_setup.py"])
        if setup_result.returncode != 0:
            logger.error("Database setup failed. Please check the logs.")
            return False
        
        # Verify again after setup
        verify_result = subprocess.run(["python", "db/db_verify.py"])
        if verify_result.returncode != 0:
            logger.error("Database verification still failed after setup. Application may not function correctly.")
            return False
    
    logger.info("Database verification passed!")
    return True

def run_api_server():
    """Start the API server."""
    logger.info("Starting API server...")
    subprocess.run(["python", "app/run_api.py"])

def run_cli_command(args):
    """Run a CLI command."""
    cli_args = ["python", "app/cli.py"] + args
    logger.info(f"Running CLI command: {' '.join(cli_args)}")
    subprocess.run(cli_args)

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="PolicyPulse Application Runner")
    parser.add_argument("--skip-db-check", action="store_true", help="Skip database verification")
    parser.add_argument("--cli", nargs="+", help="Run a CLI command")
    
    args = parser.parse_args()
    
    # Check database URL
    if not check_database_url():
        sys.exit(1)
    
    # Verify database if not skipped
    if not args.skip_db_check:
        if not verify_database():
            logger.warning("Continuing despite database verification issues...")
    
    # Run CLI command if specified
    if args.cli:
        run_cli_command(args.cli)
        return
    
    # Otherwise, run the API server
    run_api_server()

if __name__ == "__main__":
    main()
