/**
 * 保护路由组件
 * 确保只有已认证用户才能访问特定页面
 */

import React, { useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'

interface ProtectedRouteProps {
  children: React.ReactNode
  fallback?: React.ReactNode
}

export function ProtectedRoute({ children, fallback }: ProtectedRouteProps) {
  const { isLoggedIn, isLoading, requireAuth } = useAuth()

  useEffect(() => {
    if (!isLoading && !isLoggedIn) {
      requireAuth() // 这将自动跳转到invite页面
    }
  }, [isLoggedIn, isLoading, requireAuth])

  // 显示加载状态
  if (isLoading) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        background: '#000', 
        color: '#fff', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        fontSize: '18px'
      }}>
        验证登录状态...
      </div>
    )
  }

  // 未登录显示fallback或空内容
  if (!isLoggedIn) {
    return fallback ? <>{fallback}</> : null
  }

  // 已登录，渲染子组件
  return <>{children}</>
}

// 简化的加载组件
export function AuthLoadingSpinner() {
  return (
    <div style={{ 
      minHeight: '100vh', 
      background: '#000', 
      color: '#fff', 
      display: 'flex', 
      flexDirection: 'column',
      alignItems: 'center', 
      justifyContent: 'center',
      gap: '16px'
    }}>
      <div style={{
        width: '40px',
        height: '40px',
        border: '3px solid #333',
        borderTop: '3px solid #3bb0e6',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite'
      }} />
      <div style={{ fontSize: '16px', color: '#a1a1aa' }}>
        正在验证内测权限...
      </div>
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}