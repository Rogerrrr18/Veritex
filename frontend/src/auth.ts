// 轻量本地鉴权与行为日志模块（替代已移除的 supabaseClient）

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

// 邀请码注册（前端校验 + 尝试上报后端）
export async function registerUser(inviteCode: string): Promise<RegisterResult> {
  if (!inviteCode || inviteCode.trim().length < 6) {
    return { success: false, error: '邀请码无效，请输入6位邀请码' };
  }

  const userId = ensureUserId();

  // 尝试通知后端（如果后端存在对应接口则记录下来，不存在也不影响前端流程）
  try {
    await fetch('/analytics/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ invite_code: inviteCode.trim(), user_id: userId })
    });
  } catch (err) {
    // 忽略网络/接口错误，前端本地注册仍然生效
    // console.warn('registerUser 上报失败:', err)
  }

  return { success: true, userData: { id: userId } };
}

// 用户行为日志（失败时静默）
export async function logUserAction(
  userId: string,
  action: string,
  payload?: string
): Promise<void> {
  try {
    await fetch('/analytics/log_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, action, payload, ts: Date.now() })
    });
  } catch (err) {
    // 静默失败，避免影响主流程
    // console.warn('logUserAction 上报失败:', err)
  }
}


