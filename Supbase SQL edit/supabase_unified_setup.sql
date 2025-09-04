-- Paper God Beta3 - 统一Supabase数据库配置
-- 🔧 解决表结构冲突，统一RLS策略
-- 在Supabase SQL Editor中运行此脚本

-- ================================
-- 第一步：完全清理现有配置
-- ================================

-- 删除所有触发器
DROP TRIGGER IF EXISTS update_conversation_on_message_insert ON conversation_messages;
DROP TRIGGER IF EXISTS auto_title_on_user_message ON conversation_messages;
DROP TRIGGER IF EXISTS auto_sequence_on_message_insert ON conversation_messages;

-- 删除所有函数
DROP FUNCTION IF EXISTS update_conversation_metadata() CASCADE;
DROP FUNCTION IF EXISTS auto_generate_conversation_title() CASCADE;
DROP FUNCTION IF EXISTS auto_set_message_sequence() CASCADE;
DROP FUNCTION IF EXISTS set_user_context(TEXT) CASCADE;
DROP FUNCTION IF EXISTS get_user_conversation_stats(TEXT) CASCADE;
DROP FUNCTION IF EXISTS cleanup_old_conversations(INTEGER) CASCADE;
DROP FUNCTION IF EXISTS archive_inactive_conversations(INTEGER) CASCADE;

-- 删除所有RLS策略
DROP POLICY IF EXISTS "invite_codes_select" ON invite_codes;
DROP POLICY IF EXISTS "invite_codes_update" ON invite_codes;
DROP POLICY IF EXISTS "users_insert" ON users;
DROP POLICY IF EXISTS "users_select" ON users;
DROP POLICY IF EXISTS "users_update" ON users;
DROP POLICY IF EXISTS "user_actions_policy" ON user_actions;
DROP POLICY IF EXISTS "user_search_history_policy" ON user_search_history;
DROP POLICY IF EXISTS "user_chat_history_policy" ON user_chat_history;
DROP POLICY IF EXISTS "user_settings_policy" ON user_settings;
DROP POLICY IF EXISTS "conversations_user_isolation" ON conversations;
DROP POLICY IF EXISTS "conversation_messages_user_isolation" ON conversation_messages;

-- 删除所有表
DROP TABLE IF EXISTS conversation_messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS user_settings CASCADE;
DROP TABLE IF EXISTS user_chat_history CASCADE;
DROP TABLE IF EXISTS user_search_history CASCADE;
DROP TABLE IF EXISTS user_actions CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS invite_codes CASCADE;

-- ================================
-- 第二步：创建统一的表结构
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

-- 7. 对话系统表 - 🔧 统一字段定义
CREATE TABLE conversations (
    -- 🔧 修复：使用单一主键conversation_id，兼容现有代码
    conversation_id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 对话基本信息
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 对话统计
    message_count INTEGER DEFAULT 0 CHECK (message_count >= 0),
    
    -- 标签 - 🔧 统一使用JSONB格式，与代码兼容
    tags JSONB DEFAULT '[]'::jsonb,
    
    -- 状态标识
    is_archived BOOLEAN DEFAULT FALSE,
    
    -- 扩展元数据
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 8. 对话消息表
CREATE TABLE conversation_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- 关联外键 - 🔧 修复：使用conversation_id直接关联
    conversation_id VARCHAR(100) NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    user_id VARCHAR(100) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 消息内容 - 🔧 修复：支持system角色
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    
    -- 时间戳
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 消息序号
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    
    -- 消息元数据
    message_metadata JSONB DEFAULT '{}'::jsonb,
    
    -- 唯一约束
    UNIQUE(conversation_id, sequence_number)
);

-- ================================
-- 第三步：创建性能优化索引
-- ================================

-- 基础表索引
CREATE INDEX idx_invite_codes_code ON invite_codes(code);
CREATE INDEX idx_invite_codes_used ON invite_codes(used);
CREATE INDEX idx_users_invite_code ON users(invite_code);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_user_actions_user_id ON user_actions(user_id);
CREATE INDEX idx_user_actions_created_at ON user_actions(created_at);
CREATE INDEX idx_search_history_user_id ON user_search_history(user_id);
CREATE INDEX idx_search_history_timestamp ON user_search_history(timestamp);
CREATE INDEX idx_search_history_search_id ON user_search_history(search_id);
CREATE INDEX idx_chat_history_user_id ON user_chat_history(user_id);
CREATE INDEX idx_chat_history_last_activity ON user_chat_history(last_activity);
CREATE INDEX idx_chat_history_chat_id ON user_chat_history(chat_id);
CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);

-- 对话系统索引
CREATE INDEX idx_conversations_user_activity ON conversations(user_id, last_activity DESC);
CREATE INDEX idx_conversations_user_created ON conversations(user_id, created_at DESC);
CREATE INDEX idx_conversations_user_archived ON conversations(user_id, is_archived);
CREATE INDEX idx_messages_conversation_seq ON conversation_messages(conversation_id, sequence_number);
CREATE INDEX idx_messages_user_timestamp ON conversation_messages(user_id, timestamp DESC);

-- ================================
-- 第四步：启用RLS并创建统一策略
-- ================================

-- 启用所有表的RLS
ALTER TABLE invite_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;

-- 🔧 创建统一的用户上下文设置函数
CREATE OR REPLACE FUNCTION set_user_context(target_user_id TEXT)
RETURNS VOID AS $$
BEGIN
    -- 设置当前会话的用户上下文
    PERFORM set_config('app.current_user_id', target_user_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 🔧 内测码策略（允许匿名访问）
CREATE POLICY "invite_codes_select" ON invite_codes
    FOR SELECT USING (true);

CREATE POLICY "invite_codes_update" ON invite_codes
    FOR UPDATE USING (NOT used);

-- 🔧 用户表策略（基本权限）
CREATE POLICY "users_insert" ON users
    FOR INSERT WITH CHECK (true);

CREATE POLICY "users_select" ON users
    FOR SELECT USING (true);

CREATE POLICY "users_update" ON users
    FOR UPDATE USING (true);

-- 🔧 统一的用户数据隔离策略
CREATE POLICY "user_actions_isolation" ON user_actions
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        user_id = current_setting('app.current_user_id', true)
    );

CREATE POLICY "user_search_history_isolation" ON user_search_history
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        user_id = current_setting('app.current_user_id', true)
    );

CREATE POLICY "user_chat_history_isolation" ON user_chat_history
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        user_id = current_setting('app.current_user_id', true)
    );

CREATE POLICY "user_settings_isolation" ON user_settings
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        user_id = current_setting('app.current_user_id', true)
    );

-- 🔧 对话系统RLS策略
CREATE POLICY "conversations_user_isolation" ON conversations
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        user_id = current_setting('app.current_user_id', true)
    );

CREATE POLICY "conversation_messages_user_isolation" ON conversation_messages
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        user_id = current_setting('app.current_user_id', true)
    );

-- ================================
-- 第五步：创建自动化触发器和函数
-- ================================

-- 1. 自动更新对话元数据
CREATE OR REPLACE FUNCTION update_conversation_metadata()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations 
    SET 
        updated_at = NOW(),
        last_activity = NOW(),
        message_count = (
            SELECT COUNT(*) 
            FROM conversation_messages 
            WHERE conversation_id = NEW.conversation_id
        )
    WHERE conversation_id = NEW.conversation_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_conversation_on_message_insert
    AFTER INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_metadata();

-- 2. 自动生成对话标题
CREATE OR REPLACE FUNCTION auto_generate_conversation_title()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.role = 'user' AND NEW.sequence_number <= 2 THEN
        UPDATE conversations 
        SET title = CASE 
            WHEN title IS NULL OR title = '' THEN 
                LEFT(NEW.content, 50) || CASE WHEN LENGTH(NEW.content) > 50 THEN '...' ELSE '' END
            ELSE title
        END
        WHERE conversation_id = NEW.conversation_id AND (title IS NULL OR title = '');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_title_on_user_message
    AFTER INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_conversation_title();

-- 3. 自动设置消息序号
CREATE OR REPLACE FUNCTION auto_set_message_sequence()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.sequence_number IS NULL OR NEW.sequence_number = 0 THEN
        SELECT COALESCE(MAX(sequence_number), 0) + 1
        INTO NEW.sequence_number
        FROM conversation_messages
        WHERE conversation_id = NEW.conversation_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_sequence_on_message_insert
    BEFORE INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION auto_set_message_sequence();

-- ================================
-- 第六步：数据约束和验证
-- ================================

-- UUID格式验证（适配VARCHAR格式）
ALTER TABLE conversations 
ADD CONSTRAINT conversations_id_format 
CHECK (conversation_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$');

-- 消息内容非空
ALTER TABLE conversation_messages 
ADD CONSTRAINT messages_content_not_empty 
CHECK (LENGTH(TRIM(content)) > 0);

-- ================================
-- 第七步：实用查询函数
-- ================================

-- 获取用户对话统计
CREATE OR REPLACE FUNCTION get_user_conversation_stats(target_user_id TEXT)
RETURNS JSON AS $$
DECLARE
    stats JSON;
BEGIN
    SELECT json_build_object(
        'total_conversations', COUNT(*),
        'active_conversations', COUNT(*) FILTER (WHERE NOT is_archived),
        'archived_conversations', COUNT(*) FILTER (WHERE is_archived),
        'total_messages', COALESCE(SUM(message_count), 0),
        'average_messages_per_conversation', 
            CASE WHEN COUNT(*) > 0 THEN ROUND(COALESCE(SUM(message_count), 0)::NUMERIC / COUNT(*), 2) ELSE 0 END,
        'last_activity', MAX(last_activity),
        'oldest_conversation', MIN(created_at),
        'newest_conversation', MAX(created_at)
    ) INTO stats
    FROM conversations 
    WHERE user_id = target_user_id;
    
    RETURN stats;
END;
$$ LANGUAGE plpgsql;

-- ================================
-- 第八步：插入初始测试数据
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
-- 第九步：验证配置完整性
-- ================================

-- 检查表创建
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 检查RLS策略
SELECT 
    schemaname,
    tablename,
    policyname,
    cmd
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- 检查函数
SELECT 
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN ('set_user_context', 'get_user_conversation_stats', 'update_conversation_metadata');

-- ================================
-- 完成提示
-- ================================

SELECT 
    '🎉 Paper God Beta3 统一数据库配置完成！' as status,
    '表结构: ✅ 统一' as tables,
    'RLS策略: ✅ 统一用户上下文' as security,
    '触发器: ✅ 自动化功能' as triggers,
    '内测码: ✅ 已插入' as invite_codes,
    '索引: ✅ 性能优化' as indexes;