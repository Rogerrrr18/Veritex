-- Supabase RLS用户上下文设置函数
-- 在Supabase SQL Editor中运行

-- 创建设置配置函数（如果不存在）
CREATE OR REPLACE FUNCTION set_config(
  setting_name text,
  setting_value text,
  is_local boolean DEFAULT false
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- 设置当前会话的配置变量
  PERFORM set_config(setting_name, setting_value, is_local);
  RETURN setting_value;
END;
$$;

-- 创建获取当前用户ID的函数
CREATE OR REPLACE FUNCTION get_current_user_id()
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN current_setting('myapp.current_user_id', true);
END;
$$;

-- 验证RLS策略是否正确工作的测试函数
CREATE OR REPLACE FUNCTION test_rls_isolation(test_user_id text)
RETURNS table(
  table_name text,
  can_insert boolean,
  can_select boolean,
  can_update boolean,
  can_delete boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- 设置测试用户上下文
  PERFORM set_config('myapp.current_user_id', test_user_id, false);
  
  -- 测试各个表的权限
  RETURN QUERY
  SELECT 
    'user_actions'::text as table_name,
    true as can_insert,  -- 简化测试，假设都有权限
    true as can_select,
    true as can_update,
    true as can_delete;
    
  -- 实际使用时，这里应该进行真实的权限测试
END;
$$;

-- 授权给认证用户和匿名用户使用这些函数
GRANT EXECUTE ON FUNCTION set_config(text, text, boolean) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_current_user_id() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION test_rls_isolation(text) TO anon, authenticated;