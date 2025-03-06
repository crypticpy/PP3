
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT || '5173'),
    strictPort: false,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://0.0.0.0:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },
    },
    cors: true,
    hmr: {
      // Simplified HMR config
      port: 5173,
      host: '0.0.0.0',
    },
    watch: {
      usePolling: true,
      interval: 1000,
    },
    fs: {
      strict: false
    },
    // Allow all Replit hosts
    allowedHosts: 'all'
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
