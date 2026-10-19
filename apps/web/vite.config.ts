import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const base = loadEnv(mode, process.cwd(), 'VITE_').VITE_API_BASE_URL?.trim();
  if (command === 'build' && base && base !== '/api') {
    const url = new URL(base);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || !['', '/', '/api', '/api/'].includes(url.pathname)) {
      throw new Error('VITE_API_BASE_URL must be an HTTPS backend origin, optionally ending in /api.');
    }
  }
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})

