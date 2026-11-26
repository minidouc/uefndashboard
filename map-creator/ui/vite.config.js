import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/rpc': 'http://127.0.0.1:4310',
      '/api': 'http://127.0.0.1:4310',
      '/ws': {
        target: 'ws://127.0.0.1:4310',
        ws: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});
