"""
LangGraph状态定义模块
基于LangGraph官方文档的TypedDict状态管理
支持内存管理和human-in-the-loop控制
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from dataclasses import dataclass
from datetime import datetime
import uuid

# 论文数据结构
@dataclass
class PaperResult:
    """标准化论文结果"""
    id: str
    title: str
    abstract: Optional[str] = None
    authors: List[Dict[str, str]] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    citations: Optional[int] = None
    doi: Optional[str] = None
    source: str = "unknown"
    relevance_score: float = 0.0
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "citations": self.citations,
            "doi": self.doi,
            "source": self.source,
            "relevance_score": self.relevance_score
        }

# 搜索统计信息
@dataclass
class SearchStats:
    """搜索统计信息"""
    total_found: int = 0
    total_processed: int = 0
    duplicates_removed: int = 0
    sources_used: List[str] = None
    search_time: float = 0.0
    
    def __post_init__(self):
        if self.sources_used is None:
            self.sources_used = []

# Human-in-the-loop控制状态
@dataclass
class HumanApprovalRequest:
    """人类审批请求"""
    request_id: str
    stage: str  # before_search, after_analysis, before_final_output
    message: str
    data: Dict[str, Any]
    created_at: datetime
    timeout_seconds: int = 300
    
    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        if not hasattr(self, 'created_at') or not self.created_at:
            self.created_at = datetime.now()

# 内存管理
@dataclass  
class MemoryContext:
    """内存上下文"""
    thread_id: str
    conversation_history: List[Dict[str, Any]] = None
    user_preferences: Dict[str, Any] = None
    research_context: Dict[str, Any] = None
    previous_searches: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.user_preferences is None:
            self.user_preferences = {}
        if self.research_context is None:
            self.research_context = {}
        if self.previous_searches is None:
            self.previous_searches = []

# 简化的状态类 - 严格符合LangGraph标准
class PaperSearchState(TypedDict):
    """
    论文搜索Agent的状态定义
    遵循LangGraph官方最佳实践：以messages为核心，最小化自定义字段
    """
    # 核心：对话消息历史 - LangGraph标准模式
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 搜索核心参数 - 简化为必需字段
    query: Optional[str]  # 当前搜索查询
    max_results: Optional[int]  # 返回结果数量
    search_strategy: Optional[str]  # basic, advanced, comprehensive
    search_keywords: Optional[str]  # LLM优化后的搜索关键词
    need_tools: Optional[bool]  # 是否需要调用工具
    
    # 搜索结果 - 核心输出
    papers: Optional[List[Dict[str, Any]]]  # 论文结果列表
    total_found: Optional[int]  # 找到的论文总数
    
    # 工作流控制 - 最小化状态管理
    current_step: Optional[str]  # 当前步骤标识
    is_completed: Optional[bool]  # 是否完成
    
    # 错误处理
    error_message: Optional[str]
    
    # LangGraph标准会话管理通过thread_id在config中处理，无需在State中

def create_initial_state(
    query: str,
    user_message: str,
    max_results: int = 10,
    search_strategy: str = "basic"
) -> PaperSearchState:
    """
    创建初始状态 - 遵循LangGraph简化原则
    """
    return PaperSearchState(
        messages=[HumanMessage(content=user_message)],
        query=query,
        max_results=max_results,
        search_strategy=search_strategy,
        papers=None,
        total_found=None,
        current_step="start",
        is_completed=False,
        error_message=None
    )

def update_search_progress(state: PaperSearchState, step: str, progress: float) -> Dict[str, Any]:
    """
    更新搜索进度的辅助函数
    """
    return {
        "current_step": step,
        "search_progress": progress
    }

def add_papers_to_state(state: PaperSearchState, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    添加论文到状态的辅助函数
    """
    existing_papers = state.get("papers", [])
    all_papers = existing_papers + papers
    
    return {
        "papers": all_papers,
        "total_found": len(all_papers)
    }

def set_error_state(state: PaperSearchState, error_message: str) -> Dict[str, Any]:
    """
    设置错误状态的辅助函数
    """
    return {
        "error_message": error_message,
        "current_step": "error"
    }

def should_retry(state: PaperSearchState) -> bool:
    """
    判断是否应该重试
    """
    return (
        state.get("retry_count", 0) < state.get("max_retries", 3) and
        state.get("error_message") is not None and
        state.get("total_found", 0) == 0
    )

def increment_retry_count(state: PaperSearchState) -> Dict[str, Any]:
    """
    增加重试计数
    """
    return {
        "retry_count": state.get("retry_count", 0) + 1,
        "error_message": None  # 清除错误消息以便重试
    }

# Human-in-the-loop相关函数
def create_approval_request(
    state: PaperSearchState, 
    stage: str, 
    message: str, 
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    创建人类审批请求
    """
    approval_request = {
        "request_id": str(uuid.uuid4()),
        "stage": stage,
        "message": message,
        "data": data,
        "created_at": datetime.now(),
        "timeout_seconds": 300
    }
    
    return {
        "pending_approval": approval_request,
        "current_step": "waiting_approval"
    }

def process_human_feedback(
    state: PaperSearchState, 
    feedback: str, 
    approved: bool
) -> Dict[str, Any]:
    """
    处理人类反馈
    """
    updates = {
        "human_feedback": feedback,
        "pending_approval": None
    }
    
    if approved:
        # 根据当前阶段决定下一步
        current_stage = state.get("pending_approval", {}).get("stage")
        if current_stage == "before_search":
            updates["current_step"] = "searching"
        elif current_stage == "after_analysis":
            updates["current_step"] = "strategy_planning"
        elif current_stage == "before_final_output":
            updates["current_step"] = "completed"
        else:
            updates["current_step"] = "processing"
    else:
        # 用户不同意，需要重新分析
        updates["current_step"] = "analysis"
        updates["search_progress"] = 0.0
    
    return updates

# 内存管理相关函数
def update_memory_context(
    state: PaperSearchState, 
    context_updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    更新内存上下文
    """
    current_memory = state.get("memory", {})
    if not current_memory:
        current_memory = {
            "thread_id": state.get("thread_id"),
            "conversation_history": [],
            "user_preferences": {},
            "research_context": {},
            "previous_searches": []
        }
    
    # 更新内存数据
    for key, value in context_updates.items():
        if key in current_memory:
            if isinstance(current_memory[key], list):
                current_memory[key].extend(value if isinstance(value, list) else [value])
            elif isinstance(current_memory[key], dict):
                current_memory[key].update(value if isinstance(value, dict) else {})
            else:
                current_memory[key] = value
    
    return {"memory": current_memory}

def add_to_conversation_history(
    state: PaperSearchState, 
    role: str, 
    content: str, 
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    添加对话历史
    """
    if metadata is None:
        metadata = {}
    
    conversation_entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(),
        "metadata": metadata
    }
    
    return update_memory_context(state, {
        "conversation_history": [conversation_entry]
    })

def save_search_to_history(
    state: PaperSearchState
) -> Dict[str, Any]:
    """
    保存搜索结果到历史
    """
    search_record = {
        "query": state.get("query"),
        "strategy": state.get("search_strategy"),
        "results_count": state.get("total_found", 0),
        "timestamp": datetime.now(),
        "session_id": state.get("session_id")
    }
    
    return update_memory_context(state, {
        "previous_searches": [search_record]
    })