"""
集成后端 - 同时支持聊天和通用MCP功能
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any, Union
import sys
import os
import re

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 使用新的统一LLM接口
from llm_interface import get_universal_llm, get_llm_client
from model_config import get_model_config_manager
from universal_mcp import get_universal_client, universal_search
from langchain_workflows.paper_search_graph_v2 import chat_with_search_strategy
# 注释掉不再使用的MCP工具导入
# from langchain_tools.mcp_google_scholar_tool import create_google_scholar_tools

# FastAPI应用初始化
app = FastAPI(
    title="Integrated Chat + MCP API", 
    version="2.0.0",
    description="集成聊天和通用MCP功能的统一后端"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
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
        # 检查LLM API
        llm_client = await get_universal_llm()
        test_response = await llm_client.simple_chat("你好")
        model_info = llm_client.get_model_info()
        
        # 检查MCP系统
        mcp_client = await get_universal_client()
        mcp_services = mcp_client.get_available_services()
        enabled_count = sum(1 for s in mcp_services.values() if s.get("enabled", True))
        
        return {
            "status": "healthy",
            "llm_api": "connected",
            "active_model": model_info.get("active_model", "unknown"),
            "model_name": model_info.get("model_name", "unknown"),
            "available_models": model_info.get("available_models", []),
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
        
        # 简化的路由判断：基础问候 vs 需要LangGraph处理
        user_message = request.message.lower()
        
        # 简单问候模式 - 直接快速响应
        simple_greetings = [
            "你好", "您好", "hi", "hello", 
            "谢谢", "thanks", "thank you",
            "再见", "bye", "goodbye"
        ]
        
        # 如果是简单问候（短小且匹配问候词），走快速响应
        is_simple_greeting = (
            len(request.message.strip()) <= 10 and 
            any(greeting in user_message for greeting in simple_greetings)
        )
        
        # 其他所有情况都交给LangGraph工作流处理（包括复杂问题、学术查询等）
        is_academic_query = not is_simple_greeting
        
        if is_academic_query:
            # 使用LangGraph v2进行智能处理
            try:
                print(f"🔄 交给LangGraph工作流处理: '{request.message}'")
                
                # 直接传递原始查询给LangGraph，让其智能处理
                langgraph_result = await chat_with_search_strategy(
                    query=request.message  # 传递原始用户输入
                )
                
                print(f"LangGraph结果: success={langgraph_result.get('success')}, 需要搜索策略={langgraph_result.get('need_search_strategy')}")
                
                if langgraph_result.get("success") and langgraph_result.get("response"):
                    # 直接使用LangGraph生成的响应（问答或搜索策略）
                    ai_response = langgraph_result["response"]
                else:
                    error_msg = langgraph_result.get("error_message", "未知错误")
                    ai_response = f"很抱歉，搜索过程中出现问题：{error_msg}\n\n建议：\n1. 尝试使用不同的关键词\n2. 确保网络连接正常\n3. 稍后重试"
                    
            except Exception as search_error:
                # 搜索出错时的处理
                import traceback
                print(f"LangGraph搜索出错: {search_error}")
                print("详细错误堆栈:")
                traceback.print_exc()
                ai_response = f"智能搜索系统暂时不可用: {str(search_error)}\n\n请稍后重试或联系管理员。"
        else:
            # 简单问候的快速响应
            try:
                print(f"⚡ 快速问候响应: '{request.message}'")
                
                if "你好" in user_message or "您好" in user_message:
                    ai_response = "你好！我是你的智能助手，很高兴为您服务。有什么可以帮助您的吗？"
                elif any(word in user_message for word in ["谢谢", "thanks", "thank you"]):
                    ai_response = "不客气！如果还有其他问题，随时都可以问我。"
                elif any(word in user_message for word in ["再见", "bye", "goodbye"]):
                    ai_response = "再见！祝您一切顺利，有需要时随时回来找我。"
                else:
                    # 其他简单问候的默认响应
                    ai_response = "你好！我是你的智能学术助手。我可以帮助您解答问题、搜索文献，或者讨论学术话题。有什么可以帮助您的吗？"
                    
            except Exception as chat_error:
                print(f"快速响应出错: {chat_error}")
                ai_response = "你好！很高兴为您服务，有什么可以帮助您的吗？"
        
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
    try:
        config_manager = get_model_config_manager()
        llm_client = await get_universal_llm()
        model_info = llm_client.get_model_info()
        
        # 构建模型列表
        models = []
        for model_name in model_info.get("available_models", []):
            models.append({
                "id": model_name,
                "name": model_name.title(),
                "description": f"{model_name.title()} 模型",
                "active": model_name == model_info.get("active_model")
            })
        
        return {
            "active_model": model_info.get("active_model"),
            "models": models,
            "model_info": {
                "current_model_name": model_info.get("model_name"),
                "temperature": model_info.get("temperature"),
                "max_tokens": model_info.get("max_tokens")
            }
        }
    except Exception as e:
        return {
            "error": f"获取模型信息失败: {str(e)}",
            "models": []
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

# === Google Scholar MCP工具专门接口 ===
class GoogleScholarKeywordRequest(BaseModel):
    query: str
    num_results: int = 10

class GoogleScholarAdvancedRequest(BaseModel):
    query: str
    author: Optional[str] = None
    year_low: Optional[int] = None
    year_high: Optional[int] = None
    num_results: int = 10

class AuthorInfoRequest(BaseModel):
    author_name: str

@app.post("/google_scholar/search_keywords")
async def google_scholar_keywords(request: GoogleScholarKeywordRequest):
    """Google Scholar关键词搜索"""
    try:
        tools = create_google_scholar_tools()
        keyword_tool = tools[0]  # GoogleScholarKeywordSearchTool
        
        result = await keyword_tool._arun(
            query=request.query,
            num_results=request.num_results
        )
        
        return {"success": True, "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关键词搜索失败: {str(e)}")

@app.post("/google_scholar/search_advanced")
async def google_scholar_advanced(request: GoogleScholarAdvancedRequest):
    """Google Scholar高级搜索"""
    try:
        tools = create_google_scholar_tools()
        advanced_tool = tools[1]  # GoogleScholarAdvancedSearchTool
        
        # 构建参数字典
        params = {"query": request.query, "num_results": request.num_results}
        if request.author:
            params["author"] = request.author
        if request.year_low:
            params["year_low"] = request.year_low
        if request.year_high:
            params["year_high"] = request.year_high
        
        result = await advanced_tool._arun(**params)
        
        return {"success": True, "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"高级搜索失败: {str(e)}")

@app.post("/google_scholar/author_info")
async def google_scholar_author_info(request: AuthorInfoRequest):
    """获取作者信息"""
    try:
        tools = create_google_scholar_tools()
        author_tool = tools[2]  # AuthorInfoTool
        
        result = await author_tool._arun(author_name=request.author_name)
        
        return {"success": True, "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取作者信息失败: {str(e)}")

@app.get("/google_scholar/test")
async def test_google_scholar_tools():
    """测试Google Scholar MCP工具功能"""
    try:
        tools = create_google_scholar_tools()
        
        # 简单测试三个工具
        results = {
            "tools_created": len(tools),
            "tool_names": [tool.name for tool in tools],
            "test_results": {}
        }
        
        # 测试关键词搜索
        try:
            test_result1 = await tools[0]._arun(query="AI", num_results=2)
            results["test_results"]["keyword_search"] = "success"
        except Exception as e:
            results["test_results"]["keyword_search"] = f"failed: {str(e)}"
        
        # 测试高级搜索
        try:
            test_result2 = await tools[1]._arun(query="machine learning", author="Smith", num_results=2)
            results["test_results"]["advanced_search"] = "success"
        except Exception as e:
            results["test_results"]["advanced_search"] = f"failed: {str(e)}"
        
        # 测试作者信息
        try:
            test_result3 = await tools[2]._arun(author_name="Test Author")
            results["test_results"]["author_info"] = "success"
        except Exception as e:
            results["test_results"]["author_info"] = f"failed: {str(e)}"
        
        return {"success": True, "results": results}
        
    except Exception as e:
        return {"success": False, "error": f"工具测试失败: {str(e)}"}

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