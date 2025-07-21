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

# 导入原有模块
from main import GroqKeywordExpander, QueryBuilder, LiteratureCollector
from user_analytics import UserAnalytics

# 导入新的Elicit风格模块
from elicit_research_engine import ElicitStyleResearchEngine
from structured_data_extractor import ExtractionField, CustomColumn

app = FastAPI()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize user analytics
analytics = UserAnalytics()

# 初始化Elicit风格研究引擎
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
research_engine = ElicitStyleResearchEngine(GROQ_API_KEY) if GROQ_API_KEY else None

class ExpandRequest(BaseModel):
    keywords: str
    user_id: str

class SearchRequest(BaseModel):
    keywords: List[str]
    max_results: int = 20
    year_low: Optional[int] = None
    year_high: Optional[int] = None
    user_id: str

class ElicitSearchRequest(BaseModel):
    """Elicit风格搜索请求"""
    query: str
    max_papers: int = 50
    extraction_fields: Optional[List[str]] = None
    custom_columns: Optional[List[Dict[str, Any]]] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    user_id: str
    search_mode: str = "full"  # "full" 或 "quick"

class QuickSearchRequest(BaseModel):
    """快速搜索请求"""
    query: str
    max_papers: int = 20
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
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    expander = GroqKeywordExpander()
    
    # 处理多个关键词（用空格分隔）
    keyword_list = [kw.strip() for kw in req.keywords.split() if kw.strip()]
    
    all_expanded_terms = []
    for keyword in keyword_list:
        expanded_terms = await expander.expand_keywords(keyword)
        all_expanded_terms.extend(expanded_terms)
    
    # 去重并限制总数量
    unique_terms = list(dict.fromkeys(all_expanded_terms))  # 保持顺序去重
    final_terms = unique_terms[:12]  # 总共最多12个术语
    
    return {"expanded_terms": final_terms}

@app.post("/search_papers")
async def search_papers_api(req: SearchRequest): # Renamed to avoid conflict
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    if not req.keywords:
        raise HTTPException(status_code=400, detail="Keywords cannot be empty")
    
    query_engine = QueryBuilder(req.keywords)
    search_query = query_engine.build_query()
    
    # 不再生成xlsx文件
    collector = LiteratureCollector()
    try:
        await collector.collect(
            search_query, 
            req.max_results, 
            output_filename=None, # 不再传递文件名
            year_low=req.year_low, 
            year_high=req.year_high
        )
        return {
            "papers": collector.results
        }
    except Exception as e:
        print(f"Error during paper collection: {e}")
        raise HTTPException(status_code=500, detail=f"处理文献时发生错误: {str(e)}")

# =================== 新增Elicit风格API端点 ===================

@app.post("/elicit_search")
async def elicit_search_api(req: ElicitSearchRequest):
    """Elicit风格的智能研究搜索"""
    if not research_engine:
        raise HTTPException(status_code=500, detail="研究引擎未初始化")
    
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id, 
            "elicit_search", 
            {"query": req.query, "mode": req.search_mode}
        )
        
        if req.search_mode == "quick":
            # 快速搜索模式
            result = await research_engine.quick_search(
                query=req.query,
                max_papers=req.max_papers
            )
            return {"status": "success", "mode": "quick", "data": result}
        
        else:
            # 完整研究模式
            # 处理提取字段
            extraction_fields = None
            if req.extraction_fields:
                extraction_fields = []
                for field_name in req.extraction_fields:
                    try:
                        field = ExtractionField(field_name)
                        extraction_fields.append(field)
                    except ValueError:
                        logger.warning(f"未知的提取字段: {field_name}")
            
            # 处理自定义列
            custom_columns = None
            if req.custom_columns:
                custom_columns = []
                for col_data in req.custom_columns:
                    try:
                        column = CustomColumn(
                            name=col_data.get("name", ""),
                            description=col_data.get("description", ""),
                            extraction_prompt=col_data.get("extraction_prompt", ""),
                            data_type=col_data.get("data_type", "text")
                        )
                        custom_columns.append(column)
                    except Exception as e:
                        logger.warning(f"自定义列处理失败: {e}")
            
            # 执行完整研究
            session = await research_engine.research(
                query=req.query,
                max_papers=req.max_papers,
                extraction_fields=extraction_fields,
                custom_columns=custom_columns,
                year_min=req.year_min,
                year_max=req.year_max
            )
            
            # 导出会话摘要
            summary = research_engine.export_session_summary(session)
            
            return {
                "status": "success",
                "mode": "full",
                "session_id": session.session_id,
                "summary": summary,
                "research_matrix": session.research_matrix,
                "reasoning_trace": session.reasoning_trace
            }
    
    except Exception as e:
        logger.error(f"Elicit搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能搜索失败: {str(e)}")

@app.post("/quick_search")
async def quick_search_api(req: QuickSearchRequest):
    """快速搜索API"""
    if not research_engine:
        raise HTTPException(status_code=500, detail="研究引擎未初始化")
    
    # 验证用户登录状态
    if not verify_user_login(req.user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    try:
        # 记录用户行为
        await analytics.log_user_action(
            req.user_id, 
            "quick_search", 
            {"query": req.query}
        )
        
        result = await research_engine.quick_search(
            query=req.query,
            max_papers=req.max_papers
        )
        
        return {"status": "success", "data": result}
    
    except Exception as e:
        logger.error(f"快速搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"快速搜索失败: {str(e)}")

@app.get("/reasoning_trace/{session_id}")
async def get_reasoning_trace(session_id: str, user_id: str = Query(...)):
    """获取推理过程追踪"""
    if not verify_user_login(user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    # 这里可以从数据库或缓存中获取会话的推理过程
    # 目前返回当前引擎的推理过程
    if research_engine:
        trace = research_engine.get_reasoning_trace()
        return {"session_id": session_id, "reasoning_trace": trace}
    else:
        raise HTTPException(status_code=500, detail="研究引擎未初始化")

@app.get("/extraction_fields")
async def get_available_extraction_fields():
    """获取可用的数据提取字段"""
    fields = [
        {"name": field.value, "enum_name": field.name} 
        for field in ExtractionField
    ]
    return {"available_fields": fields}

@app.post("/analyze_query")
async def analyze_query_intent(query: str, user_id: str):
    """分析查询意图"""
    if not research_engine:
        raise HTTPException(status_code=500, detail="研究引擎未初始化")
    
    if not verify_user_login(user_id):
        raise HTTPException(status_code=401, detail="用户未登录或无效")
    
    try:
        # 使用查询处理器分析意图
        processed_query = await research_engine.query_processor.process_query(query)
        
        return {
            "original_query": query,
            "query_type": processed_query.query_intent.query_type.value,
            "complexity": processed_query.query_intent.complexity.value,
            "entities": processed_query.query_intent.entities,
            "concepts": processed_query.query_intent.concepts,
            "research_focus": processed_query.query_intent.research_focus,
            "suggested_strategy": processed_query.query_intent.suggested_search_strategy,
            "processed_keywords": processed_query.processed_keywords,
            "search_queries": processed_query.search_queries,
            "optimization_notes": processed_query.optimization_notes
        }
    
    except Exception as e:
        logger.error(f"查询分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询分析失败: {str(e)}")

# =================== 保留原有API端点 ===================

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