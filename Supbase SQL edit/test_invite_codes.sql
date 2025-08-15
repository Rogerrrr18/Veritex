-- 测试内测码查询脚本
-- 在Supabase SQL Editor中运行此脚本来验证内测码

-- 1. 查看所有内测码
SELECT 
    code,
    used,
    created_at,
    notes
FROM invite_codes
ORDER BY created_at DESC;

-- 2. 查看可用的内测码
SELECT 
    code,
    notes
FROM invite_codes
WHERE used = false
ORDER BY code;

-- 3. 测试查询特定内测码
SELECT 
    *
FROM invite_codes
WHERE code = 'BETA001';

-- 4. 获取统计信息
SELECT get_invite_stats();

-- 5. 查看所有表
SELECT 
    table_name,
    table_type
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;