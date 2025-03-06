
import os
import sys
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting PolicyPulse application")
        
        # Import app only after logging is configured
        from app.api import app
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, specify your frontend domain
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static files if needed
        try:
            app.mount("/static", StaticFiles(directory="static"), name="static")
        except:
            logger.warning("No static directory found, skipping static file mounting")
        
        # Start the server
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", 3000))
        
        logger.info(f"Starting server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
