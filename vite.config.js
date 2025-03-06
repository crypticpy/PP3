
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
      clientPort: 443,
      host: 'replit.dev',
    },
    watch: {
      usePolling: true,
      interval: 1000,
    },
    fs: {
      strict: false
    },
    // Add allowedHosts to fix the blocked host issue
    allowedHosts: ['.replit.dev', '.replit.app', '.replit.com']
  },
});
