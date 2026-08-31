import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  // GitHub Pages のサブパス配信用。ローカルは '/'
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        // ホストで `npm run dev` する場合は localhost:8000。
        // frontend コンテナから叩く場合は VITE_API_TARGET=http://backend:8000 を渡す
        target: process.env.VITE_API_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
