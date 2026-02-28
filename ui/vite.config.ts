import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    strictPort: true,
    open: '/v2',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8585',
        changeOrigin: true
      }
    }
  }
});
