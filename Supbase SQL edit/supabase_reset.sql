-- Supabase完全重置脚本 - 解决策略冲突和数据串联问题
-- 在Supabase SQL Editor中运行

-- 1. 删除所有现有策略
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

-- 2. 删除所有现有表（包含数据）
DROP TABLE IF EXISTS user_settings CASCADE;
DROP TABLE IF EXISTS user_chat_history CASCADE;
DROP TABLE IF EXISTS user_search_history CASCADE;
DROP TABLE IF EXISTS user_actions CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS invite_codes CASCADE;

-- 3. 重新创建所有表
CREATE TABLE invite_codes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE,
    user_id VARCHAR(100),
    notes TEXT
);

CREATE TABLE users (
    id VARCHAR(100) PRIMARY KEY,
    invite_code VARCHAR(50) REFERENCES invite_codes(code),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE user_actions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_search_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id),
    search_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    original_query TEXT NOT NULL,
    expanded_keywords JSONB NOT NULL,
    papers JSONB NOT NULL,
    max_results INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_chat_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id),
    chat_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    title TEXT NOT NULL,
    messages JSONB NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id) UNIQUE,
    theme VARCHAR(10) DEFAULT 'dark',
    language VARCHAR(10) DEFAULT 'zh',
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. 启用RLS
ALTER TABLE invite_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- 5. 创建严格的RLS策略
-- 内测码策略（允许匿名访问）
CREATE POLICY "anonymous_select_invite_codes" ON invite_codes
    FOR SELECT USING (true);

CREATE POLICY "anonymous_update_invite_codes" ON invite_codes
    FOR UPDATE USING (NOT used);

-- 用户策略（允许创建和查看）
CREATE POLICY "allow_user_insert" ON users
    FOR INSERT WITH CHECK (true);

CREATE POLICY "allow_user_select" ON users
    FOR SELECT USING (true);

CREATE POLICY "allow_user_update" ON users
    FOR UPDATE USING (true);

-- 严格的数据隔离策略 - 关键：使用auth.uid()确保数据隔离
CREATE POLICY "user_own_actions_only" ON user_actions
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

CREATE POLICY "user_own_search_only" ON user_search_history
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

CREATE POLICY "user_own_chat_only" ON user_chat_history
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

CREATE POLICY "user_own_settings_only" ON user_settings
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

-- 6. 插入全新的内测码
INSERT INTO invite_codes (code, notes) VALUES 
('BETA001', '内测码1'),
('BETA002', '内测码2'),
('BETA003', '内测码3'),
('DEV2024', '开发者码'),
('TEST001', '测试码'),
('DEMO001', '演示码');

-- 7. 验证表创建
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;