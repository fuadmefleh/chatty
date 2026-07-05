import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/explorer': {
        target: 'http://localhost:8015',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/explorer/, ''),
      },
      '/api/chatty': {
        target: 'http://localhost:8016',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  preview: {
    // Trusts all Host headers rather than hardcoding one deployer's domain.
    // Safe here: in the Docker Compose deployment (see ../../docker-compose.yml)
    // `vite preview`'s dev-only use is superseded by a dedicated nginx image,
    // and this config's own `npm run preview` is only ever reached through a
    // trusted reverse proxy on an internal network, never exposed directly.
    allowedHosts: true,
  },
})
