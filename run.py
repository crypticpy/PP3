import os
import sys
import logging
import socket
import subprocess
import threading
import time
import requests
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

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

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Forward API requests to the backend
        if self.path.startswith('/api/'):
            backend_url = f"http://0.0.0.0:{os.environ.get('BACKEND_PORT')}{self.path}"
            self.proxy_request(backend_url)
        # Root path should serve the frontend
        elif self.path == "/" or self.path == "":
            frontend_url = f"http://0.0.0.0:{os.environ.get('FRONTEND_PORT')}/"
            self.proxy_request(frontend_url)
        # All other requests go to the frontend
        else:
            frontend_url = f"http://0.0.0.0:{os.environ.get('FRONTEND_PORT')}{self.path}"
            self.proxy_request(frontend_url)

    def do_POST(self):
        # Handle POST requests similarly
        if self.path.startswith('/api/'):
            backend_url = f"http://0.0.0.0:{os.environ.get('BACKEND_PORT')}{self.path}"  # Using 0.0.0.0 instead of localhost
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            self.proxy_request(backend_url, method='POST', data=post_data)
        else:
            frontend_url = f"http://0.0.0.0:{os.environ.get('FRONTEND_PORT')}{self.path}"  # Using 0.0.0.0 instead of localhost
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            self.proxy_request(frontend_url, method='POST', data=post_data)

    def proxy_request(self, url, method='GET', data=None):
        try:
            # Copy headers from original request
            headers = {k: v for k, v in self.headers.items()}
            
            # Log the proxy request for debugging
            logger.info(f"Proxying {method} request to: {url}")

            # Make the request to the target service
            response = None  # Initialize with None to ensure it's always defined
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=data, timeout=10)

            # Ensure response is not None before proceeding
            if response is not None:
                # Log response status for debugging
                logger.info(f"Received response: {response.status_code}")
                
                # Send the response back
                self.send_response(response.status_code)

                # Forward headers
                for key, value in response.headers.items():
                    if key.lower() not in ('connection', 'keep-alive', 'transfer-encoding'):
                        self.send_header(key, value)

                self.end_headers()

                # Send the content
                self.wfile.write(response.content)
            else:
                # Handle case where response is None
                self.send_error(500, "Internal Server Error: No response received")

        except requests.RequestException as e:
            logger.error(f"Proxy error: {str(e)}")
            self.send_error(502, f"Bad Gateway: {str(e)}")
        except Exception as e:
            logger.error(f"Proxy error: {str(e)}")
            self.send_error(500, f"Internal Server Error: {str(e)}")

    # Handle all other HTTP methods the same way
    do_PUT = do_POST
    do_DELETE = do_GET
    do_OPTIONS = do_GET
    do_HEAD = do_GET

def start_proxy(proxy_port):
    """Start a simple reverse proxy server."""
    try:
        server = HTTPServer(('0.0.0.0', proxy_port), ProxyHandler)
        logger.info(f"Starting proxy server on port {proxy_port}")
        logger.info(f"Frontend URL: http://0.0.0.0:{os.environ.get('FRONTEND_PORT')}")
        logger.info(f"Backend URL: http://0.0.0.0:{os.environ.get('BACKEND_PORT')}")
        logger.info(f"Main application URL: http://0.0.0.0:{proxy_port}")
        
        # Print debug info for users
        print(f"\n==== PolicyPulse Application Started ====")
        print(f"Access the application at: http://0.0.0.0:{proxy_port}")
        print(f"If you see connection issues in the browser, try accessing:")
        print(f"  - Frontend directly: http://0.0.0.0:{os.environ.get('FRONTEND_PORT')}")
        print(f"  - Backend directly: http://0.0.0.0:{os.environ.get('BACKEND_PORT')}")
        print(f"=========================================\n")
        
        server.serve_forever()
    except OSError as e:
        if e.errno == 98:  # Address already in use
            logger.error(f"Proxy port {proxy_port} is already in use. Please try a different port.")
            sys.exit(1)
        else:
            logger.error(f"Error starting proxy: {e}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting proxy: {e}")
        sys.exit(1)

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

def start_frontend(frontend_port):
    """Start the frontend application using npm."""
    # Use the correct path to the project root
    project_root = Path(__file__).parent

    logger.info(f"Starting frontend from project root: {project_root} on port {frontend_port}")
    os.chdir(project_root)

    # Set environment variables for frontend
    env = os.environ.copy()
    env["PORT"] = str(frontend_port)
    env["VITE_API_URL"] = f"/api"  # Use relative URL through proxy
    env["VITE_BACKEND_PORT"] = str(os.environ.get('BACKEND_PORT'))

    # Run npm install with legacy-peer-deps flag to fix React version conflicts
    if not os.path.exists("node_modules") or os.path.getmtime("package.json") > os.path.getmtime("node_modules"):
        logger.info("Installing frontend dependencies with legacy-peer-deps...")
        try:
            subprocess.run(["npm", "install", "--legacy-peer-deps"], check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"npm install failed, trying with force: {e}")
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
        proxy_port = 3000      # Main application port
        frontend_port = 5173   # Vite default port
        backend_port = 8000    # FastAPI default port

        # Make sure ports are free
        proxy_port = find_available_port(proxy_port)
        frontend_port = find_available_port(frontend_port)
        backend_port = find_available_port(backend_port)

        # Set environment variables
        os.environ["FRONTEND_PORT"] = str(frontend_port)
        os.environ["BACKEND_PORT"] = str(backend_port)

        logger.info(f"Using ports - Proxy: {proxy_port}, Frontend: {frontend_port}, Backend: {backend_port}")

        # Start backend first to ensure API is available
        backend_thread = threading.Thread(target=start_backend, args=(backend_port,), daemon=True)
        backend_thread.start()

        # Wait for backend to start
        time.sleep(3)
        logger.info("Backend started, now starting frontend...")

        # Start frontend with access to backend
        frontend_thread = threading.Thread(target=start_frontend, args=(frontend_port,), daemon=True)
        frontend_thread.start()

        # Wait for frontend to actually be ready instead of just sleeping
        if wait_for_frontend(frontend_port):
            logger.info("Frontend is ready, now starting proxy...")
        else:
            logger.warning("Frontend might not be fully ready, starting proxy anyway...")

        # Start the proxy last
        proxy_thread = threading.Thread(target=start_proxy, args=(proxy_port,))
        proxy_thread.start()

        # Wait for the proxy thread to finish
        proxy_thread.join()

    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()