import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT || '5175'),
    strictPort: false,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://0.0.0.0:8002',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },
    },
    cors: true,
    hmr: {
      // Enhanced HMR config for Replit
      clientPort: 443,  // For Replit
      host: '0.0.0.0',
      protocol: 'wss',
      timeout: 120000,
    },
    watch: {
      usePolling: true,
      interval: 1000,
    },
    fs: {
      strict: false
    },
    // Allow all Replit hosts
    allowedHosts: [
      'picard.replit.dev', 
      '2d81b13f-422b-4641-a71e-b98d13690b4c-00-25k3c676pm01w.picard.replit.dev',
      '.replit.dev',
      'all'
    ]
  },
  // Add optimizeDeps to help with module resolution
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom'],
    force: true
  },
  // Ensure we have full source maps for debugging
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom']
        }
      }
    }
  }
});