/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const gatewayUrl = process.env.VITE_GATEWAY_URL || 'http://localhost:8000';

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
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
  },
});
