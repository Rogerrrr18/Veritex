"""
Paper God Beta3 - 统一对话管理器
简化架构：内存缓存 + Supabase云端存储
移除JSON文件备用存储，专注核心功能
"""

import asyncio
import logging
import uuid
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Supabase同步管理器
from supabase_sync import SupabaseSyncManager, get_sync_manager

# 数据模型
from models.conversation import (
    Conversation, ChatMessage, ConversationSummary, 
    ConversationMetadata, ConversationCreateRequest
)

logger = logging.getLogger(__name__)


class ConversationManager:
    """统一对话管理器 - 内存缓存 + Supabase云端存储"""
    
    def __init__(self):
        # 内存缓存配置
        self._memory_cache: Dict[str, Conversation] = {}
        self._cache_max_size = 100
        self._cache_ttl = timedelta(hours=1)
        self._last_cleanup = datetime.now()
        
        # Supabase同步管理器
        self._sync_manager: Optional[SupabaseSyncManager] = None
        self._initialized = False
        
        # 性能统计
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'supabase_saves': 0,
            'supabase_loads': 0,
            'errors': 0
        }
        
        logger.info("统一对话管理器初始化完成")
    
    async def initialize(self):
        """异步初始化Supabase连接"""
        if self._initialized:
            return
            
        try:
            self._sync_manager = await get_sync_manager()
            if self._sync_manager.is_available:
                logger.info("Supabase连接初始化成功")
            else:
                logger.warning("Supabase连接失败，将在内存模式下运行")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"对话管理器初始化失败: {e}")
            self._initialized = True  # 即使失败也标记为已初始化，避免重复尝试
    
    async def create_conversation(self, user_id: str, request: Optional[ConversationCreateRequest] = None) -> Conversation:
        """创建新对话"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 创建对话对象
            conversation_id = str(uuid.uuid4())
            now = datetime.now()
            
            title = request.title if request and request.title else f"对话 {now.strftime('%m-%d %H:%M')}"
            
            metadata = ConversationMetadata(
                title=title,
                created_at=now,
                updated_at=now,
                last_activity=now,
                message_count=0,
                tags=request.tags if request and request.tags else [],
                is_archived=False
            )
            
            conversation = Conversation(
                conversation_id=conversation_id,
                messages=[],
                metadata=metadata
            )
            
            # 如果有初始消息，添加它
            if request and request.initial_message:
                message = ChatMessage(
                    role="user",
                    content=request.initial_message,
                    timestamp=now,
                    metadata={}
                )
                conversation.messages.append(message)
                conversation.metadata.message_count = 1
            
            # 缓存到内存
            cache_key = f"{user_id}:{conversation_id}"
            self._memory_cache[cache_key] = conversation
            self._cleanup_cache_if_needed()
            
            # 同步到Supabase（异步）
            if self._sync_manager and self._sync_manager.is_available:
                asyncio.create_task(self._save_to_supabase(conversation, user_id))
            
            logger.info(f"对话创建成功: {conversation_id} (用户: {user_id})")
            return conversation
            
        except Exception as e:
            logger.error(f"创建对话失败: {e}")
            self.stats['errors'] += 1
            raise
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """获取对话（双层缓存查找）"""
        if not self._initialized:
            await self.initialize()
            
        cache_key = f"{user_id}:{conversation_id}"
        
        try:
            # 第一层：检查内存缓存
            if cache_key in self._memory_cache:
                self.stats['cache_hits'] += 1
                conversation = self._memory_cache[cache_key]
                # 更新最后活跃时间
                conversation.metadata.last_activity = datetime.now()
                logger.debug(f"内存缓存命中: {conversation_id[:8]}...")
                return conversation
            
            self.stats['cache_misses'] += 1
            
            # 第二层：从Supabase加载
            if self._sync_manager and self._sync_manager.is_available:
                conversation = await self._sync_manager.load_conversation(conversation_id, user_id)
                if conversation:
                    self.stats['supabase_loads'] += 1
                    # 缓存到内存
                    self._memory_cache[cache_key] = conversation
                    self._cleanup_cache_if_needed()
                    
                    conversation.metadata.last_activity = datetime.now()
                    logger.debug(f"Supabase加载成功: {conversation_id[:8]}...")
                    return conversation
            
            logger.debug(f"对话不存在: {conversation_id} (用户: {user_id})")
            return None
            
        except Exception as e:
            logger.error(f"获取对话失败: {e}")
            self.stats['errors'] += 1
            return None
    
    async def add_message_to_conversation(self, conversation_id: str, user_id: str, role: str, content: str, 
                                        metadata: Optional[Dict[str, Any]] = None) -> Optional[Conversation]:
        """向对话添加消息"""
        try:
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                logger.warning(f"对话不存在，无法添加消息: {conversation_id}")
                return None
            
            # 创建新消息
            message = ChatMessage(
                role=role,
                content=content,
                timestamp=datetime.now(),
                metadata=metadata or {}
            )
            
            # 添加到对话
            conversation.messages.append(message)
            conversation.metadata.message_count = len(conversation.messages)
            conversation.metadata.updated_at = datetime.now()
            conversation.metadata.last_activity = datetime.now()
            
            # 更新对话
            success = await self.update_conversation(conversation, user_id)
            return conversation if success else None
            
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            self.stats['errors'] += 1
            return None
    
    async def update_conversation(self, conversation: Conversation, user_id: str) -> bool:
        """更新对话到所有存储层"""
        try:
            cache_key = f"{user_id}:{conversation.conversation_id}"
            
            # 更新内存缓存
            self._memory_cache[cache_key] = conversation
            
            # 异步同步到Supabase
            if self._sync_manager and self._sync_manager.is_available:
                asyncio.create_task(self._save_to_supabase(conversation, user_id))
            
            logger.debug(f"对话更新成功: {conversation.conversation_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"更新对话失败: {e}")
            self.stats['errors'] += 1
            return False
    
    async def list_conversations(self, user_id: str, limit: int = 20, offset: int = 0) -> List[ConversationSummary]:
        """列出用户对话"""
        if not self._initialized:
            await self.initialize()
            
        try:
            # 优先从Supabase获取最新数据
            if self._sync_manager and self._sync_manager.is_available:
                summaries = await self._sync_manager.list_conversations(user_id, limit, offset)
                logger.debug(f"从Supabase获取对话列表: {len(summaries)}个对话")
                return summaries
            
            # 降级到内存缓存
            logger.warning("Supabase不可用，从内存缓存获取对话列表")
            return self._list_from_memory_cache(user_id, limit, offset)
            
        except Exception as e:
            logger.error(f"列出对话失败: {e}")
            self.stats['errors'] += 1
            return []
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """删除对话"""
        try:
            cache_key = f"{user_id}:{conversation_id}"
            
            # 从内存缓存删除
            self._memory_cache.pop(cache_key, None)
            
            # 从Supabase删除
            if self._sync_manager and self._sync_manager.is_available:
                await self._sync_manager.delete_conversation(conversation_id, user_id)
            
            logger.info(f"对话删除成功: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除对话失败: {e}")
            self.stats['errors'] += 1
            return False
    
    async def archive_conversation(self, conversation_id: str, user_id: str) -> bool:
        """归档对话"""
        try:
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                return False
            
            conversation.metadata.is_archived = True
            return await self.update_conversation(conversation, user_id)
            
        except Exception as e:
            logger.error(f"归档对话失败: {e}")
            self.stats['errors'] += 1
            return False
    
    async def get_conversation_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户对话统计"""
        try:
            stats = {
                'user_id': user_id,
                'performance': self.stats.copy(),
                'cache_size': len(self._memory_cache),
                'supabase_available': self._sync_manager.is_available if self._sync_manager else False
            }
            
            # 如果Supabase可用，获取详细统计
            if self._sync_manager and self._sync_manager.is_available:
                supabase_stats = await self._sync_manager.get_user_stats(user_id)
                stats.update(supabase_stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            self.stats['errors'] += 1
            return {}
    
    async def _save_to_supabase(self, conversation: Conversation, user_id: str):
        """异步保存到Supabase（带错误处理）"""
        try:
            if self._sync_manager:
                # 设置用户上下文
                self._sync_manager.set_user_context(user_id)
                
                success = await self._sync_manager.save_conversation(conversation, user_id)
                if success:
                    self.stats['supabase_saves'] += 1
                    logger.debug(f"Supabase保存成功: {conversation.conversation_id[:8]}...")
                else:
                    logger.warning(f"Supabase保存失败: {conversation.conversation_id[:8]}...")
                    
        except Exception as e:
            logger.error(f"Supabase保存异常: {e}")
            self.stats['errors'] += 1
    
    def _list_from_memory_cache(self, user_id: str, limit: int, offset: int) -> List[ConversationSummary]:
        """从内存缓存生成对话列表（降级功能）"""
        try:
            summaries = []
            user_conversations = [
                conv for cache_key, conv in self._memory_cache.items()
                if cache_key.startswith(f"{user_id}:")
            ]
            
            # 按最后活跃时间排序
            user_conversations.sort(key=lambda x: x.metadata.last_activity, reverse=True)
            
            # 分页
            for conv in user_conversations[offset:offset + limit]:
                preview = ""
                if conv.messages:
                    last_msg = conv.messages[-1]
                    preview = last_msg.content[:100]
                    if len(last_msg.content) > 100:
                        preview += "..."
                
                summary = ConversationSummary(
                    conversation_id=conv.conversation_id,
                    title=conv.metadata.title,
                    created_at=conv.metadata.created_at,
                    updated_at=conv.metadata.updated_at,
                    message_count=conv.metadata.message_count,
                    last_activity=conv.metadata.last_activity,
                    tags=conv.metadata.tags,
                    is_archived=conv.metadata.is_archived,
                    preview=preview
                )
                summaries.append(summary)
            
            return summaries
            
        except Exception as e:
            logger.error(f"内存缓存列表生成失败: {e}")
            return []
    
    def _cleanup_cache_if_needed(self):
        """按需清理内存缓存"""
        now = datetime.now()
        
        # 每10分钟清理一次过期缓存
        if now - self._last_cleanup > timedelta(minutes=10):
            self._cleanup_expired_cache()
            self._last_cleanup = now
        
        # 如果缓存满了，移除最老的条目
        if len(self._memory_cache) >= self._cache_max_size:
            oldest_key = min(self._memory_cache.keys(), 
                           key=lambda k: self._memory_cache[k].metadata.last_activity)
            self._memory_cache.pop(oldest_key, None)
            logger.debug("清理最老缓存条目以释放空间")
    
    def _cleanup_expired_cache(self):
        """清理过期的内存缓存"""
        now = datetime.now()
        expired_keys = [
            key for key, conv in self._memory_cache.items()
            if now - conv.metadata.last_activity > self._cache_ttl
        ]
        
        for key in expired_keys:
            self._memory_cache.pop(key, None)
        
        if expired_keys:
            logger.debug(f"清理过期缓存: {len(expired_keys)} 个对话")


# 全局对话管理器实例
_conversation_manager: Optional[ConversationManager] = None


async def get_conversation_manager() -> ConversationManager:
    """获取对话管理器实例"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
        await _conversation_manager.initialize()
    return _conversation_manager


# 便捷函数（保持API兼容性）
async def create_conversation_with_user(user_id: str, request: Optional[ConversationCreateRequest] = None) -> Conversation:
    """便捷函数：创建带用户ID的对话"""
    manager = await get_conversation_manager()
    return await manager.create_conversation(user_id, request)


async def get_conversation_with_user(conversation_id: str, user_id: str) -> Optional[Conversation]:
    """便捷函数：获取用户的对话"""
    manager = await get_conversation_manager()
    return await manager.get_conversation(conversation_id, user_id)


async def add_message_with_user(conversation_id: str, user_id: str, role: str, content: str, 
                               metadata: Optional[Dict[str, Any]] = None) -> Optional[Conversation]:
    """便捷函数：向用户对话添加消息"""
    manager = await get_conversation_manager()
    return await manager.add_message_to_conversation(conversation_id, user_id, role, content, metadata)