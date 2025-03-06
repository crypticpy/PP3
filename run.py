
import os
import sys
import logging
from pathlib import Path

# Configure logging before importing any app modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Add the current directory to the path to allow proper imports
        current_dir = str(Path(__file__).parent.absolute())
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
            
        logger.info("Starting PolicyPulse application")
        
        # Set environment variables needed for the app
        os.environ.setdefault("PORT", "3000")
        os.environ.setdefault("HOST", "0.0.0.0")
        
        # Import and run the API
        import uvicorn
        from app.api import app
        
        # Get the port and host from environment variables
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", 3000))
        
        logger.info(f"Starting server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
        
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
