/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: { '/api': { target: env.VITE_BACKEND_URL || 'http://127.0.0.1:8001', changeOrigin: true } },
    },
    build: { rollupOptions: { output: { manualChunks: { vendor: ['react', 'react-dom', 'react-router-dom'] } } } },
    test: { environment: 'node', include: ['src/**/*.test.ts'] },
  };
});
