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
 * 基于内测码生成固定的用户ID
 * 确保同一内测码始终对应同一用户ID
 */
export function generateUserIdFromInviteCode(inviteCode: string): string {
  // 使用base64编码内测码，然后截取前8位作为hash
  const hash = btoa(inviteCode).replace(/[^a-zA-Z0-9]/g, '').slice(0, 8)
  const suffix = inviteCode.slice(-4)
  return `user_${hash}_${suffix}`
}

/**
 * 检查内测码是否已有对应的用户
 */
export async function getUserByInviteCode(code: string): Promise<{
  success: boolean
  message?: string
  userData?: UserData
  exists: boolean
}> {
  try {
    // 从内测码表获取预设的用户ID
    const { data: inviteData, error: inviteError } = await supabase
      .from('invite_codes')
      .select('user_id, used, used_at')
      .eq('code', code)
      .single()

    if (inviteError || !inviteData) {
      return {
        success: false,
        message: '内测码无效',
        exists: false
      }
    }

    const fixedUserId = inviteData.user_id

    // 检查用户是否已存在
    const { data: userData, error: userError } = await supabase
      .from('users')
      .select('*')
      .eq('id', fixedUserId)
      .single()

    if (userError && userError.code !== 'PGRST116') {
      console.error('查询用户失败:', userError)
      return {
        success: false,
        message: '查询用户失败',
        exists: false
      }
    }

    if (userData) {
      // 用户已存在，直接返回
      return {
        success: true,
        message: '欢迎回来！',
        userData: userData,
        exists: true
      }
    } else {
      // 用户不存在，返回需要创建
      return {
        success: true,
        message: '内测码有效',
        exists: false
      }
    }
  } catch (error) {
    console.error('检查用户存在性错误:', error)
    return {
      success: false,
      message: '检查失败，请稍后重试',
      exists: false
    }
  }
}

/**
 * 使用内测码创建用户或登录现有用户
 * 🔧 修复：确保一个内测码对应一个固定的用户ID
 */
export async function createUserWithInviteCode(code: string): Promise<{
  success: boolean
  message?: string
  userData?: UserData
}> {
  try {
    console.log('🔐 [Supabase] 开始处理内测码:', code)

    // 首先检查用户是否已存在
    const userCheck = await getUserByInviteCode(code)
    if (!userCheck.success) {
      return userCheck
    }

    if (userCheck.exists && userCheck.userData) {
      // 用户已存在，直接返回
      console.log('✅ [Supabase] 用户已存在，直接登录:', userCheck.userData.id)
      return {
        success: true,
        message: '欢迎回来！',
        userData: userCheck.userData
      }
    }

    // 用户不存在，需要创建新用户
    console.log('🆕 [Supabase] 需要创建新用户')

    // 从内测码表获取预设的用户ID
    const { data: inviteData, error: inviteError } = await supabase
      .from('invite_codes')
      .select('user_id, used')
      .eq('code', code)
      .single()

    if (inviteError || !inviteData) {
      console.error('❌ [Supabase] 获取内测码信息失败:', inviteError)
      return {
        success: false,
        message: '内测码无效'
      }
    }

    if (inviteData.used) {
      // 内测码已被使用，但用户不存在，这是异常情况
      console.warn('⚠️ [Supabase] 内测码已被使用但用户不存在，尝试恢复')
    }

    const fixedUserId = inviteData.user_id
    console.log('🆔 [Supabase] 使用固定用户ID:', fixedUserId)

    // 创建用户
    const { data: userData, error: userError } = await supabase
      .from('users')
      .insert({
        id: fixedUserId,
        invite_code: code,
        created_at: new Date().toISOString()
      })
      .select()
      .single()

    if (userError) {
      console.error('❌ [Supabase] 创建用户失败:', userError)
      
      // 如果是重复键错误，说明用户已存在，直接查询返回
      if (userError.code === '23505') {
        const { data: existingUser, error: queryError } = await supabase
          .from('users')
          .select('*')
          .eq('id', fixedUserId)
          .single()

        if (existingUser && !queryError) {
          console.log('✅ [Supabase] 用户已存在，返回现有用户:', existingUser.id)
          return {
            success: true,
            message: '欢迎回来！',
            userData: existingUser
          }
        }
      }

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
        used_at: new Date().toISOString()
      })
      .eq('code', code)

    if (updateError) {
      console.error('⚠️ [Supabase] 更新内测码状态失败:', updateError)
      // 不影响用户创建成功
    }

    console.log('✅ [Supabase] 用户创建成功:', userData.id)
    return {
      success: true,
      message: '注册成功！',
      userData: userData
    }
  } catch (error) {
    console.error('❌ [Supabase] 处理内测码错误:', error)
    return {
      success: false,
      message: '处理失败，请稍后重试'
    }
  }
}

/**
 * 设置当前用户上下文（用于RLS策略）
 * 🔧 修复：使用与后端SQL一致的配置项名称
 */
export async function setCurrentUserContext(userId: string): Promise<void> {
  try {
    console.log(`🔐 [前端] 设置用户上下文: ${userId}`)
    // 🔧 修复：调用后端定义的set_user_context函数，确保与RLS策略匹配
    const { error } = await supabase.rpc('set_user_context', {
      target_user_id: userId  // 使用与后端supabase_sync.py一致的参数名
    })
    
    if (error) {
      console.error('❌ [前端] 用户上下文设置失败:', error)
      throw error
    } else {
      console.log(`✅ [前端] 用户上下文设置成功: ${userId}`)
    }
  } catch (error) {
    console.error('❌ [前端] 设置用户上下文异常:', error)
    // 不抛出异常，允许应用继续运行（降级处理）
  }
}

/**
 * 清除用户上下文
 */
export async function clearUserContext(): Promise<void> {
  try {
    console.log('🗑️ [前端] 清除用户上下文')
    // 🔧 修复：调用set_user_context函数并传递空字符串清除上下文
    const { error } = await supabase.rpc('set_user_context', {
      target_user_id: ''
    })
    
    if (error) {
      console.error('❌ [前端] 清除用户上下文失败:', error)
    } else {
      console.log('✅ [前端] 用户上下文已清除')
    }
  } catch (error) {
    console.error('❌ [前端] 清除用户上下文异常:', error)
  }
}

/**
 * 更新用户最后活跃时间
 * 🔧 增强错误处理和调试日志
 */
export async function updateUserActivity(userId: string): Promise<void> {
  try {
    console.log(`🔄 [前端] 更新用户活跃时间: ${userId}`)
    
    // 先设置用户上下文
    await setCurrentUserContext(userId)
    
    const { error } = await supabase
      .from('users')
      .update({
        last_active: new Date().toISOString()
      })
      .eq('id', userId)
    
    if (error) {
      console.error('❌ [前端] 更新用户活跃时间失败:', error)
      throw error
    } else {
      console.log(`✅ [前端] 用户活跃时间已更新: ${userId}`)
    }
  } catch (error) {
    console.error('❌ [前端] 更新用户活跃时间异常:', error)
    throw error
  }
}

/**
 * 记录用户行为日志
 * 🔧 修复：增强错误处理、调试日志和数据验证
 */
export async function logUserAction(
  userId: string,
  action: string,
  payload?: unknown
): Promise<void> {
  try {
    console.log(`📝 [前端] 记录用户行为: ${userId} -> ${action}`)
    
    // 先设置用户上下文，确保RLS策略正确工作
    await setCurrentUserContext(userId)
    
    // 准备插入数据
    const insertData = {
      user_id: userId,
      action: action,
      payload: payload ? (typeof payload === 'string' ? payload : JSON.stringify(payload)) : null,
      created_at: new Date().toISOString()
    }
    
    console.log('📊 [前端] 插入数据:', insertData)
    
    const { error } = await supabase
      .from('user_actions')
      .insert(insertData)
    
    if (error) {
      console.error('❌ [前端] 记录用户行为失败:', error)
      console.error('❌ [前端] 插入数据详情:', insertData)
      throw error
    } else {
      console.log(`✅ [前端] 用户行为已记录: ${userId} -> ${action}`)
    }
  } catch (error) {
    console.error('❌ [前端] 记录用户行为异常:', error)
    console.error('❌ [前端] 用户ID:', userId, '行为:', action, 'Payload:', payload)
    throw error
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
    // 先设置用户上下文
    await setCurrentUserContext(data.userId)
    
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
    // 先设置用户上下文
    await setCurrentUserContext(userId)
    
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
    // 先设置用户上下文
    await setCurrentUserContext(userId)
    
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
    // 先设置用户上下文
    await setCurrentUserContext(data.userId)
    
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
    // 先设置用户上下文
    await setCurrentUserContext(userId)
    
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
    // 先设置用户上下文
    await setCurrentUserContext(userId)
    
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
    // 先设置用户上下文
    await setCurrentUserContext(userId)
    
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
    // 先设置用户上下文
    await setCurrentUserContext(userId)
    
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