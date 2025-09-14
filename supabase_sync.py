"""
Paper God Beta3 - Supabase同步管理器
支持用户数据隔离和RLS安全策略的云端对话存储
"""

import os
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Supabase客户端
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None

from models.conversation import Conversation, ChatMessage, ConversationSummary

logger = logging.getLogger(__name__)


class SupabaseSyncManager:
    """Supabase同步管理器 - 支持用户数据隔离的云端存储"""
    
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.is_available = False
        self._init_client()
    
    def _init_client(self):
        """初始化Supabase客户端"""
        if not create_client:
            logger.error("Supabase SDK未安装，请运行: pip install supabase")
            return
            
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            logger.error("Supabase配置缺失: SUPABASE_URL 或 SUPABASE_ANON_KEY")
            return
        
        try:
            self.supabase = create_client(url, key)
            # 测试连接
            result = self.supabase.table("conversations").select("count").limit(1).execute()
            self.is_available = True
            logger.info("Supabase连接成功")
        except Exception as e:
            logger.error(f"Supabase连接失败: {e}")
            self.is_available = False
    
    async def save_conversation(self, conversation: Conversation, user_id: str) -> bool:
        """保存对话到Supabase（支持用户隔离）"""
        if not self.is_available:
            logger.warning(f"🔇 [Supabase保存] 服务不可用，跳过保存 {conversation.conversation_id[:8]}...")
            return False
        
        try:
            # 🔧 修复：确保用户存在（解决外键约束问题）
            await self._ensure_user_exists(user_id)
            
            # 🔧 调试：设置用户上下文
            context_set = self.set_user_context(user_id)
            if not context_set:
                logger.warning(f"⚠️ [Supabase保存] 用户上下文设置失败: {user_id}")
            else:
                logger.debug(f"✅ [Supabase保存] 用户上下文设置成功: {user_id}")
            
            # 创建JSON序列化安全的对话数据
            def serialize_datetime(obj):
                """自定义datetime序列化器"""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            # 🔧 修复：简化数据结构，移除复杂的metadata嵌套
            conversation_data = {
                "conversation_id": conversation.conversation_id,
                "user_id": user_id,  # 用户隔离字段
                "title": conversation.metadata.title or f"对话 {datetime.now().strftime('%m-%d %H:%M')}",
                "created_at": conversation.metadata.created_at.isoformat(),
                "updated_at": conversation.metadata.updated_at.isoformat(),
                "last_activity": conversation.metadata.last_activity.isoformat(),
                "message_count": conversation.metadata.message_count,
                "tags": conversation.metadata.tags or [],
                "is_archived": conversation.metadata.is_archived or False,
                "metadata": {}  # 简化为空对象
            }
            
            logger.debug(f"📝 [Supabase保存] 准备保存数据: 对话={conversation.conversation_id[:8]}... 用户={user_id}")
            
            # 🔧 修复：使用复合主键进行upsert
            result = self.supabase.table("conversations").upsert(
                conversation_data,
                on_conflict="conversation_id,user_id"  # 匹配复合唯一约束
            ).execute()
            
            # 🔧 调试：检查返回结果
            if result.data:
                logger.info(f"✅ [Supabase保存] 对话保存成功: {conversation.conversation_id[:8]}... (用户: {user_id})")
                logger.debug(f"📊 [Supabase保存] 返回数据: {len(result.data)} 条记录")
                return True
            else:
                logger.error(f"❌ [Supabase保存] 返回数据为空: {conversation.conversation_id[:8]}...")
                return False
            
        except Exception as e:
            logger.error(f"❌ [Supabase保存] 失败 {conversation.conversation_id[:8]}...: {str(e)}")
            logger.debug(f"🔧 [Supabase保存] 详细错误: {type(e).__name__}: {e}")
            
            # 🔧 特殊错误处理
            if "constraint" in str(e).lower():
                logger.error(f"🔧 [Supabase保存] 约束错误，可能需要检查数据库结构")
            elif "rls" in str(e).lower():
                logger.error(f"🔧 [Supabase保存] RLS策略错误，可能用户上下文设置失败")
            
            return False
    
    async def load_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """从Supabase加载对话（用户隔离）"""
        if not self.is_available:
            logger.warning(f"🔇 [Supabase加载] 服务不可用，跳过加载 {conversation_id[:8]}...")
            return None
        
        try:
            # 🔧 修复：确保用户存在（解决外键约束问题）
            await self._ensure_user_exists(user_id)
            
            # 🔧 调试：设置用户上下文
            context_set = self.set_user_context(user_id)
            if not context_set:
                logger.warning(f"⚠️ [Supabase加载] 用户上下文设置失败: {user_id}")
            
            logger.debug(f"📖 [Supabase加载] 查询对话: {conversation_id[:8]}... (用户: {user_id})")
            
            result = self.supabase.table("conversations").select("*").eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).single().execute()
            
            if not result.data:
                logger.debug(f"📭 [Supabase加载] 对话不存在: {conversation_id[:8]}... (用户: {user_id})")
                return None
            
            # 🔧 修复：从简化的数据结构重建对话对象
            row_data = result.data
            
            # 重建对话元数据
            from models.conversation import ConversationMetadata
            metadata = ConversationMetadata(
                title=row_data.get("title", ""),
                created_at=datetime.fromisoformat(row_data["created_at"]),
                updated_at=datetime.fromisoformat(row_data["updated_at"]),
                last_activity=datetime.fromisoformat(row_data["last_activity"]),
                message_count=row_data.get("message_count", 0),
                tags=row_data.get("tags", []),
                is_archived=row_data.get("is_archived", False)
            )
            
            # 重建对话对象（暂时不加载消息，提高性能）
            conversation = Conversation(
                conversation_id=row_data["conversation_id"],
                messages=[],  # 消息按需加载
                metadata=metadata
            )
            
            logger.debug(f"✅ [Supabase加载] 对话加载成功: {conversation_id[:8]}... (用户: {user_id})")
            return conversation
            
        except Exception as e:
            logger.debug(f"📭 [Supabase加载] 加载失败 {conversation_id[:8]}... (用户: {user_id}): {str(e)}")
            logger.debug(f"🔧 [Supabase加载] 详细错误: {type(e).__name__}: {e}")
            return None
    
    async def list_conversations(self, user_id: str, limit: int = 20, offset: int = 0) -> List[ConversationSummary]:
        """列出用户的对话摘要"""
        if not self.is_available:
            return []
        
        try:
            result = self.supabase.table("conversations").select(
                "conversation_id,title,created_at,updated_at,message_count,last_activity,tags,is_archived"
            ).eq(
                "user_id", user_id
            ).order(
                "last_activity", desc=True
            ).range(offset, offset + limit - 1).execute()
            
            summaries = []
            for row in result.data:
                # 生成预览内容
                preview = ""
                try:
                    full_conv = await self.load_conversation(row["conversation_id"], user_id)
                    if full_conv and full_conv.messages:
                        last_msg = full_conv.messages[-1]
                        preview = last_msg.content[:100]
                        if len(last_msg.content) > 100:
                            preview += "..."
                except:
                    pass
                
                summary = ConversationSummary(
                    conversation_id=row["conversation_id"],
                    title=row["title"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    message_count=row["message_count"],
                    last_activity=datetime.fromisoformat(row["last_activity"]),
                    tags=row.get("tags", []),
                    is_archived=row.get("is_archived", False),
                    preview=preview
                )
                summaries.append(summary)
            
            return summaries
            
        except Exception as e:
            logger.error(f"列出对话失败 (用户: {user_id}): {e}")
            return []
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """删除用户的对话"""
        if not self.is_available:
            return False
        
        try:
            result = self.supabase.table("conversations").delete().eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).execute()
            
            logger.info(f"对话删除成功: {conversation_id} (用户: {user_id})")
            return True
            
        except Exception as e:
            logger.error(f"删除对话失败 {conversation_id} (用户: {user_id}): {e}")
            return False
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户的对话统计"""
        if not self.is_available:
            return {}
        
        try:
            # 获取总数
            total_result = self.supabase.table("conversations").select(
                "conversation_id", count="exact"
            ).eq("user_id", user_id).execute()
            
            # 获取活跃对话数
            active_result = self.supabase.table("conversations").select(
                "conversation_id", count="exact"
            ).eq("user_id", user_id).eq("is_archived", False).execute()
            
            # 获取消息总数
            messages_result = self.supabase.table("conversations").select(
                "message_count"
            ).eq("user_id", user_id).execute()
            
            total_messages = sum(row.get("message_count", 0) for row in messages_result.data)
            total_conversations = total_result.count or 0
            active_conversations = active_result.count or 0
            
            return {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "archived_conversations": total_conversations - active_conversations,
                "total_messages": total_messages,
                "average_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"获取用户统计失败 (用户: {user_id}): {e}")
            return {}
    
    async def cleanup_old_conversations(self, user_id: str, days: int = 30) -> int:
        """清理用户的旧对话"""
        if not self.is_available:
            return 0
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            result = self.supabase.table("conversations").delete().eq(
                "user_id", user_id
            ).lt(
                "last_activity", cutoff_date
            ).execute()
            
            deleted_count = len(result.data) if result.data else 0
            logger.info(f"清理完成，删除 {deleted_count} 个过期对话 (用户: {user_id})")
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理对话失败 (用户: {user_id}): {e}")
            return 0
    
    def set_user_context(self, user_id: str) -> bool:
        """设置用户上下文以支持RLS策略"""
        if not self.is_available:
            logger.warning(f"🔇 [用户上下文] Supabase不可用，跳过用户上下文设置: {user_id}")
            return False
        
        try:
            logger.debug(f"🔧 [用户上下文] 设置用户上下文: {user_id}")
            
            # 调用数据库函数设置用户上下文
            result = self.supabase.rpc('set_user_context', {
                'target_user_id': user_id
            }).execute()
            
            # 🔧 调试：检查RPC调用结果
            if result:
                logger.debug(f"✅ [用户上下文] RPC调用成功: {user_id}")
                logger.debug(f"📊 [用户上下文] RPC返回: {result}")
                
                # 验证上下文是否真正设置成功
                try:
                    verify_result = self.supabase.rpc('current_setting', {
                        'setting_name': 'app.current_user_id'
                    }).execute()
                    logger.debug(f"🔍 [用户上下文] 验证结果: {verify_result}")
                except Exception as verify_error:
                    logger.debug(f"⚠️ [用户上下文] 无法验证上下文设置: {verify_error}")
                
                return True
            else:
                logger.warning(f"⚠️ [用户上下文] RPC调用返回空结果: {user_id}")
                return False
            
        except Exception as e:
            logger.error(f"❌ [用户上下文] 设置失败 (用户: {user_id}): {str(e)}")
            logger.debug(f"🔧 [用户上下文] 详细错误: {type(e).__name__}: {e}")
            
            # 🔧 特殊错误处理
            if "function" in str(e).lower() and "does not exist" in str(e).lower():
                logger.error(f"🔧 [用户上下文] set_user_context函数不存在，请检查SQL配置")
            
            return False
    
    async def _ensure_user_exists(self, user_id: str) -> bool:
        """确保用户在数据库中存在（解决外键约束问题）"""
        if not self.is_available:
            return False
        
        try:
            logger.debug(f"🔍 [用户检查] 检查用户是否存在: {user_id}")
            
            # 检查用户是否已存在
            result = self.supabase.table("users").select("id").eq("id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                logger.debug(f"✅ [用户检查] 用户已存在: {user_id}")
                return True
            
            # 用户不存在，创建新用户
            logger.info(f"🆕 [用户创建] 创建新用户: {user_id}")
            
            user_data = {
                "id": user_id,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat()
            }
            
            # 🔧 修复：允许自动创建用户（开发阶段）
            # 用户应该已经通过前端内测码验证，这里只是确保数据库记录存在
            try:
                create_result = self.supabase.table("users").insert(user_data).execute()
                if create_result.data:
                    logger.info(f"✅ [用户创建] 用户创建成功: {user_id}")
                    return True
                else:
                    logger.error(f"❌ [用户创建] 创建失败，返回数据为空: {user_id}")
                    return False
            except Exception as create_error:
                create_error_str = str(create_error)
                # 如果是重复键错误，说明用户已存在（并发创建场景）
                if "duplicate key" in create_error_str.lower() or "unique constraint" in create_error_str.lower() or "23505" in create_error_str:
                    logger.info(f"✅ [用户创建] 用户已存在（并发创建）: {user_id}")
                    return True
                else:
                    logger.error(f"❌ [用户创建] 创建用户失败 {user_id}: {create_error_str}")
                    return False
                
        except Exception as e:
            error_str = str(e)
            logger.debug(f"🔧 [用户检查] 详细错误: {type(e).__name__}: {e}")
            
            # 如果是重复键错误，说明用户已存在（并发创建场景）
            if "duplicate key" in error_str.lower() or "unique constraint" in error_str.lower() or "23505" in error_str:
                logger.info(f"✅ [用户检查] 用户已存在（并发创建）: {user_id}")
                return True
            
            logger.error(f"❌ [用户检查] 检查/创建用户失败 {user_id}: {error_str}")
            return False


# 全局同步管理器实例
_sync_manager: Optional[SupabaseSyncManager] = None


async def get_sync_manager() -> SupabaseSyncManager:
    """获取Supabase同步管理器实例"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SupabaseSyncManager()
    return _sync_manager


async def init_sync_manager() -> SupabaseSyncManager:
    """初始化Supabase同步管理器"""
    global _sync_manager
    _sync_manager = SupabaseSyncManager()
    return _sync_manager


# 数据库表结构SQL（用于初始化）
SUPABASE_SCHEMA = """
-- 用户表（支持内测码验证的用户）
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 对话表（支持RLS用户隔离）
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    tags TEXT[] DEFAULT '{}',
    is_archived BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- 复合唯一约束
    UNIQUE(conversation_id, user_id)
);

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_last_activity ON conversations(last_activity DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_active ON conversations(user_id, is_archived, last_activity DESC);

-- 启用RLS（行级安全）
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- 用户上下文设置函数
CREATE OR REPLACE FUNCTION set_user_context(target_user_id TEXT)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_user_id', target_user_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 获取当前用户上下文函数
CREATE OR REPLACE FUNCTION get_current_user_id()
RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('app.current_user_id', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 🔧 简化的RLS策略（开发阶段，允许所有操作）
-- 生产环境应该使用更严格的策略
CREATE POLICY IF NOT EXISTS "开发阶段_允许所有用户操作" ON users
    FOR ALL USING (true);

CREATE POLICY IF NOT EXISTS "开发阶段_允许所有对话操作" ON conversations
    FOR ALL USING (true);

-- 注释掉的生产环境RLS策略（供参考）
-- CREATE POLICY "生产_用户只能访问自己的数据" ON users
--     FOR ALL USING (auth.jwt() ->> 'sub' = id OR get_current_user_id() = id);
-- 
-- CREATE POLICY "生产_用户只能访问自己的对话" ON conversations
--     FOR ALL USING (auth.jwt() ->> 'sub' = user_id OR get_current_user_id() = user_id);
"""