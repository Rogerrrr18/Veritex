-- 🚀 快速RLS测试 - 无需创建用户
-- 在Supabase SQL Editor中运行

-- 1. 测试用户上下文函数是否工作
SELECT '=== 测试用户上下文函数 ===' as test_name;
SELECT set_user_context('test_user_123');
SELECT get_current_user_id() as current_user_id;

-- 2. 清除用户上下文
SELECT '=== 清除用户上下文 ===' as test_name;
SELECT clear_user_context();
SELECT get_current_user_id() as current_user_id_after_clear;

-- 3. 检查内测码表是否可以正常访问
SELECT '=== 测试内测码表访问 ===' as test_name;
SELECT code, used FROM invite_codes LIMIT 3;

-- 4. 检查RLS策略是否存在
SELECT '=== 检查RLS策略 ===' as test_name;
SELECT 
    tablename,
    policyname,
    cmd
FROM pg_policies 
WHERE schemaname = 'public'
AND tablename IN ('user_search_history', 'user_chat_history', 'user_actions', 'user_settings')
ORDER BY tablename, policyname;

-- 5. 检查表是否启用了RLS
SELECT '=== 检查RLS启用状态 ===' as test_name;
SELECT 
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables 
WHERE schemaname = 'public'
AND tablename IN ('invite_codes', 'users', 'user_search_history', 'user_chat_history', 'user_actions', 'user_settings')
ORDER BY tablename;

-- 6. 测试空查询（应该返回空结果而不是错误）
SELECT '=== 测试空用户上下文下的查询 ===' as test_name;
SELECT COUNT(*) as search_history_count FROM user_search_history;
SELECT COUNT(*) as chat_history_count FROM user_chat_history;
SELECT COUNT(*) as user_actions_count FROM user_actions;

SELECT '🎉 快速RLS测试完成！' as status;
SELECT '如果上述查询都正常执行且没有错误，说明RLS策略配置正确' as conclusion;