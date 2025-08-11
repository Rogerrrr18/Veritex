/**
 * 前端配置文件 - Paper God
 * 用于配置API端点和其他设置
 */

// API配置
export const API_CONFIG = {
  // 优化后端（推荐使用）- 端口8001
  OPTIMIZED_BASE_URL: 'http://localhost:8001',
  
  // 原版后端 - 端口8000  
  ORIGINAL_BASE_URL: 'http://localhost:8000',
  
  // 当前使用的后端 - 开发环境使用相对路径（通过Vite代理）
  BASE_URL: '',  // 空字符串表示使用相对路径，由Vite代理处理
  
  // API端点
  ENDPOINTS: {
    CHAT: '/chat',
    SEARCH_PAPERS: '/search_papers',
    EXPAND_KEYWORDS: '/expand_keywords',
    MULTI_SOURCE_SEARCH: '/multi_source_search',
    ANALYZE_DISCIPLINE: '/analyze_discipline',
    PERFORMANCE: '/performance',
    HEALTH: '/health'
  },
  
  // 请求配置
  REQUEST_TIMEOUT: 30000,  // 30秒超时
  RETRY_COUNT: 2,
}

// 应用配置
export const APP_CONFIG = {
  // 搜索配置
  DEFAULT_MAX_RESULTS: 20,
  MAX_SEARCH_RESULTS: 500,
  DEFAULT_MAX_KEYWORDS: 5,
  
  // UI配置
  ABSTRACT_PREVIEW_LENGTH: 120,
  ANIMATION_DELAY: 100,
  
  // 缓存配置
  CACHE_DURATION: 5 * 60 * 1000,  // 5分钟
}

// 开发模式配置
export const DEV_CONFIG = {
  ENABLE_DEBUG_LOGS: true,
  SHOW_PERFORMANCE_METRICS: true,
  MOCK_API_DELAY: 0,  // 模拟API延迟（毫秒）
}

// 导出API调用函数
export const apiCall = async (endpoint: string, data: any, method: 'GET' | 'POST' = 'POST') => {
  const url = `${API_CONFIG.BASE_URL}${endpoint}`
  
  const config: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    signal: AbortSignal.timeout(API_CONFIG.REQUEST_TIMEOUT)
  }
  
  if (method === 'POST' && data) {
    config.body = JSON.stringify(data)
  }
  
  if (DEV_CONFIG.ENABLE_DEBUG_LOGS) {
    console.log(`[API] ${method} ${url}`, data)
  }
  
  try {
    const response = await fetch(url, config)
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ 
        detail: `HTTP ${response.status}: ${response.statusText}` 
      }))
      throw new Error(errorData.detail || `请求失败: ${response.status}`)
    }
    
    const result = await response.json()
    
    if (DEV_CONFIG.ENABLE_DEBUG_LOGS) {
      console.log(`[API] ${method} ${url} - 响应:`, result)
    }
    
    return result
  } catch (error: any) {
    if (error.name === 'TimeoutError') {
      throw new Error('请求超时，请稍后重试')
    }
    throw error
  }
}

// 便捷的API调用方法
export const api = {
  chat: (message: string, history: any[] = []) => 
    apiCall(API_CONFIG.ENDPOINTS.CHAT, { message, history }),
    
  searchPapers: (query: string, maxResults: number = 20, enableExpansion: boolean = true) =>
    apiCall(API_CONFIG.ENDPOINTS.SEARCH_PAPERS, { query, max_results: maxResults, enable_expansion: enableExpansion }),
    
  multiSourceSearch: (query: string, maxResults: number = 50, sources?: string[]) =>
    apiCall(API_CONFIG.ENDPOINTS.MULTI_SOURCE_SEARCH, { query, max_results: maxResults, sources }),
    
  analyzeDiscipline: (query: string) =>
    apiCall(API_CONFIG.ENDPOINTS.ANALYZE_DISCIPLINE, { query }),
    
  getPerformance: () =>
    apiCall(API_CONFIG.ENDPOINTS.PERFORMANCE, {}, 'GET'),
    
  getHealth: () =>
    apiCall(API_CONFIG.ENDPOINTS.HEALTH, {}, 'GET')
}
// 切换后端的辅助函数
export const switchBackend = (useOptimized: boolean = true) => {
  API_CONFIG.BASE_URL = useOptimized 
    ? API_CONFIG.OPTIMIZED_BASE_URL 
    : API_CONFIG.ORIGINAL_BASE_URL
    
  console.log(`[配置] 已切换到${useOptimized ? '优化' : '原版'}后端: ${API_CONFIG.BASE_URL}`)
}
