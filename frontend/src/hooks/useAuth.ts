/**
 * 统一的认证状态管理Hook
 * 确保所有组件都能正确检查用户登录状态
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

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

  // 检查认证状态
  const checkAuthStatus = () => {
    const isLoggedIn = localStorage.getItem('invite_logged_in') === '1'
    const userId = localStorage.getItem('user_id')
    
    setAuthState({
      isLoggedIn: isLoggedIn && !!userId,
      userId: userId,
      isLoading: false
    })
    
    return isLoggedIn && !!userId
  }

  // 强制登录检查 - 如果未登录，自动跳转到invite页面
  const requireAuth = () => {
    const isValid = checkAuthStatus()
    if (!isValid) {
      // 清除无效的认证信息
      localStorage.removeItem('invite_logged_in')
      localStorage.removeItem('user_id')
      navigate('/invite')
      return false
    }
    return true
  }

  // 登出
  const logout = () => {
    localStorage.removeItem('invite_logged_in')
    localStorage.removeItem('user_id')
    // 可选：清除其他用户相关的本地数据
    // localStorage.removeItem('veritex_theme')
    // localStorage.removeItem('veritex_language')
    setAuthState({
      isLoggedIn: false,
      userId: null,
      isLoading: false
    })
    navigate('/invite')
  }

  // 组件挂载时检查认证状态
  useEffect(() => {
    checkAuthStatus()
  }, [])

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