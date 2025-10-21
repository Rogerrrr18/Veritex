// 整合Supabase的用户认证与行为日志模块
import { createUserWithInviteCode, updateUserActivity, logUserAction as logToSupabase } from './supabaseClient'

export interface RegisterResult {
  success: boolean;
  userData?: { id: string };
  error?: string;
}

// 邀请码注册 - 完全基于Supabase验证，确保内测码与用户ID一对一映射
export async function registerUser(inviteCode: string): Promise<RegisterResult> {
  console.log('🔐 [Auth] 开始验证内测码:', inviteCode);
  
  if (!inviteCode || inviteCode.trim().length === 0) {
    return { success: false, error: '请输入内测码' };
  }

  const trimmedCode = inviteCode.trim().toUpperCase();
  console.log('🔤 [Auth] 处理后的内测码:', trimmedCode);

  // 验证内测码格式 - 必须是6位英文字母
  if (!/^[A-Z]{6}$/.test(trimmedCode)) {
    return { 
      success: false, 
      error: '内测码格式不正确，请输入6位英文字母' 
    };
  }

  try {
    // 通过Supabase验证内测码并获取或创建用户
    console.log('📡 [Auth] 开始Supabase验证...');
    const supabaseResult = await createUserWithInviteCode(trimmedCode);
    console.log('✅ [Auth] Supabase验证结果:', supabaseResult.success ? '成功' : '失败');
    
    if (supabaseResult.success && supabaseResult.userData) {
      // Supabase验证成功，保存用户信息
      const userId = supabaseResult.userData.id;
      console.log('💾 [Auth] 保存用户信息到本地存储:', userId);
      
      localStorage.setItem('user_id', userId);
      localStorage.setItem('invite_code', trimmedCode);
      localStorage.setItem('invite_logged_in', '1');
      
      return { 
        success: true, 
        userData: { id: userId } 
      };
    } else {
      // Supabase验证失败，返回具体错误
      console.warn('❌ [Auth] Supabase验证失败:', supabaseResult.message);
      return { 
        success: false, 
        error: supabaseResult.message || '内测码验证失败' 
      };
    }
  } catch (error) {
    console.error('💥 [Auth] Supabase验证出现异常:', error);
    
    // 检查是否是网络错误
    if (error instanceof Error) {
      if (error.message.includes('Failed to fetch') || error.message.includes('Network')) {
        return { 
          success: false, 
          error: '网络连接失败，请检查网络连接后重试' 
        };
      }
      
      if (error.message.includes('CORS')) {
        return { 
          success: false, 
          error: 'Supabase连接配置错误，请联系管理员' 
        };
      }
      
      return { 
        success: false, 
        error: `验证失败: ${error.message}` 
      };
    }
    
    // 不再提供本地降级模式，确保数据完整性
    return { 
      success: false, 
      error: '内测码验证系统暂时不可用，请稍后重试' 
    };
  }
}

/**
 * 检查本地是否有有效的登录状态
 */
export function getStoredUserId(): string | null {
  const userId = localStorage.getItem('user_id');
  const isLoggedIn = localStorage.getItem('invite_logged_in');
  
  if (userId && isLoggedIn === '1') {
    return userId;
  }
  
  return null;
}

/**
 * 清除本地登录状态
 */
export function clearStoredAuth(): void {
  localStorage.removeItem('user_id');
  localStorage.removeItem('invite_code');
  localStorage.removeItem('invite_logged_in');
}

// 用户行为日志 - 优先使用Supabase，失败时降级到后端API
export async function logUserAction(
  userId: string,
  action: string,
  payload?: string
): Promise<void> {
  // 更新用户活跃时间
  try {
    await updateUserActivity(userId);
  } catch (error) {
    console.warn('更新用户活跃时间失败:', error);
  }

  // 记录用户行为
  try {
    await logToSupabase(userId, action, payload);
  } catch (error) {
    console.warn('Supabase日志记录失败，降级到后端API:', error);
    
    // 降级到后端API
    try {
      await fetch('/analytics/log_action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, action, payload, ts: Date.now() })
      });
    } catch (err) {
      console.warn('后端API日志记录也失败:', err);
    }
  }
}


