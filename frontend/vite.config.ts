import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      proxy: {
        // 默认代理到后端8000；本地端口冲突时可在 frontend/.env 中设置 VITE_BACKEND_URL
        '/chat': backendUrl,
        '/expand_keywords': backendUrl,
        '/search_papers': backendUrl,
        '/multi_source_search': backendUrl,
        '/analyze_discipline': backendUrl,
        '/batch_expand': backendUrl,
        '/performance': backendUrl,
        '/health': backendUrl,
        '/clear_cache': backendUrl,
        '/analytics': backendUrl,
      }
    }
  }
})
