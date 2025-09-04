-- Paper God Beta2 - 对话系统扩展SQL脚本
-- 🔄 在现有用户系统基础上新增对话功能
-- 使用方法：在Supabase SQL Editor中运行此脚本（需先运行supabase_complete_setup.sql）

-- ================================
-- 检查前置条件
-- ================================

-- 确保基础用户表已存在
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users') THEN
        RAISE EXCEPTION '请先运行 supabase_complete_setup.sql 创建基础用户系统';
    END IF;
    
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'invite_codes') THEN
        RAISE EXCEPTION '请先运行 supabase_complete_setup.sql 创建基础用户系统';
    END IF;
END $$;

-- ================================
-- 对话系统表结构
-- ================================

-- 删除已存在的对话相关表（如果存在）
DROP TABLE IF EXISTS conversation_messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;

-- 1. 对话主表 - 存储对话元数据
CREATE TABLE conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id VARCHAR(100) UNIQUE NOT NULL, -- 对应原有UUID格式
    user_id VARCHAR(100) NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 用户隔离
    
    -- 对话元数据（对应ConversationMetadata）
    title TEXT, -- 对话标题
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    tags JSONB DEFAULT '[]'::jsonb, -- 对话标签数组
    is_archived BOOLEAN DEFAULT FALSE,
    
    -- 扩展字段
    metadata JSONB DEFAULT '{}'::jsonb -- 额外元数据
);

-- 2. 对话消息表 - 存储具体消息内容
CREATE TABLE conversation_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id VARCHAR(100) NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    user_id VARCHAR(100) NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 用户隔离（冗余但利于性能）
    
    -- 消息内容（对应ChatMessage）
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_metadata JSONB DEFAULT '{}'::jsonb, -- 消息级元数据
    
    -- 消息序号（用于排序和分页）
    sequence_number INTEGER NOT NULL,
    
    -- 确保同一对话内消息序号唯一
    UNIQUE(conversation_id, sequence_number)
);

-- ================================
-- 性能优化索引
-- ================================

-- 对话表索引
CREATE INDEX idx_conversations_user_activity 
    ON conversations(user_id, last_activity DESC, is_archived);

CREATE INDEX idx_conversations_user_created 
    ON conversations(user_id, created_at DESC);

CREATE INDEX idx_conversations_conversation_id 
    ON conversations(conversation_id);

-- 消息表索引
CREATE INDEX idx_messages_conversation_sequence 
    ON conversation_messages(conversation_id, sequence_number);

CREATE INDEX idx_messages_user_timestamp 
    ON conversation_messages(user_id, timestamp DESC);

-- ================================
-- RLS（行级安全）策略
-- ================================

-- 启用RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;

-- 🔧 创建用户上下文设置函数（后端调用需要）
CREATE OR REPLACE FUNCTION set_user_context(user_id TEXT)
RETURNS VOID AS $$
BEGIN
    -- 设置当前会话的用户上下文
    PERFORM set_config('app.user_id', user_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 对话表RLS策略
CREATE POLICY "conversations_user_isolation" ON conversations
    FOR ALL USING (
        user_id = current_setting('app.user_id', true)::text
    );

-- 消息表RLS策略  
CREATE POLICY "conversation_messages_user_isolation" ON conversation_messages
    FOR ALL USING (
        user_id = current_setting('app.user_id', true)::text
    );

-- ================================
-- 自动化触发器和函数
-- ================================

-- 1. 自动更新对话元数据的函数
CREATE OR REPLACE FUNCTION update_conversation_metadata()
RETURNS TRIGGER AS $$
BEGIN
    -- 更新对话的最后活跃时间、更新时间和消息计数
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

-- 在插入新消息时自动更新对话元数据
CREATE TRIGGER update_conversation_on_message_insert
    AFTER INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_metadata();

-- 2. 自动生成对话标题的函数
CREATE OR REPLACE FUNCTION auto_generate_conversation_title()
RETURNS TRIGGER AS $$
BEGIN
    -- 如果是用户消息且是对话的前几条消息，自动生成标题
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

-- 在插入用户消息时自动生成标题
CREATE TRIGGER auto_title_on_user_message
    AFTER INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_conversation_title();

-- 3. 自动设置消息序号的函数
CREATE OR REPLACE FUNCTION auto_set_message_sequence()
RETURNS TRIGGER AS $$
BEGIN
    -- 如果没有手动设置序号，自动分配
    IF NEW.sequence_number IS NULL OR NEW.sequence_number = 0 THEN
        SELECT COALESCE(MAX(sequence_number), 0) + 1
        INTO NEW.sequence_number
        FROM conversation_messages
        WHERE conversation_id = NEW.conversation_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 在插入消息前自动设置序号
CREATE TRIGGER auto_sequence_on_message_insert
    BEFORE INSERT ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION auto_set_message_sequence();

-- ================================
-- 数据完整性约束
-- ================================

-- 确保对话ID格式正确（UUID格式）
ALTER TABLE conversations 
ADD CONSTRAINT conversations_id_format 
CHECK (conversation_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$');

-- 确保消息内容非空
ALTER TABLE conversation_messages 
ADD CONSTRAINT messages_content_not_empty 
CHECK (LENGTH(TRIM(content)) > 0);

-- 确保消息序号为正数
ALTER TABLE conversation_messages 
ADD CONSTRAINT messages_sequence_positive 
CHECK (sequence_number > 0);

-- ================================
-- 实用查询函数
-- ================================

-- 1. 获取用户对话统计
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

-- 2. 清理过期对话
CREATE OR REPLACE FUNCTION cleanup_old_conversations(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- 删除超过指定天数的归档对话
    WITH deleted AS (
        DELETE FROM conversations 
        WHERE is_archived = true 
          AND last_activity < (NOW() - INTERVAL '1 day' * days_to_keep)
        RETURNING id
    )
    SELECT COUNT(*) INTO deleted_count FROM deleted;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 3. 批量归档旧对话
CREATE OR REPLACE FUNCTION archive_inactive_conversations(inactive_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- 归档超过指定天数无活动的对话
    WITH archived AS (
        UPDATE conversations 
        SET is_archived = true, updated_at = NOW()
        WHERE is_archived = false 
          AND last_activity < (NOW() - INTERVAL '1 day' * inactive_days)
        RETURNING id
    )
    SELECT COUNT(*) INTO archived_count FROM archived;
    
    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;

-- ================================
-- 测试数据（可选）
-- ================================

-- 取消注释以下代码可插入测试数据
/*
-- 插入测试对话（需要先有有效的user_id）
INSERT INTO conversations (conversation_id, user_id, title) VALUES 
('550e8400-e29b-41d4-a716-446655440000', 'user_example_123', '测试学术讨论');

-- 插入测试消息
INSERT INTO conversation_messages (conversation_id, user_id, role, content, sequence_number) VALUES 
('550e8400-e29b-41d4-a716-446655440000', 'user_example_123', 'user', '你好，我想了解机器学习的基础知识', 1),
('550e8400-e29b-41d4-a716-446655440000', 'user_example_123', 'assistant', '机器学习是人工智能的一个重要分支...', 2),
('550e8400-e29b-41d4-a716-446655440000', 'user_example_123', 'user', '能推荐一些入门论文吗？', 3);
*/

-- ================================
-- 验证安装
-- ================================

-- 验证表创建成功
DO $$
DECLARE
    conversations_count INTEGER;
    messages_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO conversations_count FROM information_schema.tables WHERE table_name = 'conversations';
    SELECT COUNT(*) INTO messages_count FROM information_schema.tables WHERE table_name = 'conversation_messages';
    
    IF conversations_count = 0 THEN
        RAISE EXCEPTION '对话表创建失败';
    END IF;
    
    IF messages_count = 0 THEN
        RAISE EXCEPTION '消息表创建失败';
    END IF;
    
    RAISE NOTICE '✅ 对话系统扩展安装成功！';
    RAISE NOTICE '📊 已创建 conversations 和 conversation_messages 表';
    RAISE NOTICE '🔐 已配置 RLS 策略确保用户数据隔离';
    RAISE NOTICE '⚡ 已创建索引优化查询性能';
    RAISE NOTICE '🔧 已设置自动化触发器和实用函数';
END $$;

-- ================================
-- 使用说明
-- ================================

-- 使用说明（以注释形式记录）
/*
📋 对话系统使用指南:

1. 用户上下文设置（必须）:
   SELECT set_config('app.user_id', 'your_user_id', false);

2. 创建新对话:
   INSERT INTO conversations (conversation_id, user_id, title) 
   VALUES ('new-uuid', current_setting('app.user_id'), '对话标题');

3. 添加消息:
   INSERT INTO conversation_messages (conversation_id, user_id, role, content)
   VALUES ('conversation-uuid', current_setting('app.user_id'), 'user', '消息内容');

4. 查询对话列表:
   SELECT * FROM conversations 
   WHERE user_id = current_setting('app.user_id') 
   ORDER BY last_activity DESC;

5. 获取对话消息:
   SELECT * FROM conversation_messages 
   WHERE conversation_id = 'target-uuid' 
   ORDER BY sequence_number;

6. 获取统计信息:
   SELECT get_user_conversation_stats(current_setting('app.user_id'));

⚠️  重要：所有操作都通过 RLS 策略自动限制为当前用户的数据
*/