-- 测试RLS策略数据隔离 - 修复版本
-- 在Supabase SQL Editor中运行此脚本

-- 清理可能存在的测试数据
DELETE FROM user_search_history WHERE search_id IN ('search_1_test', 'search_2_test');
DELETE FROM user_chat_history WHERE chat_id IN ('chat_1_test', 'chat_2_test');
DELETE FROM users WHERE id IN ('user_test_1', 'user_test_2');

-- 创建测试用户（必须先创建用户才能插入历史数据）
INSERT INTO users (id, invite_code, created_at) VALUES 
('user_test_1', 'TEST001', NOW()),
('user_test_2', 'TEST001', NOW());

-- 模拟用户1的数据操作
SELECT set_user_context('user_test_1');

-- 插入用户1的测试数据
INSERT INTO user_search_history (user_id, search_id, timestamp, original_query, expanded_keywords, papers, max_results)
VALUES (
    'user_test_1',
    'search_1_test',
    NOW(),
    '测试查询1',
    '["关键词1", "关键词2"]'::jsonb,
    '[]'::jsonb,
    10
);

INSERT INTO user_chat_history (user_id, chat_id, timestamp, title, messages, last_activity)
VALUES (
    'user_test_1',
    'chat_1_test',
    NOW(),
    '测试聊天1',
    '[]'::jsonb,
    NOW()
);

-- 模拟用户2的数据操作
SELECT set_user_context('user_test_2');

-- 插入用户2的测试数据
INSERT INTO user_search_history (user_id, search_id, timestamp, original_query, expanded_keywords, papers, max_results)
VALUES (
    'user_test_2',
    'search_2_test',
    NOW(),
    '测试查询2',
    '["关键词3", "关键词4"]'::jsonb,
    '[]'::jsonb,
    20
);

INSERT INTO user_chat_history (user_id, chat_id, timestamp, title, messages, last_activity)
VALUES (
    'user_test_2',
    'chat_2_test',
    NOW(),
    '测试聊天2',
    '[]'::jsonb,
    NOW()
);

-- 测试用户1只能看到自己的数据
SELECT set_user_context('user_test_1');

SELECT '=== 用户1应该只能看到自己的搜索历史 ===' as test_name;
SELECT user_id, search_id, original_query FROM user_search_history;

SELECT '=== 用户1应该只能看到自己的聊天历史 ===' as test_name;
SELECT user_id, chat_id, title FROM user_chat_history;

-- 测试用户2只能看到自己的数据
SELECT set_user_context('user_test_2');

SELECT '=== 用户2应该只能看到自己的搜索历史 ===' as test_name;
SELECT user_id, search_id, original_query FROM user_search_history;

SELECT '=== 用户2应该只能看到自己的聊天历史 ===' as test_name;
SELECT user_id, chat_id, title FROM user_chat_history;

-- 测试无用户上下文时应该看不到任何数据
SELECT clear_user_context();

SELECT '=== 无用户上下文时应该看不到任何数据 ===' as test_name;
SELECT COUNT(*) as search_count FROM user_search_history;
SELECT COUNT(*) as chat_count FROM user_chat_history;

-- 显示当前用户上下文状态
SELECT '=== 当前用户上下文 ===' as test_name;
SELECT get_current_user_id() as current_user;

-- 测试总结
SELECT '=== 测试结果总结 ===' as test_name;
SELECT 
    '如果用户1和用户2分别只能看到自己的1条搜索和1条聊天记录，' ||
    '而无用户上下文时看到0条记录，则RLS策略正常工作！' as result;

-- 清理测试数据
SELECT set_user_context('user_test_1');
DELETE FROM user_search_history WHERE search_id = 'search_1_test';
DELETE FROM user_chat_history WHERE chat_id = 'chat_1_test';

SELECT set_user_context('user_test_2');  
DELETE FROM user_search_history WHERE search_id = 'search_2_test';
DELETE FROM user_chat_history WHERE chat_id = 'chat_2_test';

-- 清理测试用户
DELETE FROM users WHERE id IN ('user_test_1', 'user_test_2');

SELECT clear_user_context();

SELECT '🎉 RLS隔离测试完成！' as status;