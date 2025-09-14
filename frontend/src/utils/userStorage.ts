/**
 * 用户隔离存储工具类
 * 实现逻辑多租户的数据隔离机制
 * 确保每个用户(租户)的数据完全独立
 */

/**
 * 获取当前登录用户ID
 */
function getCurrentUserId(): string | null {
  return localStorage.getItem('user_id')
}

/**
 * 用户隔离存储管理器
 * 实现多租户应用的数据隔离
 */
export class UserStorage {
  /**
   * 设置用户隔离数据
   * @param key 数据键名
   * @param value 数据值
   */
  static setUserData(key: string, value: string): void {
    const userId = getCurrentUserId()
    if (!userId) {
      console.warn('⚠️ 用户未登录，无法保存用户数据:', key)
      return
    }
    
    const userKey = `${key}_${userId}`
    localStorage.setItem(userKey, value)
    console.log(`✅ 保存用户数据: ${userKey}`)
  }

  /**
   * 获取用户隔离数据
   * @param key 数据键名
   * @returns 数据值或null
   */
  static getUserData(key: string): string | null {
    const userId = getCurrentUserId()
    if (!userId) {
      console.warn('⚠️ 用户未登录，无法获取用户数据:', key)
      return null
    }
    
    const userKey = `${key}_${userId}`
    return localStorage.getItem(userKey)
  }

  /**
   * 删除用户隔离数据
   * @param key 数据键名
   */
  static removeUserData(key: string): void {
    const userId = getCurrentUserId()
    if (!userId) {
      console.warn('⚠️ 用户未登录，无法删除用户数据:', key)
      return
    }
    
    const userKey = `${key}_${userId}`
    localStorage.removeItem(userKey)
    console.log(`🗑️ 删除用户数据: ${userKey}`)
  }

  /**
   * 设置全局共享数据（所有租户共享）
   * @param key 数据键名
   * @param value 数据值
   */
  static setGlobalData(key: string, value: string): void {
    localStorage.setItem(key, value)
    console.log(`🌍 保存全局数据: ${key}`)
  }

  /**
   * 获取全局共享数据
   * @param key 数据键名
   * @returns 数据值或null
   */
  static getGlobalData(key: string): string | null {
    return localStorage.getItem(key)
  }

  /**
   * 清除指定用户的所有数据
   * @param userId 用户ID（可选，默认为当前用户）
   */
  static clearUserData(userId?: string): void {
    const targetUserId = userId || getCurrentUserId()
    if (!targetUserId) {
      console.warn('⚠️ 无法确定要清除的用户ID')
      return
    }

    console.log(`🔄 开始清除用户 ${targetUserId} 的所有数据`)

    // 定义所有需要清除的用户隔离数据键名
    const userDataKeys = [
      'veritex_chat_history',
      'veritex_current_analysis',
      'paper_god_search_history', 
      'paper_god_chat_history',
      'paper_god_unified_history',
      'paper_god_user_settings'
    ]

    // 清除用户隔离数据
    userDataKeys.forEach(key => {
      const userKey = `${key}_${targetUserId}`
      localStorage.removeItem(userKey)
      console.log(`🗑️ 已清除: ${userKey}`)
    })

    console.log(`✅ 用户 ${targetUserId} 的数据清理完成`)
  }

  /**
   * 获取当前用户的所有数据键名
   * @returns 用户数据键名数组
   */
  static getUserDataKeys(): string[] {
    const userId = getCurrentUserId()
    if (!userId) return []

    const keys: string[] = []
    const suffix = `_${userId}`
    
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.endsWith(suffix)) {
        keys.push(key)
      }
    }
    
    return keys
  }

  /**
   * 检查当前用户是否有数据
   * @returns 是否有用户数据
   */
  static hasUserData(): boolean {
    return this.getUserDataKeys().length > 0
  }

  /**
   * 获取用户数据统计信息
   * @returns 数据统计对象
   */
  static getUserDataStats(): {
    userId: string | null
    dataCount: number
    totalSize: number
    keys: string[]
  } {
    const userId = getCurrentUserId()
    const keys = this.getUserDataKeys()
    
    let totalSize = 0
    keys.forEach(key => {
      const value = localStorage.getItem(key)
      if (value) {
        totalSize += value.length
      }
    })

    return {
      userId,
      dataCount: keys.length,
      totalSize,
      keys
    }
  }

  /**
   * 验证和清理关键词扩展数据
   * @param analysis 分析结果对象
   * @returns 清理后的分析结果或null
   */
  static validateKeywordAnalysis(analysis: any): any | null {
    if (!analysis || typeof analysis !== 'object') {
      console.warn('⚠️ 分析结果数据格式异常');
      return null;
    }

    // 检查hierarchical_keywords结构
    if (analysis.hierarchical_keywords && typeof analysis.hierarchical_keywords === 'object') {
      const validLevels = ['exact_terms', 'core_synonyms', 'related_terms', 'context_terms'];
      let hasValidKeywords = false;

      for (const level of validLevels) {
        const levelData = analysis.hierarchical_keywords[level];
        if (levelData && Array.isArray(levelData.terms) && levelData.terms.length > 0) {
          // 过滤掉空字符串和非字符串项
          levelData.terms = levelData.terms.filter((term: unknown) => 
            typeof term === 'string' && (term as string).trim().length > 0
          );
          
          if (levelData.terms.length > 0) {
            hasValidKeywords = true;
          }
        }
      }

      if (!hasValidKeywords) {
        console.warn('⚠️ 未找到有效的关键词数据');
        return null;
      }

      console.log('✅ 关键词数据验证通过');
      return analysis;
    }

    return null;
  }
}

/**
 * 数据迁移工具
 * 将现有的全局数据迁移为用户隔离数据
 */
export class DataMigration {
  /**
   * 迁移现有数据到用户隔离格式
   */
  static migrateToUserIsolation(): void {
    const userId = getCurrentUserId()
    if (!userId) {
      console.warn('⚠️ 用户未登录，无法进行数据迁移')
      return
    }

    console.log(`🔄 开始为用户 ${userId} 迁移数据`)

    // 需要迁移的数据映射
    const migrationMap = [
      { old: 'veritex_chat_history', new: 'veritex_chat_history' },
      { old: 'veritex_current_analysis', new: 'veritex_current_analysis' },
      { old: 'paper_god_search_history', new: 'paper_god_search_history' },
      { old: 'paper_god_chat_history', new: 'paper_god_chat_history' },
      { old: 'paper_god_unified_history', new: 'paper_god_unified_history' }
    ]

    migrationMap.forEach(({ old, new: newKey }) => {
      const oldData = localStorage.getItem(old)
      if (oldData) {
        UserStorage.setUserData(newKey, oldData)
        console.log(`📦 迁移数据: ${old} → ${newKey}_${userId}`)
        
        // 迁移完成后清除旧数据
        localStorage.removeItem(old)
        console.log(`🗑️ 清除旧数据: ${old}`)
      }
    })

    console.log(`✅ 用户 ${userId} 的数据迁移完成`)
  }

  /**
   * 检查是否需要数据迁移
   * @returns 是否需要迁移
   */
  static needsMigration(): boolean {
    // 检查是否存在旧格式的数据
    const oldDataKeys = [
      'veritex_chat_history',
      'veritex_current_analysis', 
      'paper_god_search_history',
      'paper_god_chat_history',
      'paper_god_unified_history'
    ]

    return oldDataKeys.some(key => localStorage.getItem(key) !== null)
  }

  /**
   * 自动迁移（如果需要的话）
   */
  static autoMigrate(): void {
    if (this.needsMigration()) {
      console.log('🔄 检测到旧格式数据，开始自动迁移')
      this.migrateToUserIsolation()
    }
  }
}

// 导出常用的数据键名常量
export const USER_DATA_KEYS = {
  CHAT_HISTORY: 'veritex_chat_history',
  CURRENT_ANALYSIS: 'veritex_current_analysis',
  SEARCH_HISTORY: 'paper_god_search_history',
  CHAT_HISTORY_UNIFIED: 'paper_god_chat_history',
  UNIFIED_HISTORY: 'paper_god_unified_history',
  USER_SETTINGS: 'paper_god_user_settings'
} as const

// 全局共享数据键名（所有租户共享）
export const GLOBAL_DATA_KEYS = {
  THEME: 'veritex_theme',
  LANGUAGE: 'veritex_language', 
  LLM_MODE: 'veritex_llm_mode'
} as const