import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/expand_keywords': 'http://localhost:8000',
      '/search_papers': 'http://localhost:8000',
    }
  }
})
