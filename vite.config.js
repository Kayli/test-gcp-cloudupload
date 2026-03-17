import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  root: 'client',
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:3000',
      '/config': 'http://localhost:3000',
      '/uploads': 'http://localhost:3000',
      '/files': 'http://localhost:3000',
    },
  },
  build: {
    outDir: '../public',
    emptyOutDir: true,
  },
})
