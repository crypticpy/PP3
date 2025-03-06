import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // Listen on all interfaces (0.0.0.0) to make the server accessible from outside
    host: '0.0.0.0',
    // Use PORT env var (set by run.py) or fallback to 5175
    // IMPORTANT: Don't hardcode this port as run.py dynamically finds available ports
    port: parseInt(process.env.PORT || '5175'),
    // Don't exit if port is already in use (run.py handles port availability)
    strictPort: false,
    // API proxy configuration - critical for frontend/backend communication
    proxy: {
      '/api': {
        // IMPORTANT: The backend port is dynamically set by run.py through VITE_BACKEND_PORT env var
        // DO NOT hardcode a specific port number here as it will break the application
        // The port is determined at runtime and passed to the frontend
        target: `http://0.0.0.0:${process.env.VITE_BACKEND_PORT || '8001'}`,
        changeOrigin: true,
        secure: false,
        // Strip /api prefix when forwarding to backend
        rewrite: (path) => path.replace(/^\/api/, ''),
        configure: (proxy, options) => {
          // Log all proxy errors with more detail
          proxy.on('error', (err, req, res) => {
            console.error(`Proxy error for ${req.method} ${req.url}:`, err.message);
          });
          
          // Log outgoing proxy requests with full path
          // IMPORTANT: This uses the dynamic options.target which contains the correct port
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log(`Proxying ${req.method} ${req.url} to ${options.target}${proxyReq.path}`);
          });
          
          // Log incoming proxy responses with status code
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log(`Received response from proxy: ${proxyRes.statusCode} for ${req.method} ${req.url}`);
          });
        },
        // Increase timeout for slow responses
        timeout: 30000
      },
    },
    // Enable CORS for development
    cors: true,
    // Hot Module Replacement configuration - specifically tuned for Replit environment
    hmr: {
      // IMPORTANT: These settings are specifically for Replit's environment 
      // The clientPort 443 is required for Replit's HTTPS connections
      clientPort: 443,  // Required for Replit
      host: '0.0.0.0',
      protocol: 'wss', // WebSocket Secure protocol for Replit
      timeout: 120000, // Long timeout for Replit's sometimes slower connections
      overlay: true,
      reconnect: 10000, // Extended reconnection time due to Replit's environment
    },
    // File watching configuration - important for Replit's filesystem
    watch: {
      // IMPORTANT: usePolling is required in Replit's environment
      // otherwise file changes may not be detected properly
      usePolling: true,
      interval: 1000,
    },
    // Filesystem configuration
    fs: {
      strict: false // Allow importing from outside of project root
    },
    // IMPORTANT: These allowedHosts settings are required for proper functioning in Replit
    // Without these, the development server will reject connections
    allowedHosts: [
      'picard.replit.dev', 
      '2d81b13f-422b-4641-a71e-b98d13690b4c-00-25k3c676pm01w.picard.replit.dev',
      '.replit.dev',
      'all'
    ]
  },
  // Dependencies optimization configuration
  // IMPORTANT: This helps with module resolution in Replit's environment
  optimizeDeps: {
    // Pre-bundle these dependencies for faster development server start
    include: ['react', 'react-dom', 'react-router-dom'],
    // Force dependency pre-bundling even after server restart
    force: true
  },
  // Production build configuration
  // IMPORTANT: These settings affect how the application is bundled for production
  build: {
    // Generate source maps for debugging
    sourcemap: true,
    rollupOptions: {
      output: {
        // Split React libraries into a separate vendor chunk for better caching
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom']
        }
      }
    }
  }
  // IMPORTANT NOTE FOR FUTURE REFERENCE:
  // 1. The backend port is dynamically assigned by run.py
  // 2. The port is passed to Vite through VITE_BACKEND_PORT environment variable
  // 3. DO NOT hardcode port numbers in the proxy configuration
  // 4. The application uses relative API paths (/api) which are proxied to the backend
});