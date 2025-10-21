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
    
    try {
      // 检查数据大小，如果超过限制则进行优化
      const maxSize = 2 * 1024 * 1024; // 2MB限制
      
      if (value.length >= maxSize) {
        console.warn(`⚠️ 数据过大 (${Math.round(value.length / 1024)}KB)，尝试压缩存储`);
        
        // 特殊处理统一历史数据
        if (key === USER_DATA_KEYS.UNIFIED_HISTORY) {
          this.setLargeUnifiedHistory(userKey, value);
          return;
        }
        
        // 其他大数据的压缩处理
        const compressedValue = this.compressData(value);
        if (compressedValue.length < maxSize) {
          localStorage.setItem(userKey, compressedValue);
          console.log(`✅ 压缩后保存用户数据: ${userKey} (${Math.round(compressedValue.length / 1024)}KB)`);
          return;
        }
        
        // 如果压缩后仍然过大，只保留最近的数据
        console.warn('⚠️ 数据仍然过大，只保留最近数据');
        const truncatedValue = this.truncateData(value, key);
        localStorage.setItem(userKey, truncatedValue);
        console.log(`⚠️ 截断保存用户数据: ${userKey}`);
        return;
      }
      
      // 正常大小，直接存储
      localStorage.setItem(userKey, value);
      console.log(`✅ 保存用户数据: ${userKey}`);
      
    } catch (error) {
      console.error(`❌ 保存用户数据失败: ${userKey}`, error);
      
      // 降级处理：尝试只保存最重要的数据
      try {
        const fallbackValue = this.createFallbackData(value, key);
        localStorage.setItem(userKey, fallbackValue);
        console.warn(`⚠️ 降级保存用户数据: ${userKey}`);
      } catch (fallbackError) {
        console.error(`❌ 降级保存也失败: ${userKey}`, fallbackError);
      }
    }
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
    
    // 如果是统一历史数据，尝试读取分页数据
    if (key === USER_DATA_KEYS.UNIFIED_HISTORY) {
      const result = this.getLargeUnifiedHistory(userKey);
      if (result) {
        return result;
      }
    }
    
    return localStorage.getItem(userKey)
  }

  /**
   * 处理大型统一历史数据的存储
   */
  private static setLargeUnifiedHistory(userKey: string, value: string): void {
    try {
      const history = JSON.parse(value);
      const maxSize = 1.5 * 1024 * 1024; // 1.5MB限制，留出安全边距
      
      // 先清理旧的分页数据
      this.clearPagedHistory(userKey);
      
      // 尝试直接存储
      if (value.length < maxSize) {
        localStorage.setItem(userKey, value);
        return;
      }
      
      // 数据过大，进行分页存储
      console.log(`📦 统一历史数据过大，进行分页存储 (${Math.round(value.length / 1024)}KB)`);
      
      // 压缩历史数据
      const compressedHistory = this.compressHistoryData(history);
      
      // 计算每页条目数
      const avgItemSize = value.length / history.length;
      const itemsPerPage = Math.floor(maxSize / avgItemSize) - 1; // 留出安全边距
      
      // 分页存储
      for (let i = 0; i < compressedHistory.length; i += itemsPerPage) {
        const page = compressedHistory.slice(i, i + itemsPerPage);
        const pageKey = `${userKey}_page_${Math.floor(i / itemsPerPage)}`;
        
        try {
          localStorage.setItem(pageKey, JSON.stringify(page));
          console.log(`✅ 保存分页 ${Math.floor(i / itemsPerPage)}: ${page.length} 条记录`);
        } catch (error) {
          console.error(`❌ 保存分页失败: ${pageKey}`, error);
          break;
        }
      }
      
    } catch (error) {
      console.error('处理大型统一历史数据失败:', error);
      // 降级：只保存最近的记录
      try {
        const recentHistory = JSON.parse(value).slice(0, 20);
        localStorage.setItem(userKey, JSON.stringify(recentHistory));
        console.warn('⚠️ 降级保存最近20条历史记录');
      } catch (e) {
        console.error('降级保存也失败:', e);
      }
    }
  }

  /**
   * 读取大型统一历史数据
   */
  private static getLargeUnifiedHistory(userKey: string): string | null {
    // 首先尝试读取主数据
    const mainData = localStorage.getItem(userKey);
    if (mainData) {
      return mainData;
    }
    
    // 尝试读取分页数据
    const allHistory: any[] = [];
    let pageIndex = 0;
    let hasMore = true;
    
    while (hasMore) {
      const pageKey = `${userKey}_page_${pageIndex}`;
      const pageData = localStorage.getItem(pageKey);
      
      if (pageData) {
        try {
          const pageHistory = JSON.parse(pageData);
          allHistory.push(...pageHistory);
          pageIndex++;
        } catch (error) {
          console.error(`读取分页 ${pageIndex} 失败:`, error);
          hasMore = false;
        }
      } else {
        hasMore = false;
      }
    }
    
    return allHistory.length > 0 ? JSON.stringify(allHistory) : null;
  }

  /**
   * 压缩历史数据
   */
  private static compressHistoryData(history: any[]): any[] {
    return history.map(item => {
      // 压缩搜索结果数据
      if (item.type === 'search' && item.data && item.data.papers) {
        return {
          ...item,
          data: {
            ...item.data,
            papers: item.data.papers.map((paper: any) => ({
              title: paper.title || '',
              authors: paper.authors || '',
              year: paper.year || '',
              citations: paper.citations || 0,
              abstract: paper.abstract ? paper.abstract.slice(0, 200) + '...' : '', // 截断摘要
              url: paper.url || ''
            }))
          }
        };
      }
      
      // 压缩聊天数据
      if (item.type === 'chat' && item.data && item.data.messages) {
        return {
          ...item,
          data: {
            ...item.data,
            messages: item.data.messages.slice(-20) // 只保留最近20条消息
          }
        };
      }
      
      return item;
    });
  }

  /**
   * 清理分页历史数据
   */
  private static clearPagedHistory(userKey: string): void {
    let pageIndex = 0;
    let hasMore = true;
    
    while (hasMore) {
      const pageKey = `${userKey}_page_${pageIndex}`;
      if (localStorage.getItem(pageKey)) {
        localStorage.removeItem(pageKey);
        pageIndex++;
      } else {
        hasMore = false;
      }
    }
  }

  /**
   * 通用数据压缩
   */
  private static compressData(data: string): string {
    try {
      const parsed = JSON.parse(data);
      
      // 如果是数组，只保留最近的数据
      if (Array.isArray(parsed)) {
        const compressed = parsed.slice(0, 50); // 只保留50条
        return JSON.stringify(compressed);
      }
      
      return data;
    } catch (error) {
      console.error('数据压缩失败:', error);
      return data.slice(0, 1024 * 1024); // 截断到1MB
    }
  }

  /**
   * 截断数据
   */
  private static truncateData(data: string, key: string): string {
    try {
      const parsed = JSON.parse(data);
      
      if (Array.isArray(parsed)) {
        // 根据不同类型的数据采用不同的截断策略
        let maxItems = 10;
        if (key.includes('history')) maxItems = 20;
        if (key.includes('search')) maxItems = 15;
        
        return JSON.stringify(parsed.slice(0, maxItems));
      }
      
      return JSON.stringify(parsed);
    } catch (error) {
      return data.slice(0, 500 * 1024); // 截断到500KB
    }
  }

  /**
   * 创建降级数据
   */
  private static createFallbackData(data: string, _key: string): string {
    try {
      const parsed = JSON.parse(data);
      
      if (Array.isArray(parsed)) {
        // 只保留最重要的几条记录
        return JSON.stringify(parsed.slice(0, 5));
      }
      
      // 对象类型的数据，只保留关键字段
      const essential = {
        id: parsed.id,
        timestamp: parsed.timestamp || Date.now(),
        title: parsed.title || '数据过大已压缩',
        type: parsed.type
      };
      
      return JSON.stringify(essential);
    } catch (error) {
      // 最后的降级方案
      return JSON.stringify({
        error: 'Data too large',
        timestamp: Date.now(),
        originalSize: data.length
      });
    }
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

    // 检查hierarchical_keywords结构（兼容 terms 与 chinese/english 双格式）
    if (analysis.hierarchical_keywords && typeof analysis.hierarchical_keywords === 'object') {
      const validLevels = ['exact_terms', 'core_synonyms', 'related_terms', 'context_terms'];
      let hasValidKeywords = false;

      for (const level of validLevels) {
        const levelData = analysis.hierarchical_keywords[level];
        if (!levelData || typeof levelData !== 'object') continue;

        // 兼容新格式：如果没有terms，但有chinese/english，则合并为terms（去重保持顺序）
        if (!Array.isArray(levelData.terms)) {
          const zh = Array.isArray(levelData.chinese) ? levelData.chinese : [];
          const en = Array.isArray(levelData.english) ? levelData.english : [];
          const merged = [...zh, ...en].filter((t) => typeof t === 'string' && t.trim().length > 0);
          if (merged.length > 0) {
            // 去重保持顺序
            const unique = Array.from(new Set(merged.map((t) => t.trim())));
            levelData.terms = unique;
          }
        }

        if (Array.isArray(levelData.terms) && levelData.terms.length > 0) {
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
  USER_SETTINGS: 'paper_god_user_settings',
  KEYWORD_CLOUD: 'keyword_cloud_data' // 🔑 关键词云数据存储键
} as const

// 全局共享数据键名（所有租户共享）
export const GLOBAL_DATA_KEYS = {
  THEME: 'veritex_theme',
  LANGUAGE: 'veritex_language', 
  LLM_MODE: 'veritex_llm_mode'
} as const
