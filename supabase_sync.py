"""
Paper God Beta3 - Supabase同步管理器
支持用户数据隔离和RLS安全策略的云端对话存储
"""

import os
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

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
            return False
        
        try:
            conversation_data = {
                "conversation_id": conversation.conversation_id,
                "user_id": user_id,  # 用户隔离字段
                "title": conversation.metadata.title,
                "created_at": conversation.metadata.created_at.isoformat(),
                "updated_at": conversation.metadata.updated_at.isoformat(),
                "last_activity": conversation.metadata.last_activity.isoformat(),
                "message_count": conversation.metadata.message_count,
                "tags": conversation.metadata.tags,
                "is_archived": conversation.metadata.is_archived,
                "conversation_data": conversation.dict()  # 完整对话数据
            }
            
            # 使用upsert确保幂等性
            result = self.supabase.table("conversations").upsert(
                conversation_data,
                on_conflict="conversation_id,user_id"
            ).execute()
            
            logger.debug(f"对话保存成功: {conversation.conversation_id} (用户: {user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Supabase保存失败 {conversation.conversation_id}: {e}")
            return False
    
    async def load_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """从Supabase加载对话（用户隔离）"""
        if not self.is_available:
            return None
        
        try:
            result = self.supabase.table("conversations").select("*").eq(
                "conversation_id", conversation_id
            ).eq(
                "user_id", user_id
            ).single().execute()
            
            if not result.data:
                return None
            
            # 从conversation_data字段恢复完整对话对象
            conversation_dict = result.data.get("conversation_data", {})
            if not conversation_dict:
                logger.error(f"对话数据为空: {conversation_id}")
                return None
            
            conversation = Conversation.parse_obj(conversation_dict)
            logger.debug(f"对话加载成功: {conversation_id} (用户: {user_id})")
            return conversation
            
        except Exception as e:
            logger.debug(f"Supabase加载失败 {conversation_id} (用户: {user_id}): {e}")
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
            logger.warning("Supabase不可用，跳过用户上下文设置")
            return False
        
        try:
            # 调用数据库函数设置用户上下文
            result = self.supabase.rpc('set_user_context', {
                'target_user_id': user_id
            }).execute()
            
            logger.debug(f"用户上下文设置成功: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"设置用户上下文失败 (用户: {user_id}): {e}")
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
-- 对话表（支持RLS用户隔离）
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    tags TEXT[] DEFAULT '{}',
    is_archived BOOLEAN DEFAULT FALSE,
    conversation_data JSONB NOT NULL,
    
    -- 复合唯一约束
    UNIQUE(conversation_id, user_id)
);

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_last_activity ON conversations(last_activity DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_active ON conversations(user_id, is_archived, last_activity DESC);

-- 启用RLS（行级安全）
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- RLS策略：用户只能访问自己的数据
CREATE POLICY IF NOT EXISTS "用户只能访问自己的对话" ON conversations
    FOR ALL USING (auth.jwt() ->> 'sub' = user_id);

-- 允许匿名用户使用临时user_id（开发阶段）
CREATE POLICY IF NOT EXISTS "允许匿名用户访问" ON conversations
    FOR ALL USING (true);
"""