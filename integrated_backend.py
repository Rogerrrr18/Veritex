"""
集成后端 - 同时支持聊天和通用MCP功能
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any, Union
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from qwen_api_async import get_qwen_client
from universal_mcp import get_universal_client, universal_search

# FastAPI应用初始化
app = FastAPI(
    title="Integrated Chat + MCP API", 
    version="2.0.0",
    description="集成聊天和通用MCP功能的统一后端"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 聊天相关模型
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    response: str
    history: List[ChatMessage]

# MCP搜索相关模型
class UniversalSearchRequest(BaseModel):
    query: str
    sources: Optional[List[str]] = None
    strategy: Optional[str] = None
    limit: Optional[int] = 20
    category: Optional[str] = None
    year: Optional[str] = None
    venue: Optional[str] = None

class PaperSearchResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    count: Optional[int] = None
    source: Optional[str] = None
    source_counts: Optional[Dict[str, int]] = None

# === 基础路由 ===
@app.get("/")
async def root():
    return {
        "message": "Integrated Chat + MCP API is running!",
        "version": "2.0.0",
        "features": [
            "千问聊天API",
            "通用MCP学术搜索",
            "零代码添加新数据源",
            "并行多源搜索",
            "智能去重和排序"
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查千问API
        qwen_client = await get_qwen_client()
        test_response = await qwen_client.simple_chat("你好")
        
        # 检查MCP系统
        mcp_client = await get_universal_client()
        mcp_services = mcp_client.get_available_services()
        enabled_count = sum(1 for s in mcp_services.values() if s.get("enabled", True))
        
        return {
            "status": "healthy",
            "qwen_api": "connected",
            "mcp_services": enabled_count,
            "total_services": len(mcp_services),
            "response_preview": test_response[:20] + "..." if test_response else "N/A"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# === 聊天功能 ===
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口"""
    try:
        # 转换历史记录格式
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        
        # 检查是否是MCP搜索请求
        user_message = request.message.lower()
        if any(keyword in user_message for keyword in ["搜索", "论文", "文献", "search", "paper", "甲烷", "methane"]):
            # 如果是搜索请求，调用MCP并返回增强回复
            try:
                # 提取关键词
                search_query = request.message
                if "搜索" in user_message:
                    search_query = user_message.split("搜索")[-1].strip()
                elif "论文" in user_message:
                    search_query = user_message.replace("论文", "").strip()
                
                # 处理中文查询词，转换为英文
                if "甲烷" in search_query or "干重整" in search_query:
                    search_query = "methane dry reforming"
                
                print(f"MCP搜索查询: {search_query}")
                
                # 使用MCP搜索
                mcp_result = await universal_search(
                    query=search_query,
                    strategy="fast",
                    limit=5
                )
                
                print(f"MCP搜索结果: success={mcp_result.get('success')}, count={mcp_result.get('total_count', 0)}")
                
                if mcp_result.get("success") and mcp_result.get("papers"):
                    papers = mcp_result["papers"][:3]  # 取前3篇
                    
                    # 构建增强回复
                    ai_response = f"我为你找到了{len(papers)}篇相关论文：\n\n"
                    for i, paper in enumerate(papers, 1):
                        title = paper.get("title", "无标题")[:80]
                        authors_list = paper.get("authors", [])
                        authors = ", ".join([a.get("name", "") for a in authors_list[:2]])
                        if len(authors_list) > 2:
                            authors += f" 等{len(authors_list)}人"
                        year = paper.get("year") or "未知年份"
                        source = paper.get("source", "未知来源")
                        
                        ai_response += f"{i}. **{title}**\n"
                        ai_response += f"   作者: {authors}\n"
                        ai_response += f"   年份: {year} | 来源: {source}\n\n"
                    
                    ai_response += f"共找到 {mcp_result.get('total_count', 0)} 篇相关论文。如需查看更多论文或获取详细信息，请告诉我！"
                else:
                    ai_response = f"很抱歉，没有找到关于'{search_query}'的相关论文。可能的原因：\n1. 搜索词过于具体\n2. 数据库中暂时没有相关内容\n3. 建议尝试使用英文关键词搜索\n\n你可以尝试搜索更通用的关键词，比如 'methane reforming' 或 'catalyst'。"
                    
            except Exception as mcp_error:
                # MCP出错时提供友好的回复
                print(f"MCP搜索出错: {mcp_error}")
                ai_response = f"搜索过程中遇到了一些技术问题。让我为你提供一些关于甲烷干重整的基本信息：\n\n甲烷干重整(Dry Reforming of Methane, DRM)是一种重要的化学工艺，主要涉及：\n- 将甲烷(CH₄)和二氧化碳(CO₂)转化为合成气(H₂和CO)\n- 重要的催化剂研究领域\n- 在石化工业中有重要应用\n\n建议你稍后重试搜索功能，或者查看相关的学术数据库如arXiv、Google Scholar等。"
        else:
            # 普通聊天
            try:
                qwen_client = await get_qwen_client()
                ai_response = await qwen_client.simple_chat(request.message, history)
            except Exception as chat_error:
                print(f"聊天API出错: {chat_error}")
                ai_response = "很抱歉，我现在无法正常回复。系统可能正在维护中，请稍后再试。如果问题持续存在，请检查网络连接或联系管理员。"
        
        # 构建完整的对话历史
        updated_history = history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": ai_response}
        ]
        
        # 转换回响应格式
        response_history = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in updated_history
        ]
        
        return ChatResponse(
            response=ai_response,
            history=response_history
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聊天服务错误: {str(e)}")

@app.get("/models")
async def get_models():
    """获取可用模型列表"""
    return {
        "models": [
            {"id": "qwen-turbo", "name": "千问Turbo", "description": "快速响应模型"},
            {"id": "qwen-plus", "name": "千问Plus", "description": "高质量模型"},
            {"id": "qwen-max", "name": "千问Max", "description": "顶级模型"}
        ]
    }

# === MCP功能 ===
@app.post("/universal_search")
async def universal_search_endpoint(request: UniversalSearchRequest):
    """通用搜索接口"""
    try:
        search_params = {
            "limit": request.limit,
            "category": request.category,
            "year": request.year,
            "venue": request.venue
        }
        search_params = {k: v for k, v in search_params.items() if v is not None}
        
        result = await universal_search(
            query=request.query,
            sources=request.sources,
            strategy=request.strategy,
            **search_params
        )
        
        return {
            "success": result.get("success", False),
            "papers": result.get("papers", []),
            "total_count": result.get("total_count", 0),
            "source_stats": result.get("source_stats"),
            "errors": result.get("errors"),
            "strategy": request.strategy,
            "query": request.query
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

# 兼容性MCP接口
@app.post("/search_papers", response_model=PaperSearchResponse)
async def search_papers(query: str, limit: int = 10, venue: str = None, year: str = None):
    """兼容性论文搜索接口"""
    try:
        result = await universal_search(
            query=query, 
            strategy="fast", 
            limit=limit,
            venue=venue,
            year=year
        )
        
        return PaperSearchResponse(
            success=result.get("success", False),
            data={"data": result.get("papers", [])},
            count=result.get("total_count", 0),
            source="universal_mcp",
            source_counts=result.get("source_stats")
        )
        
    except Exception as e:
        return PaperSearchResponse(
            success=False,
            error=f"搜索论文时发生错误: {str(e)}",
            data=None,
            count=0
        )

@app.post("/search_arxiv", response_model=PaperSearchResponse)
async def search_arxiv(query: str, max_results: int = 10, category: str = None):
    """兼容性arXiv搜索接口"""
    try:
        client = await get_universal_client()
        result = await client.search_service("arxiv", query=query, limit=max_results, category=category)
        
        return PaperSearchResponse(
            success=result.get("success", False),
            data={"data": [p.to_dict() if hasattr(p, 'to_dict') else p for p in result.get("papers", [])]},
            count=result.get("count", 0),
            source="arxiv"
        )
        
    except Exception as e:
        return PaperSearchResponse(
            success=False,
            error=f"arXiv搜索失败: {str(e)}",
            data=None,
            count=0,
            source="arxiv"
        )

@app.get("/services")
async def get_services():
    """获取MCP服务信息"""
    try:
        client = await get_universal_client()
        services = client.get_available_services()
        strategies = client.get_search_strategies()
        
        return {
            "services": services,
            "strategies": strategies,
            "total_services": len(services)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务信息失败: {str(e)}")

@app.get("/mcp/status")
async def mcp_status():
    """MCP服务状态检查"""
    try:
        client = await get_universal_client()
        services = client.get_available_services()
        
        service_status = {}
        for service_id, service_info in services.items():
            if service_info.get("enabled"):
                try:
                    test_result = await client.search_service(service_id, query="test", limit=1)
                    service_status[service_id] = {
                        "status": "healthy" if test_result.get("success") else "error",
                        "error": test_result.get("error") if not test_result.get("success") else None
                    }
                except Exception as e:
                    service_status[service_id] = {"status": "error", "error": str(e)}
        
        return {
            "status": "healthy",
            "message": "MCP管理器运行正常",
            "total_services": len(services),
            "enabled_services": len([s for s in services.values() if s.get("enabled")]),
            "service_status": service_status
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": "MCP状态检查失败",
            "error": str(e)
        }

@app.get("/mcp/services")
async def get_mcp_services():
    """获取MCP服务列表"""
    try:
        client = await get_universal_client()
        services = client.get_available_services()
        
        return {
            "services": services,
            "total_count": len(services)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取MCP服务信息失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)