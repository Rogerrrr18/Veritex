import json
import os
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

from models.conversation import (
    Conversation, ChatMessage, ConversationSummary, 
    ConversationMetadata, ConversationCreateRequest
)

logger = logging.getLogger(__name__)


class ConversationManager:
    """对话管理器 - 负责会话的创建、存储、检索和管理"""
    
    def __init__(self, storage_dir: str = "./conversations"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        # 内存缓存，提升性能
        self._memory_cache: Dict[str, Conversation] = {}
        self._cache_max_size = 100
        self._cache_ttl = timedelta(hours=1)  # 缓存1小时
        self._last_cleanup = datetime.now()
        
        logger.info(f"对话管理器初始化完成，存储目录: {self.storage_dir}")
    
    async def create_conversation(self, request: Optional[ConversationCreateRequest] = None) -> Conversation:
        """创建新对话"""
        conversation = Conversation()
        
        if request:
            if request.title:
                conversation.metadata.title = request.title
            
            if request.initial_message:
                conversation.add_message("user", request.initial_message)
        
        # 保存到文件系统
        await self._save_conversation(conversation)
        
        # 添加到内存缓存
        self._memory_cache[conversation.conversation_id] = conversation
        
        logger.info(f"创建新对话: {conversation.conversation_id}")
        return conversation
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取对话"""
        # 先检查内存缓存
        if conversation_id in self._memory_cache:
            conversation = self._memory_cache[conversation_id]
            # 更新最后活跃时间
            conversation.metadata.last_activity = datetime.now()
            return conversation
        
        # 从文件系统加载
        conversation_file = self.storage_dir / f"{conversation_id}.json"
        if not conversation_file.exists():
            logger.warning(f"对话不存在: {conversation_id}")
            return None
        
        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            conversation = Conversation.parse_obj(data)
            conversation.metadata.last_activity = datetime.now()
            
            # 添加到内存缓存
            self._add_to_cache(conversation)
            
            return conversation
            
        except Exception as e:
            logger.error(f"加载对话失败 {conversation_id}: {e}")
            return None
    
    async def update_conversation(self, conversation: Conversation) -> bool:
        """更新对话"""
        try:
            # 更新内存缓存
            self._memory_cache[conversation.conversation_id] = conversation
            
            # 保存到文件系统
            await self._save_conversation(conversation)
            
            logger.debug(f"对话更新成功: {conversation.conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新对话失败 {conversation.conversation_id}: {e}")
            return False
    
    async def add_message_to_conversation(
        self, 
        conversation_id: str, 
        role: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Conversation]:
        """向对话添加消息"""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        conversation.add_message(role, content, metadata)
        await self.update_conversation(conversation)
        
        return conversation
    
    async def list_conversations(
        self, 
        limit: int = 20, 
        offset: int = 0,
        archived: Optional[bool] = None,
        search_query: Optional[str] = None
    ) -> List[ConversationSummary]:
        """列出对话摘要"""
        conversation_files = list(self.storage_dir.glob("*.json"))
        conversations = []
        
        for file_path in conversation_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                conversation = Conversation.parse_obj(data)
                
                # 过滤条件
                if archived is not None and conversation.metadata.is_archived != archived:
                    continue
                
                if search_query and search_query.lower() not in (conversation.metadata.title or "").lower():
                    # 也搜索消息内容
                    if not any(search_query.lower() in msg.get('content', '').lower() 
                             for msg in data.get('messages', [])):
                        continue
                
                # 创建摘要
                preview = ""
                if conversation.messages:
                    last_msg = conversation.messages[-1]
                    preview = last_msg.content[:100]
                    if len(last_msg.content) > 100:
                        preview += "..."
                
                summary = ConversationSummary(
                    conversation_id=conversation.conversation_id,
                    title=conversation.metadata.title,
                    created_at=conversation.metadata.created_at,
                    updated_at=conversation.metadata.updated_at,
                    message_count=conversation.metadata.message_count,
                    last_activity=conversation.metadata.last_activity,
                    tags=conversation.metadata.tags,
                    is_archived=conversation.metadata.is_archived,
                    preview=preview
                )
                
                conversations.append(summary)
                
            except Exception as e:
                logger.error(f"加载对话摘要失败 {file_path}: {e}")
                continue
        
        # 按最后活跃时间排序
        conversations.sort(key=lambda x: x.last_activity, reverse=True)
        
        # 分页
        return conversations[offset:offset + limit]
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话"""
        try:
            # 从内存缓存移除
            self._memory_cache.pop(conversation_id, None)
            
            # 删除文件
            conversation_file = self.storage_dir / f"{conversation_id}.json"
            if conversation_file.exists():
                conversation_file.unlink()
            
            logger.info(f"对话删除成功: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除对话失败 {conversation_id}: {e}")
            return False
    
    async def archive_conversation(self, conversation_id: str) -> bool:
        """归档对话"""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False
        
        conversation.metadata.is_archived = True
        return await self.update_conversation(conversation)
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """获取对话统计信息"""
        conversation_files = list(self.storage_dir.glob("*.json"))
        
        total_conversations = len(conversation_files)
        active_conversations = 0
        archived_conversations = 0
        total_messages = 0
        
        for file_path in conversation_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                is_archived = data.get('metadata', {}).get('is_archived', False)
                message_count = data.get('metadata', {}).get('message_count', 0)
                
                if is_archived:
                    archived_conversations += 1
                else:
                    active_conversations += 1
                
                total_messages += message_count
                
            except Exception as e:
                logger.error(f"统计对话失败 {file_path}: {e}")
                continue
        
        return {
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "archived_conversations": archived_conversations,
            "total_messages": total_messages,
            "average_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0,
            "cache_size": len(self._memory_cache),
            "storage_directory": str(self.storage_dir)
        }
    
    async def cleanup_old_conversations(self, days: int = 30) -> int:
        """清理旧对话"""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        conversation_files = list(self.storage_dir.glob("*.json"))
        
        for file_path in conversation_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                last_activity_str = data.get('metadata', {}).get('last_activity')
                if last_activity_str:
                    last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
                    if last_activity < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"清理过期对话: {file_path.stem}")
                
            except Exception as e:
                logger.error(f"清理对话失败 {file_path}: {e}")
                continue
        
        logger.info(f"清理完成，删除 {deleted_count} 个过期对话")
        return deleted_count
    
    async def _save_conversation(self, conversation: Conversation):
        """保存对话到文件系统"""
        conversation_file = self.storage_dir / f"{conversation.conversation_id}.json"
        
        # 确保元数据更新
        conversation.metadata.updated_at = datetime.now()
        
        with open(conversation_file, 'w', encoding='utf-8') as f:
            json.dump(conversation.dict(), f, ensure_ascii=False, indent=2, default=str)
    
    def _add_to_cache(self, conversation: Conversation):
        """添加对话到内存缓存"""
        # 清理过期缓存
        self._cleanup_cache()
        
        # 如果缓存满了，移除最老的条目
        if len(self._memory_cache) >= self._cache_max_size:
            oldest_id = min(self._memory_cache.keys(), 
                           key=lambda x: self._memory_cache[x].metadata.last_activity)
            self._memory_cache.pop(oldest_id, None)
        
        self._memory_cache[conversation.conversation_id] = conversation
    
    def _cleanup_cache(self):
        """清理过期的内存缓存"""
        now = datetime.now()
        if now - self._last_cleanup < timedelta(minutes=10):  # 每10分钟清理一次
            return
        
        expired_ids = [
            conv_id for conv_id, conv in self._memory_cache.items()
            if now - conv.metadata.last_activity > self._cache_ttl
        ]
        
        for conv_id in expired_ids:
            self._memory_cache.pop(conv_id, None)
        
        self._last_cleanup = now
        
        if expired_ids:
            logger.debug(f"清理过期缓存: {len(expired_ids)} 个对话")


# 全局对话管理器实例
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """获取对话管理器实例"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager


async def init_conversation_manager(storage_dir: str = "./conversations") -> ConversationManager:
    """初始化对话管理器"""
    global _conversation_manager
    _conversation_manager = ConversationManager(storage_dir)
    return _conversation_manager