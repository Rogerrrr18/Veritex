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

from qwen_api_async import get_qwen_client
from universal_mcp import get_universal_client, universal_search
from langchain_workflows.paper_search_graph_v2 import search_literature_simple
from langchain_tools.mcp_google_scholar_tool import create_google_scholar_tools

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
        
        # 智能判断是否是学术搜索请求
        user_message = request.message.lower()
        
        # 定义学术搜索的关键词组合
        academic_keywords = [
            ("搜索", ["论文", "文献", "研究", "paper"]),
            ("查找", ["论文", "文献", "研究", "paper"]), 
            ("找", ["论文", "文献", "研究", "paper"]),
            ("机器学习", []),
            ("甲烷", ["干重整", "reforming"]),
            ("methane", ["reforming"]),
            ("search", ["paper", "literature", "research"]),
        ]
        
        # 明确的学术搜索词汇
        explicit_academic = ["论文", "文献", "paper", "literature", "research"]
        
        # 数量 + 学术词汇的模式
        quantity_academic_pattern = r'\d+\s*篇\s*(论文|文献|paper)'
        
        is_academic_query = False
        
        # 检查是否匹配学术搜索模式
        if any(word in user_message for word in explicit_academic):
            is_academic_query = True
        elif re.search(quantity_academic_pattern, user_message):
            is_academic_query = True
        else:
            # 检查关键词组合
            for primary, secondary in academic_keywords:
                if primary in user_message:
                    if not secondary:  # 如"机器学习"这样的单独关键词
                        is_academic_query = True
                        break
                    elif any(sec in user_message for sec in secondary):
                        is_academic_query = True
                        break
        
        if is_academic_query:
            # 使用LangGraph v2进行智能搜索
            try:
                # 提取搜索关键词和数量
                search_query = request.message
                max_results = 5  # 默认5篇
                
                # 智能提取搜索词
                if "搜索" in user_message:
                    parts = user_message.split("搜索")
                    if len(parts) > 1:
                        search_query = parts[-1].strip()
                elif "论文" in user_message:
                    search_query = user_message.replace("论文", "").replace("篇", "").strip()
                elif "文献" in user_message:
                    search_query = user_message.replace("文献", "").replace("篇", "").strip()
                
                # 提取数量信息
                numbers = re.findall(r'(\d+)篇', user_message)
                if numbers:
                    try:
                        max_results = min(int(numbers[0]), 20)  # 最多20篇
                    except:
                        pass
                
                # 处理特殊查询词
                if "甲烷" in search_query or "干重整" in search_query:
                    search_query = "methane reforming"
                
                # 清理搜索词
                search_query = re.sub(r'[我想要需要帮助查找]', '', search_query).strip()
                if not search_query:
                    search_query = "machine learning"  # 默认搜索
                
                print(f"LangGraph搜索查询: '{search_query}', 数量: {max_results}")
                
                # 使用新的LangGraph架构进行搜索
                langgraph_result = await search_literature_simple(
                    query=search_query,
                    max_results=max_results
                )
                
                print(f"LangGraph搜索结果: success={langgraph_result.get('success')}, count={langgraph_result.get('total_found', 0)}")
                
                if langgraph_result.get("success") and langgraph_result.get("formatted_results"):
                    # 直接使用LangGraph生成的标准化表格结果
                    ai_response = langgraph_result["formatted_results"]
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