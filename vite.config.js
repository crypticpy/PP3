
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
      host: 'localhost',
    },
    allowedHosts: ['2d81b13f-422b-4641-a71e-b98d13690b4c-00-25k3c676pm01w.picard.replit.dev', '.replit.dev']
  },
});
