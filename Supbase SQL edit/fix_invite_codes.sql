-- 🚨 修复内测码表RLS策略问题
-- 立即在Supabase SQL Editor中执行

-- 临时禁用内测码表的RLS，允许匿名访问
ALTER TABLE invite_codes DISABLE ROW LEVEL SECURITY;

-- 删除可能存在的有问题的策略
DROP POLICY IF EXISTS "invite_codes_select" ON invite_codes;
DROP POLICY IF EXISTS "invite_codes_update" ON invite_codes;
DROP POLICY IF EXISTS "anonymous_select_invite_codes" ON invite_codes;
DROP POLICY IF EXISTS "anonymous_update_invite_codes" ON invite_codes;

-- 重新启用RLS
ALTER TABLE invite_codes ENABLE ROW LEVEL SECURITY;

-- 创建正确的内测码策略（允许匿名访问）
CREATE POLICY "allow_anonymous_select_invite_codes" ON invite_codes
    FOR SELECT USING (true);

CREATE POLICY "allow_anonymous_update_invite_codes" ON invite_codes
    FOR UPDATE USING (NOT used);

-- 验证策略创建
SELECT 
    tablename,
    policyname,
    cmd
FROM pg_policies 
WHERE tablename = 'invite_codes'
ORDER BY policyname;

SELECT '✅ 内测码表RLS策略修复完成' as status;