import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inside Docker (compose) the api is reachable by service name.
// Outside Docker (plain npm run dev) it's on localhost.
const API_URL = process.env.API_URL || 'http://localhost:3000'

export default defineConfig({
  root: 'client',
  plugins: [react()],
  server: {
    host: '0.0.0.0',  // bind to all interfaces so the port is reachable from the host
    proxy: {
      '/health': API_URL,
      '/config': API_URL,
      '/uploads': API_URL,
      '/files': API_URL,
    },
  },
  build: {
    outDir: '../public',
    emptyOutDir: true,
  },
})
