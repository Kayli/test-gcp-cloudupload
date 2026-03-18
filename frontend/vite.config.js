import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inside Docker (compose) the api is reachable by service name.
// Outside Docker (plain npm run dev) it's on localhost.
const API_URL   = process.env.API_URL   || 'http://localhost:3000'
// MinIO is reachable by service name inside compose, localhost elsewhere.
const MINIO_URL = process.env.MINIO_URL || 'http://localhost:9000'

export default defineConfig({
  root: '.',
  plugins: [react()],
  server: {
    host: '0.0.0.0',  // bind to all interfaces so the port is reachable from the host
    proxy: {
      '/health': API_URL,
      '/config': API_URL,
      '/uploads': API_URL,
      '/files':   API_URL,
      // Proxy MinIO object storage through Vite so the host browser can reach
      // it without needing port 9000 forwarded.  The bucket is named "objstore"
      // so its path (/objstore/...) never collides with the /uploads API route.
      //
      // changeOrigin MUST be false: S3 presigned URLs embed the Host in the
      // HMAC signature.  If Vite rewrites Host to minio:9000 the signature
      // won't match → 403 SignatureDoesNotMatch.  Keeping the original
      // Host: localhost:5173 makes the signature validate correctly.
      '/objstore': {
        target:       MINIO_URL,
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: '../public',
    emptyOutDir: true,
  },
})
