import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 8860,
    strictPort: true,
    allowedHosts: ['csidebate.xyz', '8.137.182.23'],
    proxy: {
      '/api': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:7860',
        ws: true,
      },
    },
  },
});
