"""
LangGraph学术论文搜索Agent
基于官方chatbot模式，整合状态管理和工作流执行
集成实时监控和可视化功能
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, AsyncIterator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from langchain_workflows.state_schemas import PaperSearchState, add_messages
from langchain_workflows.paper_search_graph import create_paper_search_graph, get_paper_search_graph
from langchain_workflows.monitoring import get_workflow_monitor
from langchain_workflows.visualization import WorkflowVisualizer
from langchain_tools.google_scholar_tool import google_scholar_tool


class PaperSearchAgent:
    """学术论文搜索Agent - 基于LangGraph chatbot架构，集成监控和可视化"""
    
    def __init__(self, enable_monitoring: bool = True, enable_langsmith: bool = True):
        """初始化Agent"""
        self.enable_monitoring = enable_monitoring
        self.enable_langsmith = enable_langsmith
        
        # 创建增强的工作流图
        self.workflow_graph = create_paper_search_graph(
            enable_monitoring=enable_monitoring,
            enable_langsmith=enable_langsmith
        )
        
        self.memory = MemorySaver()
        self.app = self.workflow_graph.graph.compile(checkpointer=self.memory)
        
        # 可视化器
        self.visualizer = WorkflowVisualizer() if enable_monitoring else None
        
    async def search_papers(self, 
                          query: str, 
                          max_results: int = 10,
                          year_from: Optional[int] = None,
                          year_to: Optional[int] = None,
                          thread_id: str = "default") -> Dict[str, Any]:
        """
        执行论文搜索 - 集成可视化监控
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            year_from: 起始年份
            year_to: 结束年份  
            thread_id: 会话线程ID
            
        Returns:
            搜索结果字典
        """
        print(f"🔍 开始论文搜索: {query}")
        
        try:
            # 使用增强的工作流图执行搜索
            result = await self.workflow_graph.run_search(
                query=query,
                session_id=thread_id,
                max_results=max_results,
                filters={
                    "year_from": year_from,
                    "year_to": year_to
                }
            )
            
            # 格式化返回结果以保持兼容性
            return {
                "status": "completed" if result.get("success") else "error",
                "query": query,
                "total_results": result.get("total_found", 0),
                "papers": result.get("papers", []),
                "error": result.get("error_message"),
                "session_id": result.get("session_id"),
                "search_stats": result.get("search_stats", {})
            }
            
        except Exception as e:
            error_msg = f"搜索失败: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "status": "error",
                "query": query,
                "total_results": 0,
                "papers": [],
                "error": error_msg
            }
    
    async def chat(self, 
                   message: str,
                   thread_id: str = "default") -> str:
        """
        聊天接口 - 处理用户消息并返回响应
        
        Args:
            message: 用户消息
            thread_id: 会话线程ID
            
        Returns:
            AI响应消息
        """
        try:
            # 获取当前状态
            config = {"configurable": {"thread_id": thread_id}}
            current_state = await self.app.aget_state(config)
            
            # 添加用户消息
            new_state = PaperSearchState(
                messages=current_state.values.get("messages", []) + [HumanMessage(content=message)],
                search_query=message,
                max_results=10,
                search_results=[],
                processed_results=[],
                search_status="started"
            )
            
            # 执行工作流
            final_state = await self.app.ainvoke(new_state, config=config)
            
            # 获取最后的AI消息
            messages = final_state.get("messages", [])
            if messages and isinstance(messages[-1], AIMessage):
                return messages[-1].content
            else:
                # 生成响应消息
                results = final_state.get("processed_results", [])
                if results:
                    response = f"找到了 {len(results)} 篇相关论文：\n\n"
                    for i, paper in enumerate(results[:3], 1):
                        response += f"{i}. {paper.get('title', '未知标题')}\n"
                        if paper.get('authors'):
                            response += f"   作者: {paper['authors']}\n"
                        if paper.get('year'):
                            response += f"   年份: {paper['year']}\n"
                        response += "\n"
                else:
                    response = "抱歉，没有找到相关论文。请尝试其他搜索关键词。"
                
                return response
            
        except Exception as e:
            return f"搜索过程中发生错误: {str(e)}"
    
    async def get_state(self, thread_id: str = "default") -> Dict[str, Any]:
        """
        获取当前状态
        
        Args:
            thread_id: 会话线程ID
            
        Returns:
            当前状态字典
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.app.aget_state(config)
        return state.values if state else {}
    
    async def stream_search(self, 
                          query: str,
                          max_results: int = 10,
                          year_from: Optional[int] = None,
                          year_to: Optional[int] = None,
                          thread_id: str = "default") -> AsyncIterator[Dict[str, Any]]:
        """
        流式搜索 - 实时返回搜索进度
        集成监控系统，提供详细的执行状态
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            year_from: 起始年份
            year_to: 结束年份
            thread_id: 会话线程ID
            
        Yields:
            搜索状态更新字典
        """
        print(f"🚀 开始流式搜索: {query}")
        
        # 获取监控器（如果启用）
        monitor = get_workflow_monitor(thread_id) if self.enable_monitoring else None
        
        # 订阅监控事件并转发
        if monitor:
            async def forward_monitor_events():
                event_queue = asyncio.Queue()
                
                def queue_event(event_data):
                    try:
                        event_queue.put_nowait(event_data)
                    except asyncio.QueueFull:
                        print("⚠️ 事件队列已满")
                
                monitor.subscribe(queue_event)
                
                try:
                    while True:
                        event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                        yield {
                            "type": "monitor_event",
                            "event": event.get("event"),
                            "node": event.get("node_name"),
                            "status": event.get("status", "unknown"),
                            "message": event.get("message", ""),
                            "progress": event.get("progress", 0.0),
                            "timestamp": event.get("timestamp"),
                            "session_id": thread_id
                        }
                except asyncio.TimeoutError:
                    break
                finally:
                    monitor.unsubscribe(queue_event)
            
            # 启动监控事件转发
            monitor_task = asyncio.create_task(
                self._stream_monitor_events(monitor, thread_id)
            )
        
        try:
            # 执行搜索并流式返回结果
            search_task = asyncio.create_task(
                self.search_papers(query, max_results, year_from, year_to, thread_id)
            )
            
            # 模拟进度更新（实际应用中会从真实的节点执行中获取）
            progress_steps = [
                {"step": "初始化", "progress": 0.1},
                {"step": "分析查询", "progress": 0.2},
                {"step": "搜索数据源", "progress": 0.5},
                {"step": "处理结果", "progress": 0.8},
                {"step": "生成响应", "progress": 1.0}
            ]
            
            for step_info in progress_steps:
                yield {
                    "type": "progress_update",
                    "step": step_info["step"],
                    "progress": step_info["progress"],
                    "message": f"正在{step_info['step']}...",
                    "session_id": thread_id,
                    "timestamp": asyncio.get_event_loop().time()
                }
                await asyncio.sleep(0.5)  # 模拟处理时间
            
            # 等待搜索完成
            final_result = await search_task
            
            yield {
                "type": "search_completed",
                "status": final_result.get("status"),
                "total_results": final_result.get("total_results", 0),
                "papers": final_result.get("papers", []),
                "error": final_result.get("error"),
                "session_id": thread_id,
                "search_stats": final_result.get("search_stats", {})
            }
            
        except Exception as e:
            error_msg = f"流式搜索失败: {str(e)}"
            print(f"❌ {error_msg}")
            yield {
                "type": "search_error",
                "error": error_msg,
                "session_id": thread_id
            }
        finally:
            # 清理监控任务
            if self.enable_monitoring and 'monitor_task' in locals():
                monitor_task.cancel()
    
    async def _stream_monitor_events(self, monitor, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """
        流式监控事件助手方法
        """
        event_queue = asyncio.Queue()
        
        def queue_event(event_data):
            try:
                event_queue.put_nowait(event_data)
            except asyncio.QueueFull:
                pass
        
        monitor.subscribe(queue_event)
        
        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    yield {
                        "type": "monitor_event",
                        "data": event,
                        "session_id": session_id
                    }
                except asyncio.TimeoutError:
                    break
        finally:
            monitor.unsubscribe(queue_event)
    
    # 可视化和监控方法
    def get_workflow_visualization(self) -> str:
        """获取工作流可视化图表"""
        return self.workflow_graph.get_workflow_visualization()
    
    def get_ascii_flow(self) -> str:
        """获取ASCII流程图"""
        return self.workflow_graph.get_ascii_flow()
    
    def get_execution_stats(self, session_id: str) -> Dict[str, Any]:
        """获取执行统计数据"""
        monitor = get_workflow_monitor(session_id)
        if monitor:
            return monitor.export_monitoring_data()
        return {"message": "监控未启用或会话不存在"}
    
    def visualize_workflow(self):
        """打印工作流可视化"""
        print("🎨 LangGraph论文搜索工作流")
        print("="*50)
        print(self.get_ascii_flow())
        print("\n📊 Mermaid图表:")
        print(self.get_workflow_visualization())
    
    def enable_monitoring_for_session(self, session_id: str):
        """为特定会话启用监控"""
        if self.enable_monitoring:
            self.workflow_graph.enable_real_time_monitoring(session_id)
        else:
            print("⚠️ 监控功能未全局启用")
    
    def get_monitor_dashboard_data(self, session_id: str) -> Dict[str, Any]:
        """获取监控面板数据"""
        monitor = get_workflow_monitor(session_id)
        if not monitor:
            return {"error": "监控器不存在"}
        
        stats = monitor.get_current_stats()
        return {
            "session_id": session_id,
            "stats": {
                "start_time": stats.start_time.isoformat(),
                "nodes_executed": stats.nodes_executed,
                "nodes_completed": stats.nodes_completed,
                "nodes_failed": stats.nodes_failed,
                "success_rate": stats.success_rate
            },
            "recent_events": list(monitor.execution_history)[-10:],  # 最近10个事件
            "performance_data": {
                node: monitor.get_node_performance(node)
                for node in monitor.node_metrics.keys()
            }
        }


# 创建全局Agent实例
paper_search_agent = PaperSearchAgent()


# 测试函数
async def test_agent():
    """测试Agent功能 - 包含可视化演示"""
    print("🧪 测试LangGraph论文搜索Agent...")
    
    # 显示工作流可视化
    paper_search_agent.visualize_workflow()
    
    # 测试搜索
    print("\n🔍 测试论文搜索功能:")
    result = await paper_search_agent.search_papers(
        query="machine learning",
        max_results=5,
        thread_id="test_session"
    )
    
    print(f"搜索结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    
    # 测试流式搜索
    print("\n🚀 测试流式搜索功能:")
    async for update in paper_search_agent.stream_search(
        query="deep learning",
        max_results=3,
        thread_id="stream_test_session"
    ):
        print(f"📊 进度更新: {json.dumps(update, ensure_ascii=False, indent=2)}")
    
    # 测试聊天
    print("\n💬 测试聊天功能:")
    response = await paper_search_agent.chat("搜索深度学习相关论文", "chat_test_session")
    print(f"聊天响应: {response}")
    
    # 获取监控数据
    print("\n📈 监控数据:")
    stats = paper_search_agent.get_execution_stats("test_session")
    print(f"执行统计: {json.dumps(stats, ensure_ascii=False, indent=2)}")

async def demo_visualization():
    """演示可视化功能"""
    print("🎨 LangGraph工作流可视化演示")
    print("="*60)
    
    # 创建Agent实例
    agent = PaperSearchAgent(enable_monitoring=True, enable_langsmith=True)
    
    # 显示可视化
    agent.visualize_workflow()
    
    # 演示实时监控
    print("\n🔄 开始实时监控演示...")
    session_id = "demo_visualization"
    
    # 启用监控
    agent.enable_monitoring_for_session(session_id)
    
    # 执行搜索以生成监控数据
    await agent.search_papers("artificial intelligence", thread_id=session_id)
    
    # 获取监控面板数据
    dashboard_data = agent.get_monitor_dashboard_data(session_id)
    print(f"\n📊 监控面板数据:")
    print(json.dumps(dashboard_data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(demo_visualization())
    else:
        asyncio.run(test_agent())