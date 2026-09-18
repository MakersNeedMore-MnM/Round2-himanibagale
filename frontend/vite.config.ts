import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The production build lands directly inside the Python package so the
// daemon can serve the dashboard from its own directory (see
// backend/daemon/server.py).  Keeping the output in the package tree —
// instead of a copy step — means `npm run build` is the whole pipeline.
// The dev server is unaffected: `npm run dev` still serves from memory
// with HMR on :5173 and talks to the daemon on :8765 via CORS.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../backend/daemon/static',
    emptyOutDir: true, // safe: the target is inside ../backend, Vite allows it explicitly
  },
})
