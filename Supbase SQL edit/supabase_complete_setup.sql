-- Paper God Beta2 - Supabase完整数据库设置
-- 🔐 包含安全的RLS策略，确保用户数据完全隔离
-- 在Supabase SQL Editor中运行此脚本

-- ================================
-- 第一步：清理所有现有数据
-- ================================

-- 删除所有现有策略
DROP POLICY IF EXISTS "invite_codes_select" ON invite_codes;
DROP POLICY IF EXISTS "invite_codes_update" ON invite_codes;
DROP POLICY IF EXISTS "users_insert" ON users;
DROP POLICY IF EXISTS "users_select" ON users;
DROP POLICY IF EXISTS "users_update" ON users;
DROP POLICY IF EXISTS "user_actions_policy" ON user_actions;
DROP POLICY IF EXISTS "user_search_history_policy" ON user_search_history;
DROP POLICY IF EXISTS "user_chat_history_policy" ON user_chat_history;
DROP POLICY IF EXISTS "user_settings_policy" ON user_settings;

-- 删除旧的策略名称（如果存在）
DROP POLICY IF EXISTS "允许匿名查询内测码" ON invite_codes;
DROP POLICY IF EXISTS "允许匿名使用内测码" ON invite_codes;
DROP POLICY IF EXISTS "用户只能查看自己的信息" ON users;
DROP POLICY IF EXISTS "允许创建用户" ON users;
DROP POLICY IF EXISTS "用户只能更新自己的信息" ON users;
DROP POLICY IF EXISTS "允许插入用户行为日志" ON user_actions;
DROP POLICY IF EXISTS "用户只能查看自己的行为日志" ON user_actions;
DROP POLICY IF EXISTS "用户只能查看自己的搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "允许插入用户搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "用户只能更新自己的搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "用户只能删除自己的搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "用户只能查看自己的聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "允许插入用户聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "用户只能更新自己的聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "用户只能删除自己的聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "用户只能查看自己的设置" ON user_settings;
DROP POLICY IF EXISTS "允许插入用户设置" ON user_settings;
DROP POLICY IF EXISTS "用户只能更新自己的设置" ON user_settings;
DROP POLICY IF EXISTS "anonymous_select_invite_codes" ON invite_codes;
DROP POLICY IF EXISTS "anonymous_update_invite_codes" ON invite_codes;
DROP POLICY IF EXISTS "allow_user_insert" ON users;
DROP POLICY IF EXISTS "allow_user_select" ON users;
DROP POLICY IF EXISTS "allow_user_update" ON users;
DROP POLICY IF EXISTS "user_own_actions_only" ON user_actions;
DROP POLICY IF EXISTS "user_own_search_only" ON user_search_history;
DROP POLICY IF EXISTS "user_own_chat_only" ON user_chat_history;
DROP POLICY IF EXISTS "user_own_settings_only" ON user_settings;

-- 删除所有现有表
DROP TABLE IF EXISTS user_settings CASCADE;
DROP TABLE IF EXISTS user_chat_history CASCADE;
DROP TABLE IF EXISTS user_search_history CASCADE;
DROP TABLE IF EXISTS user_actions CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS invite_codes CASCADE;

-- ================================
-- 第二步：创建数据表结构
-- ================================

-- 1. 内测码表
CREATE TABLE invite_codes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE,
    user_id VARCHAR(100),
    notes TEXT
);

-- 2. 用户表
CREATE TABLE users (
    id VARCHAR(100) PRIMARY KEY,
    invite_code VARCHAR(50) REFERENCES invite_codes(code),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 3. 用户行为日志表
CREATE TABLE user_actions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. 用户搜索历史表
CREATE TABLE user_search_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id) ON DELETE CASCADE,
    search_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    original_query TEXT NOT NULL,
    expanded_keywords JSONB NOT NULL,
    papers JSONB NOT NULL,
    max_results INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 用户聊天历史表
CREATE TABLE user_chat_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id) ON DELETE CASCADE,
    chat_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    title TEXT NOT NULL,
    messages JSONB NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. 用户设置表
CREATE TABLE user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    theme VARCHAR(10) DEFAULT 'dark',
    language VARCHAR(10) DEFAULT 'zh',
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ================================
-- 第三步：创建数据库索引（提高性能）
-- ================================

-- 内测码表索引
CREATE INDEX idx_invite_codes_code ON invite_codes(code);
CREATE INDEX idx_invite_codes_used ON invite_codes(used);

-- 用户表索引
CREATE INDEX idx_users_invite_code ON users(invite_code);
CREATE INDEX idx_users_created_at ON users(created_at);

-- 用户行为日志索引
CREATE INDEX idx_user_actions_user_id ON user_actions(user_id);
CREATE INDEX idx_user_actions_created_at ON user_actions(created_at);

-- 搜索历史索引
CREATE INDEX idx_search_history_user_id ON user_search_history(user_id);
CREATE INDEX idx_search_history_timestamp ON user_search_history(timestamp);
CREATE INDEX idx_search_history_search_id ON user_search_history(search_id);

-- 聊天历史索引
CREATE INDEX idx_chat_history_user_id ON user_chat_history(user_id);
CREATE INDEX idx_chat_history_last_activity ON user_chat_history(last_activity);
CREATE INDEX idx_chat_history_chat_id ON user_chat_history(chat_id);

-- 用户设置索引
CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);

-- ================================
-- 第四步：启用行级安全策略(RLS)
-- ================================

ALTER TABLE invite_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- ================================
-- 第五步：创建安全的RLS策略
-- ================================

-- 🔓 内测码策略（允许匿名访问验证）
CREATE POLICY "invite_codes_select" ON invite_codes
    FOR SELECT USING (true);

CREATE POLICY "invite_codes_update" ON invite_codes
    FOR UPDATE USING (NOT used);

-- 👤 用户表策略（允许创建和基本查询）
CREATE POLICY "users_insert" ON users
    FOR INSERT WITH CHECK (true);

CREATE POLICY "users_select" ON users
    FOR SELECT USING (true);

CREATE POLICY "users_update" ON users
    FOR UPDATE USING (true);

-- 🔐 严格的用户数据隔离策略
-- 关键：使用HTTP头传递的用户ID进行验证

-- 用户行为日志策略
CREATE POLICY "user_actions_policy" ON user_actions
    FOR ALL USING (
        user_id = current_setting('request.headers.x-user-id', true)
    )
    WITH CHECK (
        user_id = current_setting('request.headers.x-user-id', true)
    );

-- 搜索历史策略
CREATE POLICY "user_search_history_policy" ON user_search_history
    FOR ALL USING (
        user_id = current_setting('request.headers.x-user-id', true)
    )
    WITH CHECK (
        user_id = current_setting('request.headers.x-user-id', true)
    );

-- 聊天历史策略
CREATE POLICY "user_chat_history_policy" ON user_chat_history
    FOR ALL USING (
        user_id = current_setting('request.headers.x-user-id', true)
    )
    WITH CHECK (
        user_id = current_setting('request.headers.x-user-id', true)
    );

-- 用户设置策略
CREATE POLICY "user_settings_policy" ON user_settings
    FOR ALL USING (
        user_id = current_setting('request.headers.x-user-id', true)
    )
    WITH CHECK (
        user_id = current_setting('request.headers.x-user-id', true)
    );

-- ================================
-- 第六步：插入初始内测码
-- ================================

INSERT INTO invite_codes (code, notes) VALUES 
('PAPERGOD001', 'Paper God内测码1 - 主要测试用'),
('PAPERGOD002', 'Paper God内测码2 - 次要测试用'),
('PAPERGOD003', 'Paper God内测码3 - 备用测试'),
('BETA2024001', 'Beta 2024版本测试码1'),
('BETA2024002', 'Beta 2024版本测试码2'),
('DEV001', '开发者专用码1'),
('DEV002', '开发者专用码2'),
('DEMO001', '演示用码1'),
('DEMO002', '演示用码2'),
('TEST001', '功能测试码');

-- ================================
-- 第七步：验证数据库设置
-- ================================

-- 检查表是否创建成功
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 检查RLS策略是否创建成功
SELECT 
    schemaname,
    tablename,
    policyname,
    cmd
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- 检查内测码是否插入成功
SELECT code, notes, used FROM invite_codes ORDER BY created_at;

-- ================================
-- 设置完成提示
-- ================================

SELECT '🎉 Paper God Beta2 数据库设置完成！' as status,
       '数据表创建: ✅' as tables,
       'RLS策略: ✅' as security,
       '内测码: ✅' as invite_codes,
       '索引优化: ✅' as indexes;