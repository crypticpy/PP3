
#!/usr/bin/env python
"""
run_api.py

Starts the PolicyPulse API server with proper configuration.
"""

import os
import uvicorn
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """Start the API server."""
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8000))
    
    logger.info(f"Starting PolicyPulse API server on {host}:{port}")
    
    # Check if database URL is set
    if not os.environ.get("DATABASE_URL"):
        logger.warning("DATABASE_URL not set! Database operations will fail.")
    
    # Start the API server
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        log_level="info",
        reload=True,
        access_log=True
    )

if __name__ == "__main__":
    main()
