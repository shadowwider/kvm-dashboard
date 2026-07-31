import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const serverPort = Number(env.SIMULATOR_UI_PORT || 13100);
  const simulatorTarget = env.VITE_SIMULATOR_TARGET || 'http://127.0.0.1:8888';

  return {
    plugins: [react()],
    base: './',
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
    server: {
      port: serverPort,
      strictPort: true,
      proxy: {
        '/api': {
          target: simulatorTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});
