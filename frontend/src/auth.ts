// 整合Supabase的用户认证与行为日志模块
import { createUserWithInviteCode, updateUserActivity, logUserAction as logToSupabase } from './supabaseClient'

export interface RegisterResult {
  success: boolean;
  userData?: { id: string };
  error?: string;
}

function ensureUserId(): string {
  const existing = localStorage.getItem('user_id');
  if (existing) return existing;
  const newId = `user_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem('user_id', newId);
  return newId;
}

// 邀请码注册 - 优先使用Supabase验证，失败时降级到本地验证
export async function registerUser(inviteCode: string): Promise<RegisterResult> {
  console.log('开始验证内测码:', inviteCode);
  
  if (!inviteCode || inviteCode.trim().length === 0) {
    return { success: false, error: '请输入内测码' };
  }

  const trimmedCode = inviteCode.trim();
  console.log('处理后的内测码:', trimmedCode);

  try {
    // 尝试通过Supabase验证内测码
    console.log('开始Supabase验证...');
    const supabaseResult = await createUserWithInviteCode(trimmedCode);
    console.log('Supabase验证结果:', supabaseResult);
    
    if (supabaseResult.success && supabaseResult.userData) {
      // Supabase验证成功，保存用户信息
      console.log('Supabase验证成功，保存用户信息:', supabaseResult.userData.id);
      localStorage.setItem('user_id', supabaseResult.userData.id);
      localStorage.setItem('invite_logged_in', '1');
      return { 
        success: true, 
        userData: { id: supabaseResult.userData.id } 
      };
    } else {
      // Supabase验证失败，返回具体错误
      console.log('Supabase验证失败:', supabaseResult.message);
      return { 
        success: false, 
        error: supabaseResult.message || '内测码验证失败' 
      };
    }
  } catch (error) {
    console.error('Supabase验证出现异常:', error);
    
    // 检查是否是网络错误
    if (error instanceof Error) {
      if (error.message.includes('Failed to fetch') || error.message.includes('Network')) {
        return { 
          success: false, 
          error: '网络连接失败，请检查网络连接或稍后重试' 
        };
      }
      
      return { 
        success: false, 
        error: `验证失败: ${error.message}` 
      };
    }
    
    // 降级到本地验证逻辑（仅作为最后手段）
    console.warn('降级到本地验证模式');
    ensureUserId();
    
    return { 
      success: false, 
      error: '内测码验证系统暂时不可用，请稍后重试' 
    };
  }
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


