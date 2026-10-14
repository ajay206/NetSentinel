/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const gatewayUrl = process.env.VITE_GATEWAY_URL || 'http://127.0.0.1:8000';

function ignoreProxyHangup(err: NodeJS.ErrnoException) {
  return err.code === 'EPIPE' || err.code === 'ECONNRESET';
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: gatewayUrl,
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: gatewayUrl,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: gatewayUrl,
        ws: true,
        changeOrigin: true,
        secure: false,
        configure(proxy) {
          proxy.on('error', (err) => {
            if (ignoreProxyHangup(err as NodeJS.ErrnoException)) {
              return;
            }
            console.error('[vite] proxy error', err);
          });
          proxy.on('proxyReqWs', (_proxyReq, _req, socket) => {
            socket.on('error', (err: NodeJS.ErrnoException) => {
              if (ignoreProxyHangup(err)) {
                return;
              }
            });
          });
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
  },
});
