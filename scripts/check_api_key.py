
#!/usr/bin/env python
"""
check_api_key.py

Script to check if LegiScan API key is properly set up
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def check_legiscan_api_key():
    """Check if LegiScan API key is set in environment variables"""
    api_key = os.environ.get("LEGISCAN_API_KEY")
    
    if not api_key:
        logger.error("❌ LEGISCAN_API_KEY not found in environment variables")
        logger.info("Please set the LEGISCAN_API_KEY in Secrets tab (Tools > Secrets)")
        return False
    else:
        logger.info("✅ LEGISCAN_API_KEY found in environment variables")
        # Just show first few characters for security
        visible_part = api_key[:4] + "..." if len(api_key) > 4 else ""
        logger.info(f"Key starts with: {visible_part}")
        return True

if __name__ == "__main__":
    logger.info("Checking for LegiScan API key...")
    if not check_legiscan_api_key():
        logger.info("To add the API key:")
        logger.info("1. Go to Tools > Secrets in the Replit interface")
        logger.info("2. Add a new secret with key 'LEGISCAN_API_KEY'")
        logger.info("3. Set the value to your LegiScan API key")
        sys.exit(1)
    else:
        logger.info("LegiScan API key is properly set up")
        sys.exit(0)
