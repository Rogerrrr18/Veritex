from fastapi import FastAPI, Query, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import os
import time
import re
import json
import logging

# 导入MCP客户端
from mcp_client import MCPClient, SearchResult, get_mcp_client

# 导入保留的核心模块
from main import GroqKeywordExpander
from user_analytics import UserAnalytics

app = FastAPI()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize user analytics
analytics = UserAnalytics()

# 初始化MCP客户端和核心组件
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
keyword_expander = GroqKeywordExpander() if GROQ_API_KEY else None

# =================== API请求模型 ===================

class ExpandRequest(BaseModel):
    keywords: str
    user_id: str

class SearchRequest(BaseModel):
    keywords: List[str]
    max_results: int = 20
    year_low: Optional[int] = None
    year_high: Optional[int] = None
    user_id: str
    sources: Optional[List[str]] = None

class MCPSearchRequest(BaseModel):
    """MCP增强搜索请求"""
    query: str
    max_results: int = 50
    sources: Optional[List[str]] = None
    enable_analysis: bool = True
    enable_visualization: bool = False
    user_id: str

class DataAnalysisRequest(BaseModel):
    """数据分析请求"""
    papers: List[Dict[str, Any]]
    analysis_type: str = "basic"
    user_id: str

class VisualizationRequest(BaseModel):
    """可视化请求"""
    data: List[Dict[str, Any]]
    chart_type: str = "network"
    user_id: str

def verify_user_login(user_id: str) -> bool:
    """验证用户是否已登录"""
    try:
        # 验证用户ID是否存在于数据库中
        from user_analytics import UserAnalytics
        analytics = UserAnalytics()
        user_result = analytics.supabase.table('users').select('id').eq('id', user_id).execute()
        return len(user_result.data) > 0
    except Exception as e:
        print(f"用户验证失败: {e}")
        return False

@app.post("/expand_keywords")
async def expand_keywords_api(req: ExpandRequest):
    """关键词扩展API - 使用Groq进行智能扩展"""
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    if not keyword_expander:
        raise HTTPException(status_code=500, detail="关键词扩展器未初始化")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id, 
            "expand_keywords", 
            {"keywords": req.keywords}
        )
        
        # 使用Groq进行关键词扩展
        expanded_terms = await keyword_expander.expand_keywords(req.keywords)
        
        return {
            "expanded_terms": expanded_terms,
            "original_keywords": req.keywords,
            "strategy": "groq_expansion",
            "count": len(expanded_terms)
        }
        
    except Exception as e:
        logger.error(f"关键词扩展失败: {e}")
        raise HTTPException(status_code=500, detail=f"关键词扩展失败: {str(e)}")

# 新增MCP增强搜索API
@app.post("/mcp_search")
async def mcp_search_api(req: MCPSearchRequest):
    """MCP增强搜索API - 集成多源搜索、数据分析和可视化"""
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id, 
            "mcp_enhanced_search", 
            {"query": req.query, "sources": req.sources}
        )
        
        # 获取MCP客户端
        mcp_client = await get_mcp_client()
        
        # 1. 多源搜索
        search_results = await mcp_client.multi_source_search(
            query=req.query,
            max_results=req.max_results,
            sources=req.sources
        )
        
        # 转换为字典格式便于分析
        papers_data = []
        for result in search_results:
            paper_dict = {
                "title": result.title,
                "authors": result.authors,
                "year": result.year,
                "abstract": result.abstract,
                "url": result.url,
                "source": result.source,
                "citations": result.citations,
                "venue": result.venue
            }
            papers_data.append(paper_dict)
        
        response_data = {
            "papers": papers_data,
            "total_found": len(papers_data),
            "sources_used": req.sources or ["arxiv", "pubmed", "semantic_scholar"],
            "search_mode": "mcp_enhanced"
        }
        
        # 2. 可选数据分析
        if req.enable_analysis and papers_data:
            try:
                analysis_result = await mcp_client.analyze_data(
                    data=papers_data,
                    analysis_type="academic_papers"
                )
                response_data["analysis"] = analysis_result
            except Exception as e:
                logger.warning(f"数据分析失败: {e}")
                response_data["analysis"] = {"error": str(e)}
        
        # 3. 可选可视化
        if req.enable_visualization and papers_data:
            try:
                viz_result = await mcp_client.generate_visualization(
                    data=papers_data,
                    chart_type="timeline"
                )
                response_data["visualization"] = viz_result
            except Exception as e:
                logger.warning(f"可视化生成失败: {e}")
                response_data["visualization"] = {"error": str(e)}
        
        return response_data
        
    except Exception as e:
        logger.error(f"MCP增强搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"增强搜索失败: {str(e)}")

@app.post("/analyze_data")
async def analyze_data_api(req: DataAnalysisRequest):
    """数据分析API - 使用MCP进行学术数据分析"""
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id,
            "data_analysis",
            {"papers_count": len(req.papers), "analysis_type": req.analysis_type}
        )
        
        # 获取MCP客户端并进行数据分析
        mcp_client = await get_mcp_client()
        analysis_result = await mcp_client.analyze_data(
            data=req.papers,
            analysis_type=req.analysis_type
        )
        
        return {
            "status": "success",
            "analysis_type": req.analysis_type,
            "data_count": len(req.papers),
            "result": analysis_result
        }
        
    except Exception as e:
        logger.error(f"数据分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据分析失败: {str(e)}")

@app.post("/generate_visualization")
async def generate_visualization_api(req: VisualizationRequest):
    """可视化生成API - 使用MCP生成学术数据可视化"""
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id,
            "generate_visualization",
            {"data_count": len(req.data), "chart_type": req.chart_type}
        )
        
        # 获取MCP客户端并生成可视化
        mcp_client = await get_mcp_client()
        viz_result = await mcp_client.generate_visualization(
            data=req.data,
            chart_type=req.chart_type
        )
        
        return {
            "status": "success",
            "chart_type": req.chart_type,
            "data_count": len(req.data),
            "visualization": viz_result
        }
        
    except Exception as e:
        logger.error(f"可视化生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"可视化生成失败: {str(e)}")

@app.post("/search_papers")
async def search_papers_api(req: SearchRequest):
    """传统搜索API - 保持向后兼容"""
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    if not req.keywords:
        raise HTTPException(status_code=400, detail="Keywords cannot be empty")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id, 
            "search_papers_traditional", 
            {"keywords": req.keywords, "max_results": req.max_results}
        )
        
        # 使用MCP客户端进行搜索
        mcp_client = await get_mcp_client()
        query = " ".join(req.keywords)
        
        # 使用MCP多源搜索
        search_results = await mcp_client.multi_source_search(
            query=query,
            max_results=req.max_results,
            sources=req.sources
        )
        
        # 转换为前端期望的格式
        papers = []
        for result in search_results:
            paper = {
                "title": result.title,
                "authors": "; ".join(result.authors) if result.authors else "",
                "year": str(result.year) if result.year else "",
                "abstract": result.abstract,
                "url": result.url
            }
            papers.append(paper)
        
        return {
            "papers": papers,
            "source": "mcp_enhanced",
            "total_found": len(papers)
        }
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

# =================== MCP系统管理API端点 ===================

@app.get("/mcp/health")
async def mcp_health_check():
    """MCP服务器健康检查"""
    try:
        mcp_client = await get_mcp_client()
        health_status = await mcp_client.health_check()
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "servers": health_status
        }
    except Exception as e:
        logger.error(f"MCP健康检查失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

@app.get("/mcp/servers")
async def list_mcp_servers():
    """列出所有MCP服务器配置"""
    try:
        mcp_client = await get_mcp_client()
        servers_info = []
        
        for server_id, server in mcp_client.servers.items():
            server_info = {
                "id": server_id,
                "name": server.name,
                "type": server.server_type.value,
                "endpoint": server.endpoint,
                "enabled": server.enabled,
                "config": server.config
            }
            servers_info.append(server_info)
        
        return {
            "status": "success",
            "servers": servers_info
        }
    except Exception as e:
        logger.error(f"获取MCP服务器列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务器列表失败: {str(e)}")

@app.post("/build_knowledge_graph")
async def build_knowledge_graph_api(req: DataAnalysisRequest):
    """构建知识图谱API - 基于论文数据构建学术知识图谱"""
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id,
            "build_knowledge_graph",
            {"papers_count": len(req.papers)}
        )
        
        # 转换数据格式
        search_results = []
        for paper in req.papers:
            result = SearchResult(
                title=paper.get("title", ""),
                authors=paper.get("authors", []) if isinstance(paper.get("authors"), list) else paper.get("authors", "").split("; "),
                year=paper.get("year"),
                abstract=paper.get("abstract", ""),
                url=paper.get("url", ""),
                source=paper.get("source", "unknown")
            )
            search_results.append(result)
        
        # 获取MCP客户端并构建知识图谱
        mcp_client = await get_mcp_client()
        graph_result = await mcp_client.build_knowledge_graph(search_results)
        
        return {
            "status": "success",
            "papers_processed": len(req.papers),
            "graph_data": graph_result
        }
        
    except Exception as e:
        logger.error(f"知识图谱构建失败: {e}")
        raise HTTPException(status_code=500, detail=f"知识图谱构建失败: {str(e)}")

# =================== 用户分析和管理API端点 ===================

# 用户数据监测API端点
@app.get("/analytics/user_stats")
async def get_user_stats():
    """获取用户统计数据"""
    try:
        stats = analytics.get_user_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户统计失败: {str(e)}")

@app.get("/analytics/user_actions")
async def get_user_actions_stats(days: int = Query(7, ge=1, le=30)):
    """获取用户行为统计"""
    try:
        stats = analytics.get_user_actions_stats(days)
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户行为统计失败: {str(e)}")

@app.get("/analytics/search_analytics")
async def get_search_analytics():
    """获取搜索行为分析"""
    try:
        analytics_data = analytics.get_search_analytics()
        return {"success": True, "data": analytics_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取搜索分析失败: {str(e)}")

@app.get("/analytics/real_time")
async def get_real_time_stats():
    """获取实时统计数据"""
    try:
        stats = analytics.get_real_time_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实时统计失败: {str(e)}")

@app.get("/analytics/user_timeline/{user_id}")
async def get_user_timeline(user_id: str, limit: int = Query(50, ge=1, le=200)):
    """获取用户时间线"""
    try:
        timeline = analytics.get_user_timeline(user_id, limit)
        return {"success": True, "data": timeline}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户时间线失败: {str(e)}")

@app.get("/analytics/daily_report")
async def get_daily_report(date: Optional[str] = Query(None)):
    """获取每日报告"""
    try:
        report = analytics.generate_daily_report(date)
        return {"success": True, "data": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成每日报告失败: {str(e)}")

@app.get("/analytics/dashboard")
async def get_dashboard_data():
    """获取仪表板数据"""
    try:
        dashboard_data = {
            "user_stats": analytics.get_user_stats(),
            "real_time_stats": analytics.get_real_time_stats(),
            "action_stats": analytics.get_user_actions_stats(7),
            "search_analytics": analytics.get_search_analytics(),
            "today_report": analytics.generate_daily_report()
        }
        return {"success": True, "data": dashboard_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取仪表板数据失败: {str(e)}") 