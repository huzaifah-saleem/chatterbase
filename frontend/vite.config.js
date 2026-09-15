// Vite config: React + Tailwind v4 plugin, dev-server proxy that forwards
// /api/* to the Flask backend on :5000 so `npm run dev` works against a
// locally running app.py without CORS or build steps.
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    },
  },
})
