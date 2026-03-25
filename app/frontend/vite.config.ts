import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url' // Modern ESM replacement for 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Modern ESM replacement for __dirname
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  
  // --- LOCAL DEV PROXY ---
  server: {
    proxy: {
      // Directs any call to /api/... to your Nginx gateway on port 80
      '/api': {
        target: 'http://localhost:80',
        changeOrigin: true,
      },
    },
  },
  // -------------------------

  assetsInclude: ['**/*.svg', '**/*.csv'],
})