"""
LangGraph状态模式定义
为Paper Search工作流定义状态结构
"""
from typing import Dict, Any, List, Optional, TypedDict
from langchain_core.messages import BaseMessage

class PaperSearchState(TypedDict):
    """
    Paper Search工作流的状态定义
    简化版本，兼容所有LangChain版本
    """
    
    # 核心消息流
    messages: List[BaseMessage]
    
    # 查询相关
    query: str
    max_results: int
    
    # 新增：搜索筛选参数
    year_from: Optional[int]  # 起始年份
    year_to: Optional[int]    # 结束年份
    sources: Optional[List[str]]  # 指定数据源
    
    # 工作流控制
    current_step: str  # "analyzing", "searching", "completed", "failed"
    is_completed: bool
    
    # 意图分析结果
    analysis_result: Optional[Dict[str, Any]]
    is_academic_query: Optional[bool]
    need_search_strategy: Optional[bool]
    force_search: Optional[bool]  # 强制执行搜索标志
    allow_search: Optional[bool]  # 是否允许在本轮流程中执行搜索
    
    # 搜索相关
    search_keywords: Optional[List[str]]
    search_results: Optional[List[Dict[str, Any]]]
    year_from: Optional[int]  # 年份筛选
    year_to: Optional[int]
    sources: Optional[List[str]]  # 数据源筛选
    
    # 错误处理
    error_message: Optional[str]
    retry_count: Optional[int]

def create_initial_state(
    query: str,
    user_message: str = None,
    max_results: int = 10,
    force_search: bool = False,
    allow_search: bool = True,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    sources: Optional[List[str]] = None
) -> PaperSearchState:
    """
    创建初始状态
    
    Args:
        query: 用户查询
        user_message: 用户消息（如果为空则使用query）
        max_results: 最大结果数量
        force_search: 是否强制执行搜索
        
    Returns:
        PaperSearchState: 初始化的状态对象
    """
    from langchain_core.messages import HumanMessage
    
    if user_message is None:
        user_message = query
        
    return PaperSearchState(
        messages=[HumanMessage(content=user_message)],
        query=query,
        max_results=max_results,
        year_from=year_from,
        year_to=year_to,
        sources=sources,
        current_step="initialized",
        is_completed=False,
        analysis_result=None,
        is_academic_query=None,
        need_search_strategy=None,
        force_search=force_search,
        allow_search=allow_search,
        search_keywords=None,
        search_results=None,
        error_message=None,
        retry_count=0
    )

def update_state_with_analysis(
    state: PaperSearchState, 
    analysis: Dict[str, Any],
    is_academic: bool = True,
    need_search: bool = False
) -> Dict[str, Any]:
    """
    更新状态 - 添加分析结果
    
    Args:
        state: 当前状态
        analysis: 分析结果
        is_academic: 是否为学术查询
        need_search: 是否需要搜索策略
        
    Returns:
        Dict: 状态更新字典
    """
    return {
        "analysis_result": analysis,
        "is_academic_query": is_academic,
        "need_search_strategy": need_search,
        "current_step": "analyzed"
    }

def update_state_with_search_results(
    state: PaperSearchState,
    search_results: List[Dict[str, Any]],
    keywords: List[str] = None
) -> Dict[str, Any]:
    """
    更新状态 - 添加搜索结果
    
    Args:
        state: 当前状态
        search_results: 搜索结果列表
        keywords: 使用的关键词
        
    Returns:
        Dict: 状态更新字典
    """
    return {
        "search_results": search_results,
        "search_keywords": keywords or [],
        "current_step": "searched"
    }

def mark_state_completed(
    state: PaperSearchState,
    final_response: str = None
) -> Dict[str, Any]:
    """
    标记状态为已完成
    
    Args:
        state: 当前状态
        final_response: 最终响应消息
        
    Returns:
        Dict: 状态更新字典
    """
    from langchain_core.messages import AIMessage
    
    updates = {
        "is_completed": True,
        "current_step": "completed"
    }
    
    if final_response:
        updates["messages"] = [AIMessage(content=final_response)]
    
    return updates

def mark_state_failed(
    state: PaperSearchState,
    error_message: str
) -> Dict[str, Any]:
    """
    标记状态为失败
    
    Args:
        state: 当前状态
        error_message: 错误消息
        
    Returns:
        Dict: 状态更新字典
    """
    from langchain_core.messages import AIMessage
    
    return {
        "is_completed": False,
        "current_step": "failed",
        "error_message": error_message,
        "messages": [AIMessage(content=f"处理过程中出现错误：{error_message}")]
    }

def get_state_summary(state: PaperSearchState) -> Dict[str, Any]:
    """
    获取状态摘要信息
    
    Args:
        state: 当前状态
        
    Returns:
        Dict: 状态摘要
    """
    return {
        "query": state.get("query", ""),
        "current_step": state.get("current_step", "unknown"),
        "is_completed": state.get("is_completed", False),
        "is_academic_query": state.get("is_academic_query", None),
        "need_search_strategy": state.get("need_search_strategy", None),
        "has_results": bool(state.get("search_results")),
        "result_count": len(state.get("search_results", [])),
        "has_error": bool(state.get("error_message")),
        "retry_count": state.get("retry_count", 0)
    }

# 测试功能
if __name__ == "__main__":
    print("🔍 测试状态模式定义...")
    
    # 创建初始状态
    initial_state = create_initial_state(
        query="机器学习算法研究",
        max_results=20
    )
    print(f"✅ 初始状态创建成功: {get_state_summary(initial_state)}")
    
    # 模拟更新状态
    analysis_update = update_state_with_analysis(
        initial_state,
        {"identified_terms": ["机器学习", "算法"]},
        is_academic=True,
        need_search=True
    )
    print(f"✅ 分析更新: {analysis_update}")
    
    # 模拟搜索结果更新
    search_update = update_state_with_search_results(
        initial_state,
        [{"title": "机器学习概述", "author": "张三"}],
        ["machine learning", "algorithm"]
    )
    print(f"✅ 搜索更新: {search_update}")
    
    print("✅ 状态模式定义测试完成")