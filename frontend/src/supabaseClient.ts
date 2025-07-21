import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://jfzchljmfnnsrszabpys.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmemNobGptZm5uc3JzemFicHlzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI2NDcwOTksImV4cCI6MjA2ODIyMzA5OX0.E_soKX6nkQm5xb4bO-q_4NmR8Z7ajQOQSq5cGtO91-g';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// 用户管理相关函数
export interface UserProfile {
  id: string;
  email?: string;
  invite_code: string;
  created_at: string;
  last_action?: string;
  last_action_at?: string;
}

export interface UserAction {
  id: string;
  user_id: string;
  action: string;
  detail?: string;
  created_at: string;
}

export interface InviteCode {
  id: string;
  code: string;
  used: boolean;
  used_by?: string;
  used_at?: string;
  created_at: string;
}

// 验证邀请码
export async function validateInviteCode(code: string): Promise<{ valid: boolean; codeData?: InviteCode; error?: string }> {
  try {
    const { data, error } = await supabase
      .from('invite_codes')
      .select('*')
      .eq('code', code.trim())
      .eq('used', false)
      .single();

    if (error || !data) {
      return { valid: false, error: '邀请码无效或已被使用' };
    }

    return { valid: true, codeData: data };
  } catch (error) {
    return { valid: false, error: '验证邀请码时出错' };
  }
}

// 注册用户
export async function registerUser(inviteCode: string, email?: string): Promise<{ success: boolean; userData?: UserProfile; error?: string }> {
  try {
    // 验证邀请码
    const validation = await validateInviteCode(inviteCode);
    if (!validation.valid) {
      return { success: false, error: validation.error };
    }

    // 创建用户
    const { data: userData, error: userError } = await supabase
      .from('users')
      .insert({ 
        invite_code: inviteCode.trim(),
        email: email || null,
        last_action: 'register',
        last_action_at: new Date().toISOString()
      })
      .select()
      .single();

    if (userError || !userData) {
      return { success: false, error: '创建用户失败' };
    }

    // 标记邀请码为已使用
    await supabase
      .from('invite_codes')
      .update({ 
        used: true, 
        used_by: userData.id,
        used_at: new Date().toISOString() 
      })
      .eq('id', validation.codeData!.id);

    // 记录注册行为
    await logUserAction(userData.id, 'register', `使用邀请码: ${inviteCode.trim()}`);

    return { success: true, userData };
  } catch (error) {
    return { success: false, error: '注册过程中出错' };
  }
}

// 记录用户行为
export async function logUserAction(userId: string, action: string, detail?: string): Promise<void> {
  try {
    await supabase
      .from('user_actions')
      .insert({
        user_id: userId,
        action,
        detail: detail || null
      });

    // 更新用户最后活动时间
    await supabase
      .from('users')
      .update({
        last_action: action,
        last_action_at: new Date().toISOString()
      })
      .eq('id', userId);
  } catch (error) {
    console.error('记录用户行为失败:', error);
  }
}

// 获取用户信息
export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  try {
    const { data, error } = await supabase
      .from('users')
      .select('*')
      .eq('id', userId)
      .single();

    if (error || !data) {
      return null;
    }

    return data;
  } catch (error) {
    console.error('获取用户信息失败:', error);
    return null;
  }
}

// 获取用户行为日志
export async function getUserActions(userId: string, limit: number = 50): Promise<UserAction[]> {
  try {
    const { data, error } = await supabase
      .from('user_actions')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (error) {
      console.error('获取用户行为失败:', error);
      return [];
    }

    return data || [];
  } catch (error) {
    console.error('获取用户行为失败:', error);
    return [];
  }
} 