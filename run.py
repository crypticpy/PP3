import os
import sys
import logging
import socket
import subprocess
import threading
import time
import requests
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

def wait_for_frontend(frontend_port, max_attempts=30):
    """Wait until the frontend server is available."""
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"http://0.0.0.0:{frontend_port}/", timeout=2)
            if response.status_code == 200:
                logger.info(f"Frontend is ready after {attempt+1} attempts")
                return True
        except requests.RequestException:
            pass

        logger.info(f"Waiting for frontend to start (attempt {attempt+1}/{max_attempts})...")
        time.sleep(1)

    logger.warning("Frontend did not start in the expected time")
    return False

def start_frontend(frontend_port, backend_port):
    """Start the frontend application using npm."""
    # Use the correct path to the project root
    project_root = Path(__file__).parent

    logger.info(f"Starting frontend from project root: {project_root} on port {frontend_port}")
    os.chdir(project_root)

    # Set environment variables for frontend
    env = os.environ.copy()
    env["PORT"] = str(frontend_port)
    env["VITE_API_URL"] = f"http://0.0.0.0:{backend_port}"  # Direct connection to backend
    env["VITE_BACKEND_PORT"] = str(backend_port)

    # Make sure node_modules exists
    if not os.path.exists("node_modules"):
        logger.info("Installing frontend dependencies...")
        try:
            subprocess.run(["npm", "install", "--legacy-peer-deps"], check=True)
        except subprocess.CalledProcessError:
            logger.warning("npm install failed with legacy-peer-deps, trying with force...")
            subprocess.run(["npm", "install", "--force"], check=True)

    # Start npm in development mode with explicit host and port
    try:
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(frontend_port), "--host", "0.0.0.0"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Safely log frontend output
        if process and process.stdout:
            for line in iter(process.stdout.readline, ''):
                if line:  # Only log non-empty lines
                    logger.info(f"FRONTEND: {line.strip()}")

            # Properly close stdout
            process.stdout.close()

            # Wait for process to complete
            return_code = process.wait()
            if return_code != 0:
                logger.error(f"Frontend process exited with code {return_code}")
        else:
            logger.error("Frontend process or stdout is None")
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

        # Set fixed ports for better predictability on Replit
        frontend_port = 5173   # Vite default port
        backend_port = 8000    # FastAPI default port

        # Make sure ports are free
        frontend_port = find_available_port(frontend_port)
        backend_port = find_available_port(backend_port)

        # Set environment variables
        os.environ["FRONTEND_PORT"] = str(frontend_port)
        os.environ["BACKEND_PORT"] = str(backend_port)

        logger.info(f"Using ports - Frontend: {frontend_port}, Backend: {backend_port}")

        # Start backend first to ensure API is available
        backend_thread = threading.Thread(target=start_backend, args=(backend_port,), daemon=True)
        backend_thread.start()

        # Wait for backend to start
        time.sleep(3)
        logger.info("Backend started, now starting frontend...")

        # Start frontend with direct access to backend
        frontend_process = threading.Thread(target=start_frontend, args=(frontend_port, backend_port))
        frontend_process.start()

        # Print service URLs for easy access
        replit_domain = os.environ.get("REPL_SLUG", "replit-app")
        print(f"\n==== PolicyPulse Application Started ====")
        print(f"  - Backend API: http://0.0.0.0:{backend_port}")
        print(f"  - Frontend UI: http://0.0.0.0:{frontend_port}")
        print(f"For external access, use your Replit domain with these ports")
        print(f"=========================================\n")

        # Keep main thread alive
        frontend_process.join()

    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()