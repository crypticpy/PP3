import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://0.0.0.0:8000',
        changeOrigin: true,
      },
    },
    allowedHosts: [
      '2d81b13f-422b-4641-a71e-b98d13690b4c-00-25k3c676pm01w.picard.replit.dev',
      '.replit.dev'
    ],
  },
}); 