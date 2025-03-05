#!/usr/bin/env python
"""
PolicyPulse main run script.
Initializes and runs the API server for the PolicyPulse application.
"""

import os
import logging
import argparse
from app.run_api import start_api_server
from app.scheduler import PolicyPulseScheduler

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the PolicyPulse application."""
    parser = argparse.ArgumentParser(description="Run the PolicyPulse application.")
    parser.add_argument('--port', type=int, default=3000, help='Port to run the API server on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the API server on')
    parser.add_argument('--scheduler', action='store_true', help='Run with background scheduler')

    args = parser.parse_args()

    if args.scheduler:
        logger.info("Starting PolicyPulse with background scheduler")
        scheduler = PolicyPulseScheduler()
        scheduler.start()

    logger.info(f"Starting PolicyPulse API server on {args.host}:{args.port}")
    start_api_server(host=args.host, port=args.port)

if __name__ == "__main__":
    main()