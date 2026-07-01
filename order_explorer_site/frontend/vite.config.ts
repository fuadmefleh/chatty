import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
    allowedHosts: ['fuadmefleh.fyi', 'www.fuadmefleh.fyi'],
  },
})
