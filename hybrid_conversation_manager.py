"""
Paper God Beta3 - 混合对话管理器（简化版）
整合双层架构：内存缓存 + Supabase云端存储 + JSON备用
支持用户数据完全隔离，向后兼容现有API接口，专为Docker部署优化
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# 现有模块导入
from conversation_manager import ConversationManager
from supabase_sync import SupabaseSyncManager, get_sync_manager

# 数据模型导入
from models.conversation import (
    Conversation, ChatMessage, ConversationSummary, 
    ConversationMetadata, ConversationCreateRequest
)

logger = logging.getLogger(__name__)


class HybridConversationManager:
    """混合对话管理器 - 云端+JSON备用的简化架构"""
    
    def __init__(self, 
                 enable_supabase: bool = True,
                 fallback_to_json: bool = True):
        """
        初始化混合管理器
        
        Args:
            enable_supabase: 是否启用Supabase云端同步
            fallback_to_json: 是否在云端服务不可用时回退到JSON文件存储
        """
        self.enable_supabase = enable_supabase
        self.fallback_to_json = fallback_to_json
        
        # 内存缓存（第一层）
        self._memory_cache: Dict[str, Conversation] = {}
        self._memory_cache_max_size = 100
        self._memory_cache_ttl = timedelta(hours=1)
        self._last_memory_cleanup = datetime.now()
        
        # 模块实例
        self._sync_manager: Optional[SupabaseSyncManager] = None
        self._json_manager: Optional[ConversationManager] = None
        
        # 性能统计
        self.stats = {
            'cache_hits': {'memory': 0, 'cloud': 0, 'json': 0},
            'cache_misses': {'memory': 0, 'cloud': 0, 'json': 0},
            'sync_operations': {'success': 0, 'failed': 0},
            'fallback_operations': 0
        }
        
        logger.info("混合对话管理器初始化完成")
    
    async def initialize(self):
        """异步初始化所有组件"""
        try:
            # 初始化Supabase同步
            if self.enable_supabase:
                try:
                    self._sync_manager = await get_sync_manager()
                    # 测试云端连接
                    if self._sync_manager.is_available:
                        logger.info("Supabase云端同步初始化完成")
                    else:
                        logger.warning("Supabase连接测试失败，将使用本地模式")
                        self.enable_supabase = False
                except Exception as e:
                    logger.error(f"Supabase初始化失败: {e}")
                    self.enable_supabase = False
            
            # 初始化JSON文件管理器（作为备用）
            if self.fallback_to_json:
                self._json_manager = ConversationManager()
                logger.info("JSON文件管理器初始化完成（作为备用）")
            
            logger.info(f"混合管理器组件状态 - Supabase: {self.enable_supabase}, JSON备用: {self.fallback_to_json}")
                       
        except Exception as e:
            logger.error(f"混合管理器初始化失败: {e}")
            raise
    
    async def create_conversation(self, user_id: str, request: Optional[ConversationCreateRequest] = None) -> Conversation:
        """创建新对话（支持用户隔离）"""
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
            
            # 缓存到内存
            cache_key = f"{user_id}:{conversation_id}"
            self._memory_cache[cache_key] = conversation
            
            # 缓存到内存层
            await self._cache_conversation_locally(conversation, user_id, cache_key)
            
            # 同步到云端（如果启用）
            if self.enable_supabase and self._sync_manager:
                asyncio.create_task(self._sync_manager.save_conversation(conversation, user_id))
            
            logger.debug(f"对话创建成功: {conversation_id} (用户: {user_id})")
            return conversation
            
        except Exception as e:
            logger.error(f"创建对话失败: {e}")
            raise
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """获取对话（三层缓存查找）"""
        cache_key = f"{user_id}:{conversation_id}"
        
        try:
            # 第一层：内存缓存
            if cache_key in self._memory_cache:
                self.stats['cache_hits']['memory'] += 1
                logger.debug(f"内存缓存命中: {conversation_id}")
                return self._memory_cache[cache_key]
            
            self.stats['cache_misses']['memory'] += 1
            
            # 第二层：Supabase云端存储
            if self.enable_supabase and self._sync_manager:
                conversation = await self._sync_manager.load_conversation(conversation_id, user_id)
                if conversation:
                    self.stats['cache_hits']['cloud'] += 1
                    # 回写到本地缓存层
                    await self._cache_conversation_locally(conversation, user_id, cache_key)
                    logger.debug(f"云端缓存命中: {conversation_id}")
                    return conversation
                
                self.stats['cache_misses']['cloud'] += 1
            
            # 第三层：JSON文件备用（向后兼容）
            if self.fallback_to_json and self._json_manager:
                conversation = await self._json_manager.get_conversation(conversation_id)
                if conversation:
                    self.stats['cache_hits']['json'] += 1
                    self.stats['fallback_operations'] += 1
                    # 回写到缓存层
                    await self._cache_conversation_locally(conversation, user_id, cache_key)
                    logger.debug(f"JSON备用命中: {conversation_id}")
                    return conversation
                
                self.stats['cache_misses']['json'] += 1
            
            logger.debug(f"对话不存在: {conversation_id} (用户: {user_id})")
            return None
            
        except Exception as e:
            logger.error(f"获取对话失败: {e}")
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
            
            # 添加消息到对话
            conversation.messages.append(message)
            conversation.metadata.message_count = len(conversation.messages)
            conversation.metadata.updated_at = datetime.now()
            conversation.metadata.last_activity = datetime.now()
            
            # 更新对话并返回更新后的对话对象
            success = await self.update_conversation(conversation, user_id)
            if success:
                return conversation  # 返回更新后的对话对象
            else:
                return None
            
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            return None
    
    async def update_conversation(self, conversation: Conversation, user_id: str) -> bool:
        """更新对话到所有存储层"""
        try:
            cache_key = f"{user_id}:{conversation.conversation_id}"
            
            # 更新内存缓存
            self._memory_cache[cache_key] = conversation
            logger.debug(f"📝 [内存] 对话已更新: {conversation.conversation_id[:8]}...")
            
            # 异步更新其他层
            tasks = []
            task_names = []
            
            # 🔧 修复：确保Supabase同步始终被触发
            if self.enable_supabase and self._sync_manager:
                logger.debug(f"🚀 [Supabase] 开始同步对话: {conversation.conversation_id[:8]}...")
                task = self._sync_manager.save_conversation(conversation, user_id)
                tasks.append(task)
                task_names.append("Supabase同步")
            
            # JSON备用（如果启用）- 修正：不重复添加消息
            if self.fallback_to_json and self._json_manager:
                # 这里应该更新整个对话，而不是添加单个消息
                try:
                    # 将混合管理器的对话保存到JSON管理器
                    await self._json_manager._save_conversation_to_file(conversation)
                    task_names.append("JSON备用")
                    logger.debug(f"💾 [JSON] 对话已备份")
                except Exception as e:
                    logger.warning(f"JSON备用保存失败: {e}")
            
            # 并发执行更新
            if tasks:
                logger.debug(f"🔄 [同步] 执行 {len(tasks)} 个同步任务: {', '.join(task_names)}")
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                success_count = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"❌ [{task_names[i]}] 同步失败: {result}")
                        self.stats['sync_operations']['failed'] += 1
                    else:
                        logger.debug(f"✅ [{task_names[i]}] 同步成功")
                        success_count += 1
                        self.stats['sync_operations']['success'] += 1
                
                logger.info(f"🎯 [同步完成] 成功: {success_count}/{len(tasks)}, 对话: {conversation.conversation_id[:8]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"更新对话失败: {e}")
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")
            return False
    
    async def list_conversations(self, user_id: str, limit: int = 20, offset: int = 0, 
                               archived: Optional[bool] = None, search_query: Optional[str] = None) -> List[ConversationSummary]:
        """列出用户对话（优先从云端获取）"""
        try:
            # 优先从云端获取最新数据
            if self.enable_supabase and self._sync_manager:
                try:
                    summaries = await self._sync_manager.list_conversations(
                        user_id=user_id,
                        limit=limit,
                        offset=offset
                    )
                    if summaries:
                        logger.debug(f"从云端获取对话列表: {len(summaries)}个对话")
                        return summaries
                except Exception as e:
                    logger.warning(f"云端获取对话列表失败: {e}")
            
            # 回退到JSON（兼容性）
            if self.fallback_to_json and self._json_manager:
                try:
                    conversations = await self._json_manager.list_conversations(
                        limit=limit,
                        offset=offset,
                        archived=archived,
                        search_query=search_query
                    )
                    # 转换为ConversationSummary格式
                    summaries = []
                    for conv in conversations:
                        summary = ConversationSummary(
                            conversation_id=conv.conversation_id,
                            title=conv.metadata.title,
                            created_at=conv.metadata.created_at,
                            updated_at=conv.metadata.updated_at,
                            last_activity=conv.metadata.last_activity,
                            message_count=conv.metadata.message_count,
                            tags=conv.metadata.tags,
                            is_archived=conv.metadata.is_archived,
                            preview=conv.messages[-1].content[:100] if conv.messages else ""
                        )
                        summaries.append(summary)
                    
                    self.stats['fallback_operations'] += 1
                    logger.debug(f"从JSON备用获取对话列表: {len(summaries)}个对话")
                    return summaries[:limit]  # 应用limit限制
                except Exception as e:
                    logger.warning(f"JSON备用获取对话列表失败: {e}")
            
            return []
            
        except Exception as e:
            logger.error(f"列出对话失败: {e}")
            return []
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """删除对话（从所有存储层）"""
        try:
            cache_key = f"{user_id}:{conversation_id}"
            
            # 从内存缓存删除
            self._memory_cache.pop(cache_key, None)
            
            # 异步从其他层删除
            tasks = []
            
            # 云端删除
            if self.enable_supabase and self._sync_manager:
                tasks.append(self._sync_manager.delete_conversation(conversation_id, user_id))
            
            # JSON备用删除
            if self.fallback_to_json and self._json_manager:
                tasks.append(self._json_manager.delete_conversation(conversation_id))
            
            # 并发执行删除
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if not isinstance(r, Exception))
                logger.debug(f"删除对话: {success_count}/{len(results)} 层成功")
            
            return True
            
        except Exception as e:
            logger.error(f"删除对话失败: {e}")
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
            return False
    
    async def get_conversation_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户对话统计信息"""
        try:
            stats = {
                'user_id': user_id,
                'total_conversations': 0,
                'active_conversations': 0,
                'archived_conversations': 0,
                'total_messages': 0,
                'cache_performance': self.stats.copy(),
                'storage_layers': {
                    'supabase_enabled': self.enable_supabase,
                    'json_fallback_enabled': self.fallback_to_json
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    async def _cache_conversation_locally(self, conversation: Conversation, user_id: str, cache_key: str):
        """将对话缓存到内存层"""
        try:
            # 添加到内存缓存
            self._memory_cache[cache_key] = conversation
                
        except Exception as e:
            logger.warning(f"内存缓存失败: {e}")


# 全局混合管理器实例
_hybrid_manager: Optional[HybridConversationManager] = None


async def get_hybrid_conversation_manager() -> HybridConversationManager:
    """获取混合对话管理器实例"""
    global _hybrid_manager
    if _hybrid_manager is None:
        _hybrid_manager = HybridConversationManager()
        await _hybrid_manager.initialize()
    return _hybrid_manager


# 向后兼容的便捷函数
async def create_conversation_with_user(user_id: str, request: Optional[ConversationCreateRequest] = None) -> Conversation:
    """便捷函数：创建带用户ID的对话"""
    manager = await get_hybrid_conversation_manager()
    return await manager.create_conversation(user_id, request)


async def get_conversation_with_user(conversation_id: str, user_id: str) -> Optional[Conversation]:
    """便捷函数：获取用户的对话"""
    manager = await get_hybrid_conversation_manager()
    return await manager.get_conversation(conversation_id, user_id)


async def add_message_with_user(conversation_id: str, user_id: str, role: str, content: str, 
                               metadata: Optional[Dict[str, Any]] = None) -> Optional[Conversation]:
    """便捷函数：向用户对话添加消息"""
    manager = await get_hybrid_conversation_manager()
    return await manager.add_message_to_conversation(conversation_id, user_id, role, content, metadata)