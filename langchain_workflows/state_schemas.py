"""
LangGraph状态定义模块
基于LangGraph官方文档的TypedDict状态管理
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from dataclasses import dataclass
from datetime import datetime

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

# 主要状态类 - 符合LangGraph标准
class PaperSearchState(TypedDict):
    """
    论文搜索Agent的状态定义
    使用TypedDict符合LangGraph官方标准
    """
    # 对话消息历史 - 使用Annotated进行消息累积
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 搜索参数
    query: str
    search_strategy: Optional[str]  # fast, balanced, comprehensive
    max_results: int
    filters: Dict[str, Any]  # year, venue, category等过滤条件
    
    # 搜索结果
    papers: List[Dict[str, Any]]  # 论文结果列表
    total_found: int
    
    # 搜索状态
    current_step: str  # query_analysis, searching, processing, completed
    search_progress: float  # 0.0 to 1.0
    error_message: Optional[str]
    
    # 会话管理
    session_id: str
    user_id: Optional[str]
    created_at: datetime
    
    # 搜索统计
    search_stats: Dict[str, Any]
    
    # 重试机制
    retry_count: int
    max_retries: int

def create_initial_state(
    query: str,
    session_id: str,
    user_message: str,
    search_strategy: str = "fast",
    max_results: int = 20,
    filters: Dict[str, Any] = None,
    user_id: str = None
) -> PaperSearchState:
    """
    创建初始状态
    """
    if filters is None:
        filters = {}
    
    return PaperSearchState(
        messages=[HumanMessage(content=user_message)],
        query=query,
        search_strategy=search_strategy,
        max_results=max_results,
        filters=filters,
        papers=[],
        total_found=0,
        current_step="query_analysis",
        search_progress=0.0,
        error_message=None,
        session_id=session_id,
        user_id=user_id,
        created_at=datetime.now(),
        search_stats={},
        retry_count=0,
        max_retries=3
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