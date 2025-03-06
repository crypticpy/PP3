
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
    }
  },
});
