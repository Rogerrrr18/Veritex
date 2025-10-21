/**
 * 统一的认证状态管理Hook
 * 确保所有组件都能正确检查用户登录状态
 * 🔐 增强多租户数据隔离机制
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserStorage } from '../utils/userStorage'
import { setCurrentUserContext, clearUserContext } from '../supabaseClient'

export interface AuthState {
  isLoggedIn: boolean
  userId: string | null
  isLoading: boolean
}

export function useAuth() {
  const navigate = useNavigate()
  const [authState, setAuthState] = useState<AuthState>({
    isLoggedIn: false,
    userId: null,
    isLoading: true
  })
  
  // 🔐 用户切换检测状态
  const [previousUserId, setPreviousUserId] = useState<string | null>(null)

  // 检查认证状态
  const checkAuthStatus = async () => {
    const isLoggedIn = localStorage.getItem('invite_logged_in') === '1'
    const userId = localStorage.getItem('user_id')
    
    const isValidAuth = isLoggedIn && !!userId
    
    setAuthState({
      isLoggedIn: isValidAuth,
      userId: userId,
      isLoading: false
    })
    
    // 🔐 设置或清除Supabase用户上下文
    if (isValidAuth && userId) {
      await setCurrentUserContext(userId)
      console.log(`🔐 已设置Supabase用户上下文: ${userId}`)
    } else {
      await clearUserContext()
      console.log('🗑️ 已清除Supabase用户上下文')
    }
    
    return isValidAuth
  }

  // 强制登录检查 - 如果未登录，自动跳转到invite页面
  const requireAuth = async () => {
    const isValid = await checkAuthStatus()
    if (!isValid) {
      // 清除无效的认证信息
      localStorage.removeItem('invite_logged_in')
      localStorage.removeItem('user_id')
      await clearUserContext()
      navigate('/invite')
      return false
    }
    return true
  }

  // 🔐 增强的多租户安全登出
  const logout = async () => {
    const currentUserId = localStorage.getItem('user_id')
    console.log('🚪 多租户用户登出，清理所有数据 for user:', currentUserId)
    
    // 🔐 清除当前用户的所有隔离数据
    if (currentUserId) {
      UserStorage.clearUserData(currentUserId)
    }
    
    // 🔐 清除认证状态
    localStorage.removeItem('invite_logged_in')
    localStorage.removeItem('user_id')
    
    // 🔐 清除Supabase用户上下文
    await clearUserContext()
    
    // 🌍 保留全局共享数据（主题、语言、LLM模式等）
    // veritex_theme, veritex_language, veritex_llm_mode 保持不变
    
    setAuthState({
      isLoggedIn: false,
      userId: null,
      isLoading: false
    })
    
    console.log('✅ 多租户用户数据清理完成，跳转到登录页')
    navigate('/invite')
  }

  // 组件挂载时检查认证状态
  useEffect(() => {
    checkAuthStatus()
  }, [])

  // 🔐 用户切换检测：监听用户ID变化，清理前用户数据
  useEffect(() => {
    const currentUserId = localStorage.getItem('user_id')
    
    // 如果检测到用户ID变化（用户切换）
    if (previousUserId && currentUserId && previousUserId !== currentUserId) {
      console.log(`🔄 检测到用户切换: ${previousUserId} → ${currentUserId}`)
      
      // 清理前一个用户的数据
      UserStorage.clearUserData(previousUserId)
      console.log(`🗑️ 已清理前用户 ${previousUserId} 的数据`)
    }
    
    // 更新previousUserId状态
    setPreviousUserId(currentUserId)
  }, [authState.userId, previousUserId])

  // 监听localStorage变化（支持多标签页同步）
  useEffect(() => {
    const handleStorageChange = () => {
      checkAuthStatus()
    }
    
    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [])

  return {
    ...authState,
    requireAuth,
    logout,
    checkAuthStatus
  }
}