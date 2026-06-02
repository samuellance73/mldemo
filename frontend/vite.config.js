import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
    server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7861', // Map to local port 7861 during local dev
        changeOrigin: true,
        secure: false,
      }
    }
  },
  build: {
    // Compile directly into the main/dist folder for automated packaging
    outDir: '../main/dist/frontend_dist',
    emptyOutDir: true,
  }
})
