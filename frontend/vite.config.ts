import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // The app always calls relative /api/v1/... paths, so the frontend never
    // hardcodes a backend host. This proxy only exists in `npm run dev`; the
    // backend's CORS setting covers a built frontend served from elsewhere.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
