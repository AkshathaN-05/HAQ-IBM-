import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the API runs on :8000 and Vite proxies /api to it, so the browser
// only ever talks to one origin and no API keys are needed in the frontend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': process.env.VITE_API_PROXY || 'http://127.0.0.1:8000' },
  },
  build: { sourcemap: false },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
    globals: true,
  },
})
