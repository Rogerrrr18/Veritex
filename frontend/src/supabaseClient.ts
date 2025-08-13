/**
 * Supabase客户端配置
 * 用于内测码验证和用户数据管理
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js'

// Supabase配置 - 使用.env中的新配置
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://jfzchljmfnnsrszabpys.supabase.co'
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmemNobGptZm5uc3JzemFicHlzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI2NDcwOTksImV4cCI6MjA2ODIyMzA5OX0.E_soKX6nkQm5xb4bO-q_4NmR8Z7ajQOQSq5cGtO91-g'

// 创建Supabase客户端
export const supabase: SupabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// 内测码验证接口
export interface InviteCode {
  id: string
  code: string
  used: boolean
  created_at: string
  used_at?: string
  user_id?: string
}

// 用户数据接口
export interface UserData {
  id: string
  invite_code: string
  created_at: string
  last_active?: string
}

/**
 * 验证内测码是否有效
 */
export async function validateInviteCode(code: string): Promise<{
  success: boolean
  message?: string
  codeData?: InviteCode
}> {
  try {
    // 查询内测码是否存在且未使用
    const { data, error } = await supabase
      .from('invite_codes')
      .select('*')
      .eq('code', code)
      .eq('used', false)
      .single()

    if (error || !data) {
      return {
        success: false,
        message: '内测码无效或已被使用'
      }
    }

    return {
      success: true,
      message: '内测码验证成功',
      codeData: data
    }
  } catch (error) {
    console.error('验证内测码错误:', error)
    return {
      success: false,
      message: '验证失败，请稍后重试'
    }
  }
}

/**
 * 使用内测码创建用户
 */
export async function createUserWithInviteCode(code: string): Promise<{
  success: boolean
  message?: string
  userData?: UserData
}> {
  try {
    // 首先验证内测码
    const validation = await validateInviteCode(code)
    if (!validation.success || !validation.codeData) {
      return validation
    }

    // 生成用户ID
    const userId = `user_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`

    // 开始事务：创建用户并标记内测码为已使用
    const { data: userData, error: userError } = await supabase
      .from('users')
      .insert({
        id: userId,
        invite_code: code,
        created_at: new Date().toISOString()
      })
      .select()
      .single()

    if (userError) {
      console.error('创建用户失败:', userError)
      return {
        success: false,
        message: '创建用户失败'
      }
    }

    // 标记内测码为已使用
    const { error: updateError } = await supabase
      .from('invite_codes')
      .update({
        used: true,
        used_at: new Date().toISOString(),
        user_id: userId
      })
      .eq('code', code)

    if (updateError) {
      console.error('更新内测码状态失败:', updateError)
      // 这里可以考虑回滚用户创建，但为了简单起见先忽略
    }

    return {
      success: true,
      message: '注册成功！',
      userData: userData
    }
  } catch (error) {
    console.error('注册用户错误:', error)
    return {
      success: false,
      message: '注册失败，请稍后重试'
    }
  }
}

/**
 * 更新用户最后活跃时间
 */
export async function updateUserActivity(userId: string): Promise<void> {
  try {
    await supabase
      .from('users')
      .update({
        last_active: new Date().toISOString()
      })
      .eq('id', userId)
  } catch (error) {
    console.error('更新用户活跃时间失败:', error)
  }
}

/**
 * 记录用户行为日志
 */
export async function logUserAction(
  userId: string,
  action: string,
  payload?: unknown
): Promise<void> {
  try {
    await supabase
      .from('user_actions')
      .insert({
        user_id: userId,
        action: action,
        payload: payload ? JSON.stringify(payload) : null,
        created_at: new Date().toISOString()
      })
  } catch (error) {
    console.error('记录用户行为失败:', error)
  }
}

// ===== 搜索历史管理 =====

export interface SearchHistoryData {
  searchId: string
  userId: string
  timestamp: string
  originalQuery: string
  expandedKeywords: string[]
  papers: unknown[]
  maxResults: number
}

/**
 * 保存搜索历史到数据库
 */
export async function saveSearchHistory(data: SearchHistoryData): Promise<void> {
  try {
    await supabase
      .from('user_search_history')
      .insert({
        user_id: data.userId,
        search_id: data.searchId,
        timestamp: data.timestamp,
        original_query: data.originalQuery,
        expanded_keywords: data.expandedKeywords,
        papers: data.papers,
        max_results: data.maxResults
      })
  } catch (error) {
    console.error('保存搜索历史失败:', error)
    throw error
  }
}

/**
 * 获取用户搜索历史
 */
export async function getUserSearchHistory(userId: string): Promise<SearchHistoryData[]> {
  try {
    const { data, error } = await supabase
      .from('user_search_history')
      .select('*')
      .eq('user_id', userId)
      .order('timestamp', { ascending: false })
      .limit(50)

    if (error) throw error

    return data.map(item => ({
      searchId: item.search_id,
      userId: item.user_id,
      timestamp: item.timestamp,
      originalQuery: item.original_query,
      expandedKeywords: item.expanded_keywords,
      papers: item.papers,
      maxResults: item.max_results
    }))
  } catch (error) {
    console.error('获取搜索历史失败:', error)
    return []
  }
}

/**
 * 删除搜索历史
 */
export async function deleteSearchHistory(userId: string, searchIds: string[]): Promise<void> {
  try {
    await supabase
      .from('user_search_history')
      .delete()
      .eq('user_id', userId)
      .in('search_id', searchIds)
  } catch (error) {
    console.error('删除搜索历史失败:', error)
    throw error
  }
}

// ===== 聊天历史管理 =====

export interface ChatHistoryData {
  chatId: string
  userId: string
  timestamp: string
  title: string
  messages: unknown[]
  lastActivity: string
}

/**
 * 保存聊天历史到数据库
 */
export async function saveChatHistory(data: ChatHistoryData): Promise<void> {
  try {
    const { error } = await supabase
      .from('user_chat_history')
      .upsert({
        user_id: data.userId,
        chat_id: data.chatId,
        timestamp: data.timestamp,
        title: data.title,
        messages: data.messages,
        last_activity: data.lastActivity
      }, {
        onConflict: 'chat_id'
      })

    if (error) throw error
  } catch (error) {
    console.error('保存聊天历史失败:', error)
    throw error
  }
}

/**
 * 获取用户聊天历史
 */
export async function getUserChatHistory(userId: string): Promise<ChatHistoryData[]> {
  try {
    const { data, error } = await supabase
      .from('user_chat_history')
      .select('*')
      .eq('user_id', userId)
      .order('last_activity', { ascending: false })
      .limit(50)

    if (error) throw error

    return data.map(item => ({
      chatId: item.chat_id,
      userId: item.user_id,
      timestamp: item.timestamp,
      title: item.title,
      messages: item.messages,
      lastActivity: item.last_activity
    }))
  } catch (error) {
    console.error('获取聊天历史失败:', error)
    return []
  }
}

/**
 * 删除聊天历史
 */
export async function deleteChatHistory(userId: string, chatIds: string[]): Promise<void> {
  try {
    await supabase
      .from('user_chat_history')
      .delete()
      .eq('user_id', userId)
      .in('chat_id', chatIds)
  } catch (error) {
    console.error('删除聊天历史失败:', error)
    throw error
  }
}

// ===== 用户设置管理 =====

export interface UserSettings {
  theme: 'light' | 'dark'
  language: 'zh' | 'en'
  settings: Record<string, unknown>
}

/**
 * 保存用户设置
 */
export async function saveUserSettings(userId: string, settings: UserSettings): Promise<void> {
  try {
    await supabase
      .from('user_settings')
      .upsert({
        user_id: userId,
        theme: settings.theme,
        language: settings.language,
        settings: settings.settings,
        updated_at: new Date().toISOString()
      }, {
        onConflict: 'user_id'
      })
  } catch (error) {
    console.error('保存用户设置失败:', error)
    throw error
  }
}

/**
 * 获取用户设置
 */
export async function getUserSettings(userId: string): Promise<UserSettings | null> {
  try {
    const { data, error } = await supabase
      .from('user_settings')
      .select('*')
      .eq('user_id', userId)
      .single()

    if (error && error.code !== 'PGRST116') { // PGRST116 = no rows returned
      throw error
    }

    if (!data) return null

    return {
      theme: data.theme,
      language: data.language,
      settings: data.settings
    }
  } catch (error) {
    console.error('获取用户设置失败:', error)
    return null
  }
}