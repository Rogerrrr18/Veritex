-- 创建用户上下文管理SQL函数
-- 在Supabase SQL Editor中运行

-- 创建设置用户上下文的函数
CREATE OR REPLACE FUNCTION set_user_context(user_id TEXT)
RETURNS VOID AS $$
BEGIN
  PERFORM set_config('app.current_user_id', user_id, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 创建清除用户上下文的函数
CREATE OR REPLACE FUNCTION clear_user_context()
RETURNS VOID AS $$
BEGIN
  PERFORM set_config('app.current_user_id', '', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 创建获取当前用户ID的函数（如果不存在）
CREATE OR REPLACE FUNCTION get_current_user_id()
RETURNS TEXT AS $$
BEGIN
  RETURN COALESCE(
    current_setting('app.current_user_id', true),
    current_setting('request.jwt.claims', true)::json->>'user_id',
    current_setting('request.headers.user-id', true),
    auth.uid()::text,
    ''
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 验证函数创建成功
SELECT 
    routine_name,
    routine_type,
    data_type
FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_name IN ('set_user_context', 'clear_user_context', 'get_current_user_id')
ORDER BY routine_name;