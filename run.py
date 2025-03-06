import os
import sys
import logging
import socket
import subprocess
import threading
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port."""
    current_port = start_port
    attempts = 0

    while attempts < max_attempts:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', current_port))
                logger.info(f"Port {current_port} is available")
                return current_port
        except OSError:
            logger.warning(f"Port {current_port} is in use, trying next port")
            current_port += 1
            attempts += 1

    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

def start_frontend(frontend_port):
    """Start the frontend application using npm."""
    # Use the correct path to the src directory
    frontend_dir = Path(__file__).parent / "src"
    if not frontend_dir.exists():
        logger.error(f"Frontend directory {frontend_dir} not found")
        return

    logger.info(f"Starting frontend from directory {frontend_dir} on port {frontend_port}")
    os.chdir(frontend_dir)

    # Set environment variable for frontend port
    env = os.environ.copy()
    env["PORT"] = str(frontend_port)

    # Run npm install first if package.json exists but node_modules doesn't
    if (frontend_dir / "package.json").exists() and not (frontend_dir / "node_modules").exists():
        logger.info("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], check=True)

    # Check if we need to run from root directory instead
    if not (frontend_dir / "package.json").exists():
        # Move up to the root directory where package.json might be
        os.chdir(Path(__file__).parent)
        logger.info(f"No package.json in src, trying from project root: {os.getcwd()}")

    # Start npm in development mode
    try:
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(frontend_port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Log frontend output
        if process.stdout is not None:
            for line in iter(process.stdout.readline, ''):
                logger.info(f"FRONTEND: {line.strip()}")
            process.stdout.close()

        return_code = process.wait()
        if return_code != 0:
            logger.error(f"Frontend process exited with code {return_code}")
    except Exception as e:
        logger.error(f"Error starting frontend: {e}")

def start_backend(backend_port):
    """Start the backend using uvicorn."""
    # Add the current directory to the path to allow proper imports
    current_dir = str(Path(__file__).parent.absolute())
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    try:
        # Import and run the API
        import uvicorn
        from app.api import app

        logger.info(f"Starting backend on port {backend_port}")
        uvicorn.run(app, host="0.0.0.0", port=backend_port)

    except Exception as e:
        logger.error(f"Error starting backend: {e}", exc_info=True)
        sys.exit(1)

def main():
    try:
        logger.info("Starting PolicyPulse application")

        # Find available ports for frontend and backend
        frontend_port = find_available_port(3000)
        backend_port = find_available_port(frontend_port + 1)

        # Set environment variables
        os.environ["FRONTEND_PORT"] = str(frontend_port)
        os.environ["BACKEND_PORT"] = str(backend_port)

        # Start frontend and backend in separate threads
        frontend_thread = threading.Thread(target=start_frontend, args=(frontend_port,), daemon=True)
        backend_thread = threading.Thread(target=start_backend, args=(backend_port,))

        frontend_thread.start()
        # Short delay to ensure frontend starts first
        time.sleep(2)
        backend_thread.start()

        # Wait for the backend thread to finish (which it won't unless there's an error)
        backend_thread.join()

    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()