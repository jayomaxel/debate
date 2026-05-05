import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiProxyTarget =
    env.VITE_DEV_API_PROXY_TARGET || 'http://localhost:7861';
  const wsProxyTarget =
    env.VITE_DEV_WS_PROXY_TARGET || apiProxyTarget.replace(/^http/, 'ws');

  return {
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
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/uploads': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/ws': {
          target: wsProxyTarget,
          ws: true,
        },
      },
    },
  };
});
