"""
LangGraph论文搜索工作流
基于LangGraph官方StateGraph模式构建
集成LangSmith追踪和实时可视化监控
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import os

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state_schemas import (
    PaperSearchState, 
    create_initial_state,
    update_search_progress,
    add_papers_to_state,
    set_error_state,
    should_retry,
    increment_retry_count
)
from .visualization import WorkflowVisualizer, setup_langsmith_tracing
from .monitoring import create_workflow_monitor, WorkflowMonitor

class PaperSearchGraph:
    """
    论文搜索工作流图
    基于LangGraph StateGraph构建
    集成可视化和监控功能
    """
    
    def __init__(self, enable_monitoring: bool = True, enable_langsmith: bool = True):
        self.checkpointer = MemorySaver()
        self.enable_monitoring = enable_monitoring
        self.enable_langsmith = enable_langsmith
        
        # 初始化LangSmith追踪
        self.langsmith_tracer = None
        if enable_langsmith:
            self.langsmith_tracer = setup_langsmith_tracing()
        
        # 构建图
        self.graph = self._build_graph()
        
        # 可视化器
        self.visualizer = None
        self.monitor = None
    
    def _build_graph(self) -> StateGraph:
        """
        构建StateGraph工作流
        """
        # 创建状态图
        workflow = StateGraph(PaperSearchState)
        
        # 添加节点
        workflow.add_node("analyze_query", self.analyze_query_node)
        workflow.add_node("search_papers", self.search_papers_node)
        workflow.add_node("process_results", self.process_results_node)
        workflow.add_node("generate_response", self.generate_response_node)
        workflow.add_node("handle_error", self.handle_error_node)
        
        # 设置入口点
        workflow.add_edge(START, "analyze_query")
        
        # 添加条件路由
        workflow.add_conditional_edges(
            "analyze_query",
            self.should_search,
            {
                "search": "search_papers",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "search_papers",
            self.should_process_results,
            {
                "process": "process_results",
                "retry": "search_papers",  # 重试搜索
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "process_results",
            self.should_generate_response,
            {
                "respond": "generate_response",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_error", END)
        
        # 编译图
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def analyze_query_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """
        查询分析节点
        """
        session_id = state.get("session_id", "default")
        
        # 监控节点开始
        if self.monitor:
            self.monitor.start_node_execution("analyze_query", state)
        
        try:
            print(f"分析查询: {state['query']}")
            
            # 更新进度
            if self.monitor:
                self.monitor.update_node_progress("analyze_query", 0.3, "正在分析查询...")
            
            updates = update_search_progress(state, "query_analysis", 0.1)
            
            # 简单的查询验证
            if not state.get("query") or len(state["query"].strip()) < 2:
                error_msg = "搜索查询太短或为空"
                updates.update(set_error_state(state, error_msg))
                
                if self.monitor:
                    self.monitor.complete_node_execution("analyze_query", "error", None, error_msg)
                
                return updates
            
            # 查询分析完成
            updates["current_step"] = "ready_to_search"
            updates["search_progress"] = 0.2
            
            if self.monitor:
                self.monitor.update_node_progress("analyze_query", 1.0, "查询分析完成")
                self.monitor.complete_node_execution("analyze_query", "completed", updates)
            
            return updates
            
        except Exception as e:
            error_msg = f"查询分析失败: {str(e)}"
            if self.monitor:
                self.monitor.complete_node_execution("analyze_query", "error", None, error_msg)
            raise
    
    async def search_papers_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """
        论文搜索节点 - 模拟搜索过程
        """
        # 监控节点开始
        if self.monitor:
            self.monitor.start_node_execution("search_papers", state)
        
        try:
            print(f"搜索论文: {state['query']}")
            
            # 更新进度
            if self.monitor:
                self.monitor.update_node_progress("search_papers", 0.2, "开始搜索论文...")
            
            updates = update_search_progress(state, "searching", 0.3)
            
            # 模拟搜索延迟
            await asyncio.sleep(1)
            
            if self.monitor:
                self.monitor.update_node_progress("search_papers", 0.6, "搜索数据源中...")
            
            # 模拟搜索结果
            mock_papers = await self._mock_paper_search(
                state["query"], 
                state.get("max_results", 10)
            )
            
            if self.monitor:
                self.monitor.update_node_progress("search_papers", 0.9, f"找到 {len(mock_papers)} 篇论文")
            
            # 添加论文到状态
            updates.update(add_papers_to_state(state, mock_papers))
            updates["current_step"] = "search_completed"
            updates["search_progress"] = 0.6
            
            if self.monitor:
                self.monitor.complete_node_execution("search_papers", "completed", updates)
            
            return updates
            
        except Exception as e:
            error_msg = f"搜索过程中出现错误: {str(e)}"
            print(f"搜索错误: {error_msg}")
            
            if self.monitor:
                self.monitor.complete_node_execution("search_papers", "error", None, error_msg)
            
            return set_error_state(state, error_msg)
    
    async def process_results_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """
        结果处理节点
        """
        print(f"处理搜索结果: {len(state.get('papers', []))} 篇论文")
        
        try:
            papers = state.get("papers", [])
            
            # 模拟结果处理：去重、排序、相关性评分
            processed_papers = await self._process_papers(papers, state["query"])
            
            # 更新状态
            updates = {
                "papers": processed_papers,
                "current_step": "processing_completed",
                "search_progress": 0.8,
                "search_stats": {
                    "total_found": len(processed_papers),
                    "processing_time": 0.5,
                    "sources": ["mock_source"]
                }
            }
            
            return updates
            
        except Exception as e:
            error_msg = f"结果处理中出现错误: {str(e)}"
            print(f"处理错误: {error_msg}")
            return set_error_state(state, error_msg)
    
    async def generate_response_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """
        生成响应节点
        """
        print("生成最终响应")
        
        try:
            papers = state.get("papers", [])
            total_found = len(papers)
            
            if total_found == 0:
                response_text = f"很抱歉，没有找到关于'{state['query']}'的相关论文。"
            else:
                # 生成响应文本
                response_text = f"找到了 {total_found} 篇关于'{state['query']}'的相关论文：\n\n"
                
                # 添加前3篇论文的摘要
                for i, paper in enumerate(papers[:3], 1):
                    response_text += f"{i}. **{paper['title']}**\n"
                    if paper.get('authors'):
                        authors = [author.get('name', '') for author in paper['authors'][:2]]
                        response_text += f"   作者: {', '.join(authors)}\n"
                    if paper.get('year'):
                        response_text += f"   年份: {paper['year']}\n"
                    response_text += "\n"
                
                if total_found > 3:
                    response_text += f"还有 {total_found - 3} 篇相关论文。"
            
            # 添加AI响应到消息历史
            ai_message = AIMessage(content=response_text)
            
            updates = {
                "messages": [ai_message],  # 这会通过add_messages累积到现有消息中
                "current_step": "completed",
                "search_progress": 1.0
            }
            
            return updates
            
        except Exception as e:
            error_msg = f"生成响应时出现错误: {str(e)}"
            print(f"响应生成错误: {error_msg}")
            return set_error_state(state, error_msg)
    
    async def handle_error_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """
        错误处理节点
        """
        error_message = state.get("error_message", "未知错误")
        print(f"处理错误: {error_message}")
        
        # 生成错误响应
        error_response = f"搜索过程中遇到问题: {error_message}\n请稍后重试或联系管理员。"
        ai_message = AIMessage(content=error_response)
        
        return {
            "messages": [ai_message],
            "current_step": "error",
            "search_progress": 0.0
        }
    
    # 条件路由函数
    def should_search(self, state: PaperSearchState) -> str:
        """判断是否应该搜索"""
        if state.get("error_message"):
            return "error"
        return "search"
    
    def should_process_results(self, state: PaperSearchState) -> str:
        """判断是否应该处理结果"""
        if state.get("error_message"):
            if should_retry(state):
                return "retry"
            return "error"
        return "process"
    
    def should_generate_response(self, state: PaperSearchState) -> str:
        """判断是否应该生成响应"""
        if state.get("error_message"):
            return "error"
        return "respond"
    
    # 辅助方法
    async def _mock_paper_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        模拟论文搜索 - 返回模拟数据
        实际实现中这里会调用真实的搜索API
        """
        mock_papers = []
        
        for i in range(min(max_results, 5)):
            paper = {
                "id": f"mock_{uuid.uuid4().hex[:8]}",
                "title": f"关于{query}的研究论文 {i+1}",
                "abstract": f"这是一篇关于{query}的重要研究论文的摘要...",
                "authors": [
                    {"name": f"作者{i+1}A"},
                    {"name": f"作者{i+1}B"}
                ],
                "year": 2020 + i,
                "venue": f"学术期刊 {i+1}",
                "url": f"https://example.com/paper_{i+1}",
                "source": "mock_source",
                "relevance_score": 0.9 - i * 0.1
            }
            mock_papers.append(paper)
        
        return mock_papers
    
    async def _process_papers(self, papers: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        处理论文结果：去重、排序等
        """
        # 简单的处理逻辑
        processed = []
        seen_titles = set()
        
        for paper in papers:
            title = paper.get("title", "").lower()
            if title not in seen_titles:
                seen_titles.add(title)
                processed.append(paper)
        
        # 按相关性评分排序
        processed.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return processed
    
    async def run_search(
        self, 
        query: str, 
        user_message: str = None,
        session_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        运行论文搜索工作流
        集成可视化和监控功能
        """
        if session_id is None:
            session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        if user_message is None:
            user_message = f"搜索关于'{query}'的论文"
        
        # 初始化监控和可视化
        if self.enable_monitoring:
            self.monitor = create_workflow_monitor(session_id)
            self.visualizer = WorkflowVisualizer(session_id)
        
        # 创建初始状态
        initial_state = create_initial_state(
            query=query,
            session_id=session_id,
            user_message=user_message,
            **kwargs
        )
        
        print(f"开始搜索工作流 (Session: {session_id})")
        
        # 显示工作流图
        if self.visualizer:
            print("\n" + "="*60)
            print("📊 工作流结构:")
            print(self.visualizer.generate_ascii_flow())
            print("="*60 + "\n")
        
        # 运行工作流
        config = {"configurable": {"thread_id": session_id}}
        
        # 添加LangSmith追踪
        if self.langsmith_tracer:
            config["callbacks"] = [self.langsmith_tracer]
        
        try:
            final_state = await self.graph.ainvoke(initial_state, config)
            
            # 提取结果
            result = {
                "success": final_state.get("current_step") == "completed",
                "papers": final_state.get("papers", []),
                "total_found": final_state.get("total_found", 0),
                "error_message": final_state.get("error_message"),
                "search_stats": final_state.get("search_stats", {}),
                "messages": [msg.content for msg in final_state.get("messages", [])],
                "session_id": session_id
            }
            
            # 生成执行报告
            if self.visualizer:
                print("\n" + self.visualizer.generate_execution_report())
            
            return result
            
        except Exception as e:
            error_msg = f"工作流执行错误: {str(e)}"
            print(error_msg) 
            
            if self.monitor:
                self.monitor.complete_node_execution("workflow", "error", None, error_msg)
            
            return {
                "success": False,
                "papers": [],
                "total_found": 0,
                "error_message": error_msg,
                "session_id": session_id
            }
    
    # 可视化和监控方法
    def get_workflow_visualization(self) -> str:
        """获取工作流可视化图表"""
        if not self.visualizer:
            self.visualizer = WorkflowVisualizer()
        return self.visualizer.generate_mermaid_graph(self.graph)
    
    def get_ascii_flow(self) -> str:
        """获取ASCII流程图"""
        if not self.visualizer:
            self.visualizer = WorkflowVisualizer()
        return self.visualizer.generate_ascii_flow()
    
    def get_execution_stats(self, session_id: str = None) -> Dict[str, Any]:
        """获取执行统计数据"""
        if self.monitor:
            return self.monitor.export_monitoring_data()
        return {"message": "监控未启用"}
    
    def enable_real_time_monitoring(self, session_id: str):
        """启用实时监控"""
        if not self.enable_monitoring:
            self.enable_monitoring = True
            self.monitor = create_workflow_monitor(session_id)
            print(f"✅ 已为会话 {session_id} 启用实时监控")
    
    def disable_monitoring(self):
        """禁用监控"""
        if self.monitor:
            self.monitor.cleanup()
            self.monitor = None
        self.enable_monitoring = False
        print("🛑 监控已禁用")

# 全局工作流实例
_paper_search_graph = None

async def get_paper_search_graph(enable_monitoring: bool = True, enable_langsmith: bool = True) -> PaperSearchGraph:
    """
    获取论文搜索工作流实例
    支持可视化和监控配置
    """
    global _paper_search_graph
    if _paper_search_graph is None:
        _paper_search_graph = PaperSearchGraph(
            enable_monitoring=enable_monitoring,
            enable_langsmith=enable_langsmith
        )
    return _paper_search_graph

def create_paper_search_graph(enable_monitoring: bool = True, enable_langsmith: bool = True) -> PaperSearchGraph:
    """
    创建新的论文搜索工作流实例
    """
    return PaperSearchGraph(
        enable_monitoring=enable_monitoring,
        enable_langsmith=enable_langsmith
    )

# 便捷可视化函数
def visualize_workflow():
    """
    快速可视化工作流
    """
    graph = create_paper_search_graph()
    print("🎨 LangGraph论文搜索工作流可视化")
    print("="*50)
    
    print("\n📊 Mermaid图表:")
    print(graph.get_workflow_visualization())
    
    print("\n🎨 ASCII流程图:")
    print(graph.get_ascii_flow())

if __name__ == "__main__":
    # 演示可视化功能
    visualize_workflow()