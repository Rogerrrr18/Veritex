from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class ChatMessage(BaseModel):
    """对话消息模型"""
    role: str = Field(..., description="消息角色: user/assistant")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="消息时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="消息元数据")


class ConversationMetadata(BaseModel):
    """对话元数据"""
    title: Optional[str] = Field(default=None, description="对话标题")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    message_count: int = Field(default=0, description="消息总数")
    last_activity: datetime = Field(default_factory=datetime.now, description="最后活跃时间")
    tags: List[str] = Field(default_factory=list, description="对话标签")
    is_archived: bool = Field(default=False, description="是否已归档")


class Conversation(BaseModel):
    """完整对话模型"""
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="对话ID")
    messages: List[ChatMessage] = Field(default_factory=list, description="消息列表")
    metadata: ConversationMetadata = Field(default_factory=ConversationMetadata, description="对话元数据")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """添加新消息"""
        message = ChatMessage(
            role=role,
            content=content,
            metadata=metadata
        )
        self.messages.append(message)
        
        # 更新对话元数据
        self.metadata.updated_at = datetime.now()
        self.metadata.last_activity = datetime.now()
        self.metadata.message_count = len(self.messages)
        
        # 自动生成对话标题（基于第一条用户消息）
        if not self.metadata.title and role == "user" and self.metadata.message_count <= 2:
            # 截取前50个字符作为标题
            title = content[:50].strip()
            if len(content) > 50:
                title += "..."
            self.metadata.title = title
    
    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的消息（用于API历史）"""
        recent = self.messages[-limit:] if len(self.messages) > limit else self.messages
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in recent
        ]
    
    def get_context_messages(self, max_tokens: int = 4000) -> List[Dict[str, str]]:
        """获取上下文消息（控制token数量）"""
        # 简单的token估算：中文1.5，英文1.3
        def estimate_tokens(text: str) -> int:
            import re
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            english_words = len(re.findall(r'[a-zA-Z]+', text))
            other_chars = len(text) - chinese_chars - english_words
            return int(chinese_chars * 1.5 + english_words * 1.3 + other_chars * 0.5)
        
        context_messages = []
        total_tokens = 0
        
        # 从最新消息开始，向前添加消息直到达到token限制
        for message in reversed(self.messages):
            msg_tokens = estimate_tokens(message.content)
            if total_tokens + msg_tokens > max_tokens and context_messages:
                break
            
            context_messages.insert(0, {
                "role": message.role,
                "content": message.content
            })
            total_tokens += msg_tokens
        
        return context_messages
    
    def update_metadata(self, **kwargs):
        """更新对话元数据"""
        for key, value in kwargs.items():
            if hasattr(self.metadata, key):
                setattr(self.metadata, key, value)
        self.metadata.updated_at = datetime.now()


class ConversationSummary(BaseModel):
    """对话摘要（用于列表展示）"""
    conversation_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_activity: datetime
    tags: List[str]
    is_archived: bool
    preview: str = Field(description="对话预览（最后一条消息）")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationCreateRequest(BaseModel):
    """创建对话请求"""
    title: Optional[str] = None
    initial_message: Optional[str] = None


class ConversationListResponse(BaseModel):
    """对话列表响应"""
    conversations: List[ConversationSummary]
    total: int
    page: int = 1
    limit: int = 20