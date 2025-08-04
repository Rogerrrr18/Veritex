"""
LangGraph工作流可视化模块
提供多种可视化方案：LangSmith集成、Mermaid图表、ASCII流程图等
"""
import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from langchain_core.tracers import LangChainTracer
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.graph import StateGraph
import io
import sys

# 配置LangSmith追踪
def setup_langsmith_tracing() -> LangChainTracer:
    """
    设置LangSmith追踪器
    """
    # 从环境变量获取配置
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "papergod")
    langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    
    if not langsmith_api_key:
        print("警告: 未找到LANGSMITH_API_KEY，LangSmith追踪将被禁用")
        return None
    
    # 设置环境变量确保LangSmith正常工作
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = langsmith_project
    os.environ["LANGCHAIN_ENDPOINT"] = langsmith_endpoint
    
    tracer = LangChainTracer(
        project_name=langsmith_project,
        client_timeout=30
    )
    
    print(f"✅ LangSmith追踪已启用 - 项目: {langsmith_project}")
    return tracer


class WorkflowVisualizer:
    """
    工作流可视化器
    支持多种可视化输出格式
    """
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.langsmith_tracer = setup_langsmith_tracing()
        self.execution_log = []
        self.node_states = {}
        
    def generate_mermaid_graph(self, graph: StateGraph) -> str:
        """
        生成Mermaid流程图代码
        """
        mermaid_code = """
```mermaid
graph TD
    START([开始]) --> analyze_query[分析查询]
    analyze_query --> |查询有效| search_papers[搜索论文]
    analyze_query --> |查询无效| handle_error[错误处理]
    search_papers --> |搜索成功| process_results[处理结果]
    search_papers --> |需要重试| search_papers
    search_papers --> |搜索失败| handle_error
    process_results --> |处理成功| generate_response[生成响应]
    process_results --> |处理失败| handle_error
    generate_response --> END([完成])
    handle_error --> END
    
    %% 样式定义
    classDef startEnd fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px
    
    class START,END startEnd
    class analyze_query,search_papers,process_results,generate_response process
    class handle_error error
```
"""
        return mermaid_code
    
    def generate_ascii_flow(self) -> str:
        """
        生成ASCII艺术流程图
        """
        ascii_flow = """
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph 论文搜索工作流                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐    ┌──────────────┐    ┌─────────────┐             │
│  │  开始   │───▶│   分析查询   │───▶│  搜索论文   │             │
│  └─────────┘    └──────────────┘    └─────────────┘             │
│                         │                    │                  │
│                         ▼                    ▼                  │
│                  ┌──────────────┐    ┌─────────────┐             │
│                  │   错误处理   │◀───│  处理结果   │             │
│                  └──────────────┘    └─────────────┘             │
│                         │                    │                  │
│                         ▼                    ▼                  │
│                  ┌──────────────┐    ┌─────────────┐             │
│                  │     结束     │◀───│  生成响应   │             │
│                  └──────────────┘    └─────────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
"""
        return ascii_flow
    
    def log_node_execution(self, node_name: str, state: Dict[str, Any], status: str = "running"):
        """
        记录节点执行状态
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "node_name": node_name,
            "status": status,
            "state_snapshot": {
                "current_step": state.get("current_step"),
                "search_progress": state.get("search_progress", 0.0),
                "papers_count": len(state.get("papers", [])),
                "error_message": state.get("error_message")
            }
        }
        
        self.execution_log.append(log_entry)
        self.node_states[node_name] = log_entry
        
        # 终端实时输出
        self._print_node_status(log_entry)
        
        return log_entry
    
    def _print_node_status(self, log_entry: Dict[str, Any]):
        """
        在终端输出节点状态
        """
        node_name = log_entry["node_name"]
        status = log_entry["status"]
        state_snapshot = log_entry["state_snapshot"]
        
        # 状态图标
        status_icons = {
            "running": "🔄",
            "completed": "✅", 
            "error": "❌",
            "waiting": "⏳"
        }
        
        icon = status_icons.get(status, "📍")
        progress = state_snapshot.get("search_progress", 0.0)
        papers_count = state_snapshot.get("papers_count", 0)
        
        # 进度条
        progress_bar = self._create_progress_bar(progress)
        
        print(f"{icon} [{log_entry['timestamp'][11:19]}] {node_name.upper()}")
        print(f"   状态: {status} | 进度: {progress_bar} {progress:.1%}")
        print(f"   论文数量: {papers_count} | 当前步骤: {state_snapshot.get('current_step', 'N/A')}")
        
        if state_snapshot.get("error_message"):
            print(f"   ❌ 错误: {state_snapshot['error_message']}")
        
        print("─" * 60)
    
    def _create_progress_bar(self, progress: float, width: int = 20) -> str:
        """
        创建ASCII进度条
        """
        filled = int(progress * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def generate_execution_report(self) -> str:
        """
        生成执行报告
        """
        if not self.execution_log:
            return "暂无执行记录"
        
        total_nodes = len(set(log["node_name"] for log in self.execution_log))
        completed_nodes = len([log for log in self.execution_log if log["status"] == "completed"])
        error_nodes = len([log for log in self.execution_log if log["status"] == "error"])
        
        start_time = self.execution_log[0]["timestamp"]
        end_time = self.execution_log[-1]["timestamp"]
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           LangGraph 工作流执行报告                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 会话ID: {self.session_id:<60} ║
║ 开始时间: {start_time:<58} ║  
║ 结束时间: {end_time:<58} ║
║ 总节点数: {total_nodes:<3} | 完成: {completed_nodes:<3} | 错误: {error_nodes:<3} | 成功率: {(completed_nodes/total_nodes*100 if total_nodes > 0 else 0):.1f}%     ║
╚══════════════════════════════════════════════════════════════════════════════╝

节点执行详情:
"""
        
        for log in self.execution_log:
            status_symbol = {"running": "🔄", "completed": "✅", "error": "❌"}.get(log["status"], "📍")
            report += f"{status_symbol} {log['timestamp'][11:19]} | {log['node_name']:<15} | {log['status']:<10}\n"
            
            if log.get("state_snapshot", {}).get("error_message"):
                report += f"   ❌ {log['state_snapshot']['error_message']}\n"
        
        return report
    
    def export_execution_data(self, format: str = "json") -> str:
        """
        导出执行数据
        
        Args:
            format: 导出格式 ("json", "csv", "yaml")
        """
        if format.lower() == "json":
            return json.dumps({
                "session_id": self.session_id,
                "execution_log": self.execution_log,
                "node_states": self.node_states,
                "summary": {
                    "total_nodes": len(set(log["node_name"] for log in self.execution_log)),
                    "total_executions": len(self.execution_log),
                    "has_errors": any(log["status"] == "error" for log in self.execution_log)
                }
            }, ensure_ascii=False, indent=2)
        else:
            return f"暂不支持 {format} 格式导出"


class WorkflowMonitoringCallback(BaseCallbackHandler):
    """
    工作流监控回调处理器
    实时监控LangGraph执行状态
    """
    
    def __init__(self, visualizer: WorkflowVisualizer):
        super().__init__()
        self.visualizer = visualizer
        self.current_node = None
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """链开始执行时触发"""
        chain_name = serialized.get("name", "unknown_chain")
        print(f"🚀 开始执行链: {chain_name}")
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """链执行结束时触发"""
        print(f"🏁 链执行完成")
    
    def on_chain_error(self, error: Exception, **kwargs) -> None:
        """链执行错误时触发"""
        print(f"💥 链执行错误: {str(error)}")
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """工具开始执行时触发"""
        tool_name = serialized.get("name", "unknown_tool")
        print(f"🔧 开始使用工具: {tool_name}")
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """工具执行结束时触发"""
        print(f"✅ 工具执行完成")


def create_workflow_visualizer(session_id: str = None) -> WorkflowVisualizer:
    """
    创建工作流可视化器实例
    """
    return WorkflowVisualizer(session_id)


def demonstrate_visualization():
    """
    演示可视化功能
    """
    print("🎨 LangGraph工作流可视化演示")
    print("=" * 50)
    
    visualizer = create_workflow_visualizer("demo_session")
    
    # 演示Mermaid图
    print("\n📊 Mermaid流程图:")
    print(visualizer.generate_mermaid_graph(None))
    
    # 演示ASCII流程图
    print("\n🎨 ASCII流程图:")
    print(visualizer.generate_ascii_flow())
    
    # 模拟节点执行
    print("\n🔄 模拟节点执行:")
    mock_states = [
        {"current_step": "query_analysis", "search_progress": 0.1, "papers": []},
        {"current_step": "searching", "search_progress": 0.5, "papers": []},
        {"current_step": "processing", "search_progress": 0.8, "papers": [{"title": "Sample Paper"}]},
        {"current_step": "completed", "search_progress": 1.0, "papers": [{"title": "Sample Paper"}]}
    ]
    
    nodes = ["analyze_query", "search_papers", "process_results", "generate_response"]
    
    for i, (node, state) in enumerate(zip(nodes, mock_states)):
        status = "completed" if i < len(nodes) - 1 else "running"
        visualizer.log_node_execution(node, state, status)
        
        # 模拟执行时间
        import time
        time.sleep(0.5)
    
    # 生成执行报告
    print("\n📋 执行报告:")
    print(visualizer.generate_execution_report())


if __name__ == "__main__":
    demonstrate_visualization()