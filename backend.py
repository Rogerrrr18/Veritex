"""
学术论文搜索系统后端
基于LangGraph Agent架构的FastAPI应用
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from langchain_agents.paper_search_agent import paper_search_agent
from langchain_workflows.monitoring import get_monitor_manager, get_workflow_monitor
from langchain_workflows.visualization import WorkflowVisualizer

# FastAPI应用
app = FastAPI(
    title="学术论文搜索系统",
    version="3.0.0",
    description="基于LangGraph的智能学术论文搜索系统"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API模型定义
class SearchRequest(BaseModel):
    """论文搜索请求"""
    query: str
    max_results: int = 10
    year_from: Optional[int] = None
    year_to: Optional[int] = None

class SearchResponse(BaseModel):
    """论文搜索响应"""
    session_id: str
    status: str
    message: str

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    """聊天响应"""
    response: str
    session_id: str

# 会话管理
class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "created_at": datetime.now(),
            "status": "created",
            "results": None
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, data: Dict[str, Any]):
        """更新会话"""
        if session_id in self.sessions:
            self.sessions[session_id].update(data)

# 全局会话管理器
session_manager = SessionManager()

# WebSocket连接管理
class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """连接WebSocket"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        """断开连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        """发送消息"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_text(json.dumps(message, ensure_ascii=False))

# 全局连接管理器
manager = ConnectionManager()

# API端点
@app.get("/")
async def root():
    """根端点"""
    return {"message": "学术论文搜索系统API", "version": "3.0.0"}

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/search", response_model=SearchResponse)
async def search_papers(request: SearchRequest):
    """
    异步论文搜索
    创建搜索会话并返回session_id用于跟踪进度
    """
    try:
        # 创建会话
        session_id = session_manager.create_session()
        
        # 更新会话状态
        session_manager.update_session(session_id, {
            "status": "searching",
            "query": request.query,
            "max_results": request.max_results,
            "year_from": request.year_from,
            "year_to": request.year_to
        })
        
        # 后台执行搜索
        asyncio.create_task(execute_search(
            session_id, 
            request.query, 
            request.max_results,
            request.year_from,
            request.year_to
        ))
        
        return SearchResponse(
            session_id=session_id,
            status="started",
            message="搜索已开始，请使用session_id获取结果"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/result/{session_id}")
async def get_search_result(session_id: str):
    """获取搜索结果"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return {
        "session_id": session_id,
        "status": session.get("status", "unknown"),
        "results": session.get("results"),
        "error": session.get("error")
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """与Agent聊天"""
    try:
        # 使用提供的session_id或创建新的
        session_id = request.session_id or session_manager.create_session()
        
        # 与Agent聊天
        response = await paper_search_agent.chat(
            message=request.message,
            thread_id=session_id
        )
        
        return ChatResponse(
            response=response,
            session_id=session_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket端点用于实时搜索进度和工作流监控"""
    await manager.connect(websocket, session_id)
    try:
        # 监控器管理
        monitor_manager = get_monitor_manager()
        
        # 订阅全局监控事件
        def forward_monitor_events(event_data):
            if event_data.get("session_id") == session_id:
                asyncio.create_task(manager.send_message(session_id, {
                    "type": "monitor_event",
                    "data": event_data
                }))
        
        monitor_manager.subscribe_global(forward_monitor_events)
        
        try:
            while True:
                # 保持连接活跃，并处理客户端消息
                message = await websocket.receive_text()
                data = json.loads(message)
                
                # 处理客户端请求
                if data.get("type") == "get_stats":
                    monitor = get_workflow_monitor(session_id)
                    if monitor:
                        stats = monitor.get_current_stats()
                        await manager.send_message(session_id, {
                            "type": "stats_update",
                            "data": {
                                "session_id": session_id,
                                "stats": {
                                    "start_time": stats.start_time.isoformat(),
                                    "nodes_executed": stats.nodes_executed,
                                    "nodes_completed": stats.nodes_completed,
                                    "nodes_failed": stats.nodes_failed,
                                    "success_rate": stats.success_rate
                                }
                            }
                        })
                elif data.get("type") == "start_monitoring":
                    # 启用实时监控
                    paper_search_agent.enable_monitoring_for_session(session_id)
                    await manager.send_message(session_id, {
                        "type": "monitoring_enabled",
                        "session_id": session_id
                    })
                        
        except WebSocketDisconnect:
            pass
        finally:
            if forward_monitor_events in monitor_manager.global_subscribers:
                monitor_manager.global_subscribers.remove(forward_monitor_events)
            
    except Exception as e:
        print(f"WebSocket错误: {e}")
    finally:
        manager.disconnect(session_id)

async def execute_search(session_id: str, 
                        query: str, 
                        max_results: int,
                        year_from: Optional[int] = None,
                        year_to: Optional[int] = None):
    """
    执行搜索任务
    使用流式处理实时更新进度
    """
    try:
        # 通过WebSocket发送开始消息
        await manager.send_message(session_id, {
            "type": "search_started",
            "message": "开始搜索论文...",
            "query": query
        })
        
        # 执行流式搜索
        async for update in paper_search_agent.stream_search(
            query=query,
            max_results=max_results,
            year_from=year_from,
            year_to=year_to,
            thread_id=session_id
        ):
            # 发送进度更新
            await manager.send_message(session_id, {
                "type": "search_progress",
                "node": update.get("node"),
                "status": update.get("status"),
                "message": update.get("message"),
                "results_count": update.get("results_count", 0)
            })
        
        # 获取最终结果
        final_result = await paper_search_agent.search_papers(
            query=query,
            max_results=max_results,
            year_from=year_from,
            year_to=year_to,
            thread_id=session_id
        )
        
        # 更新会话
        session_manager.update_session(session_id, {
            "status": "completed",
            "results": final_result
        })
        
        # 发送完成消息
        await manager.send_message(session_id, {
            "type": "search_completed",
            "message": f"搜索完成，找到 {final_result.get('total_results', 0)} 篇论文",
            "results": final_result
        })
        
    except Exception as e:
        # 更新会话错误状态
        session_manager.update_session(session_id, {
            "status": "error",
            "error": str(e)
        })
        
        # 发送错误消息
        await manager.send_message(session_id, {
            "type": "search_error",
            "message": f"搜索失败: {str(e)}",
            "error": str(e)
        })

# 可视化和监控API端点
@app.get("/visualization/workflow")
async def get_workflow_visualization():
    """获取工作流可视化图表"""
    try:
        mermaid_graph = paper_search_agent.get_workflow_visualization()
        ascii_flow = paper_search_agent.get_ascii_flow()
        
        return {
            "mermaid_graph": mermaid_graph,
            "ascii_flow": ascii_flow,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"可视化生成失败: {str(e)}")

@app.get("/visualization/session/{session_id}")
async def get_session_visualization(session_id: str):
    """获取特定会话的可视化数据"""
    try:
        dashboard_data = paper_search_agent.get_monitor_dashboard_data(session_id)
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"会话可视化数据获取失败: {str(e)}")

@app.get("/monitoring/stats/{session_id}")
async def get_monitoring_stats(session_id: str):
    """获取监控统计数据"""
    try:
        stats = paper_search_agent.get_execution_stats(session_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"监控数据获取失败: {str(e)}")

@app.get("/monitoring/all_sessions")
async def get_all_monitoring_stats():
    """获取所有会话的监控统计"""
    try:
        monitor_manager = get_monitor_manager()
        all_stats = monitor_manager.get_all_stats()
        return {
            "total_sessions": len(all_stats),
            "sessions": all_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全局监控数据获取失败: {str(e)}")

@app.post("/monitoring/enable/{session_id}")
async def enable_monitoring(session_id: str):
    """为会话启用监控"""
    try:
        paper_search_agent.enable_monitoring_for_session(session_id)
        return {
            "message": f"已为会话 {session_id} 启用监控",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"监控启用失败: {str(e)}")

@app.get("/stream_search/{session_id}")
async def stream_search_endpoint(session_id: str, query: str, max_results: int = 10):
    """流式搜索端点"""
    async def generate_stream():
        try:
            async for update in paper_search_agent.stream_search(
                query=query,
                max_results=max_results,
                thread_id=session_id
            ):
                yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

# 兼容性端点（保持向后兼容）
@app.post("/search_papers")
async def legacy_search_papers(request: SearchRequest):
    """兼容旧版本的搜索端点"""
    result = await paper_search_agent.search_papers(
        query=request.query,
        max_results=request.max_results,
        year_from=request.year_from,
        year_to=request.year_to
    )
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )