import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    historyApiFallback: true,
    proxy: {
      // 代理到后端（端口8000）
      '/chat': 'http://localhost:8000',
      '/expand_keywords': 'http://localhost:8000',
      '/search_papers': 'http://localhost:8000',
      '/multi_source_search': 'http://localhost:8000',
      '/analyze_discipline': 'http://localhost:8000',
      '/batch_expand': 'http://localhost:8000',
      '/performance': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/clear_cache': 'http://localhost:8000',
      '/analytics': 'http://localhost:8000',
    }
  }
})
