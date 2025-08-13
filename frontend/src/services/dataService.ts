/**
 * 统一数据服务层
 * 整合Supabase云存储和localStorage本地存储
 * 实现自动降级机制确保数据不丢失
 */

import {
  saveSearchHistory as saveSearchToSupabase,
  getUserSearchHistory as getSearchFromSupabase,
  deleteSearchHistory as deleteSearchFromSupabase,
  saveChatHistory as saveChatToSupabase,
  getUserChatHistory as getChatFromSupabase,
  deleteChatHistory as deleteChatFromSupabase,
  saveUserSettings as saveSettingsToSupabase,
  getUserSettings as getSettingsFromSupabase,
  type SearchHistoryData,
  type ChatHistoryData,
  type UserSettings
} from '../supabaseClient'

// 本地存储键名
const STORAGE_KEYS = {
  SEARCH_HISTORY: 'paper_god_search_history',
  CHAT_HISTORY: 'paper_god_chat_history',
  UNIFIED_HISTORY: 'paper_god_unified_history',
  USER_SETTINGS: 'paper_god_user_settings'
}

// 搜索历史接口（兼容现有代码）
export interface SearchHistory {
  id: string
  timestamp: number
  originalQuery: string
  expandedKeywords: string[]
  papers: unknown[]
  maxResults: number
}

// 聊天历史接口（兼容现有代码）
export interface ChatHistory {
  id: string
  timestamp: number
  title: string
  messages: unknown[]
  lastActivity: number
}

// 统一历史记录接口
export interface HistoryItem {
  id: string
  timestamp: number
  type: 'search' | 'chat'
  title: string
  data: SearchHistory | ChatHistory
}

/**
 * 搜索历史服务
 */
export class SearchHistoryService {
  /**
   * 保存搜索历史（云端优先，本地降级）
   */
  static async save(userId: string, history: SearchHistory): Promise<void> {
    try {
      // 尝试保存到云端
      const supabaseData: SearchHistoryData = {
        searchId: history.id,
        userId,
        timestamp: new Date(history.timestamp).toISOString(),
        originalQuery: history.originalQuery,
        expandedKeywords: history.expandedKeywords,
        papers: history.papers,
        maxResults: history.maxResults
      }
      
      await saveSearchToSupabase(supabaseData)
      console.log('搜索历史已保存到云端')
    } catch (error) {
      console.warn('云端保存失败，降级到本地存储:', error)
      
      // 降级到本地存储
      const existingHistory = this.getLocalHistory()
      existingHistory.unshift(history)
      
      // 限制本地存储数量
      if (existingHistory.length > 100) {
        existingHistory.splice(100)
      }
      
      localStorage.setItem(STORAGE_KEYS.SEARCH_HISTORY, JSON.stringify(existingHistory))
    }
  }

  /**
   * 获取搜索历史（云端优先，本地降级）
   */
  static async getHistory(userId: string): Promise<SearchHistory[]> {
    try {
      // 尝试从云端获取
      const cloudData = await getSearchFromSupabase(userId)
      
      if (cloudData.length > 0) {
        console.log('从云端获取到搜索历史:', cloudData.length, '条')
        
        // 转换为本地格式
        return cloudData.map(item => ({
          id: item.searchId,
          timestamp: new Date(item.timestamp).getTime(),
          originalQuery: item.originalQuery,
          expandedKeywords: item.expandedKeywords,
          papers: item.papers,
          maxResults: item.maxResults
        }))
      }
    } catch (error) {
      console.warn('云端获取失败，使用本地存储:', error)
    }
    
    // 降级到本地存储
    return this.getLocalHistory()
  }

  /**
   * 删除搜索历史
   */
  static async deleteHistory(userId: string, ids: string[]): Promise<void> {
    try {
      // 尝试从云端删除
      await deleteSearchFromSupabase(userId, ids)
      console.log('云端搜索历史删除成功')
    } catch (error) {
      console.warn('云端删除失败:', error)
    }
    
    // 同时从本地删除
    const existingHistory = this.getLocalHistory()
    const filteredHistory = existingHistory.filter(item => !ids.includes(item.id))
    localStorage.setItem(STORAGE_KEYS.SEARCH_HISTORY, JSON.stringify(filteredHistory))
  }

  /**
   * 获取本地搜索历史
   */
  private static getLocalHistory(): SearchHistory[] {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.SEARCH_HISTORY) || '[]')
    } catch {
      return []
    }
  }
}

/**
 * 聊天历史服务
 */
export class ChatHistoryService {
  /**
   * 保存聊天历史（云端优先，本地降级）
   */
  static async save(userId: string, chat: ChatHistory): Promise<void> {
    try {
      // 尝试保存到云端
      const supabaseData: ChatHistoryData = {
        chatId: chat.id,
        userId,
        timestamp: new Date(chat.timestamp).toISOString(),
        title: chat.title,
        messages: chat.messages,
        lastActivity: new Date(chat.lastActivity).toISOString()
      }
      
      await saveChatToSupabase(supabaseData)
      console.log('聊天历史已保存到云端')
    } catch (error) {
      console.warn('云端保存失败，降级到本地存储:', error)
      
      // 降级到本地存储
      const existingHistory = this.getLocalHistory()
      const existingIndex = existingHistory.findIndex(item => item.id === chat.id)
      
      if (existingIndex >= 0) {
        existingHistory[existingIndex] = chat
      } else {
        existingHistory.unshift(chat)
      }
      
      // 限制本地存储数量
      if (existingHistory.length > 50) {
        existingHistory.splice(50)
      }
      
      localStorage.setItem(STORAGE_KEYS.CHAT_HISTORY, JSON.stringify(existingHistory))
    }
  }

  /**
   * 获取聊天历史（云端优先，本地降级）
   */
  static async getHistory(userId: string): Promise<ChatHistory[]> {
    try {
      // 尝试从云端获取
      const cloudData = await getChatFromSupabase(userId)
      
      if (cloudData.length > 0) {
        console.log('从云端获取到聊天历史:', cloudData.length, '条')
        
        // 转换为本地格式
        return cloudData.map(item => ({
          id: item.chatId,
          timestamp: new Date(item.timestamp).getTime(),
          title: item.title,
          messages: item.messages,
          lastActivity: new Date(item.lastActivity).getTime()
        }))
      }
    } catch (error) {
      console.warn('云端获取失败，使用本地存储:', error)
    }
    
    // 降级到本地存储
    return this.getLocalHistory()
  }

  /**
   * 删除聊天历史
   */
  static async deleteHistory(userId: string, ids: string[]): Promise<void> {
    try {
      // 尝试从云端删除
      await deleteChatFromSupabase(userId, ids)
      console.log('云端聊天历史删除成功')
    } catch (error) {
      console.warn('云端删除失败:', error)
    }
    
    // 同时从本地删除
    const existingHistory = this.getLocalHistory()
    const filteredHistory = existingHistory.filter(item => !ids.includes(item.id))
    localStorage.setItem(STORAGE_KEYS.CHAT_HISTORY, JSON.stringify(filteredHistory))
  }

  /**
   * 获取本地聊天历史
   */
  private static getLocalHistory(): ChatHistory[] {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.CHAT_HISTORY) || '[]')
    } catch {
      return []
    }
  }
}

/**
 * 用户设置服务
 */
export class UserSettingsService {
  /**
   * 保存用户设置（云端优先，本地降级）
   */
  static async save(userId: string, settings: UserSettings): Promise<void> {
    try {
      // 尝试保存到云端
      await saveSettingsToSupabase(userId, settings)
      console.log('用户设置已保存到云端')
    } catch (error) {
      console.warn('云端保存失败，使用本地存储:', error)
    }
    
    // 始终同步保存到本地（作为备份）
    localStorage.setItem(`${STORAGE_KEYS.USER_SETTINGS}_${userId}`, JSON.stringify(settings))
  }

  /**
   * 获取用户设置（云端优先，本地降级）
   */
  static async get(userId: string): Promise<UserSettings | null> {
    try {
      // 尝试从云端获取
      const cloudSettings = await getSettingsFromSupabase(userId)
      if (cloudSettings) {
        console.log('从云端获取用户设置')
        // 同步到本地作为缓存
        localStorage.setItem(`${STORAGE_KEYS.USER_SETTINGS}_${userId}`, JSON.stringify(cloudSettings))
        return cloudSettings
      }
    } catch (error) {
      console.warn('云端获取失败，使用本地存储:', error)
    }
    
    // 降级到本地存储
    try {
      const localSettings = localStorage.getItem(`${STORAGE_KEYS.USER_SETTINGS}_${userId}`)
      return localSettings ? JSON.parse(localSettings) : null
    } catch {
      return null
    }
  }
}

/**
 * 统一历史记录服务
 */
export class UnifiedHistoryService {
  /**
   * 获取统一历史记录（搜索+聊天）
   */
  static async getHistory(userId: string): Promise<HistoryItem[]> {
    const [searchHistory, chatHistory] = await Promise.all([
      SearchHistoryService.getHistory(userId),
      ChatHistoryService.getHistory(userId)
    ])
    
    const unifiedHistory: HistoryItem[] = [
      ...searchHistory.map(item => ({
        id: item.id,
        timestamp: item.timestamp,
        type: 'search' as const,
        title: item.originalQuery,
        data: item
      })),
      ...chatHistory.map(item => ({
        id: item.id,
        timestamp: item.lastActivity,
        type: 'chat' as const,
        title: item.title,
        data: item
      }))
    ]
    
    // 按时间排序
    return unifiedHistory.sort((a, b) => b.timestamp - a.timestamp)
  }

  /**
   * 删除统一历史记录
   */
  static async deleteHistory(userId: string, ids: string[]): Promise<void> {
    // 获取当前历史记录以确定类型
    const history = await this.getHistory(userId)
    
    const searchIds = ids.filter(id => 
      history.find(item => item.id === id && item.type === 'search')
    )
    const chatIds = ids.filter(id => 
      history.find(item => item.id === id && item.type === 'chat')
    )
    
    // 分别删除不同类型的记录
    const promises = []
    if (searchIds.length > 0) {
      promises.push(SearchHistoryService.deleteHistory(userId, searchIds))
    }
    if (chatIds.length > 0) {
      promises.push(ChatHistoryService.deleteHistory(userId, chatIds))
    }
    
    await Promise.all(promises)
  }

  /**
   * 清空所有历史记录
   */
  static async clearAll(userId: string): Promise<void> {
    try {
      // 获取所有记录ID
      const history = await this.getHistory(userId)
      const allIds = history.map(item => item.id)
      
      if (allIds.length > 0) {
        await this.deleteHistory(userId, allIds)
      }
      
      // 清空本地存储
      localStorage.removeItem(STORAGE_KEYS.SEARCH_HISTORY)
      localStorage.removeItem(STORAGE_KEYS.CHAT_HISTORY)
      localStorage.removeItem(STORAGE_KEYS.UNIFIED_HISTORY)
    } catch (error) {
      console.error('清空历史记录失败:', error)
    }
  }
}