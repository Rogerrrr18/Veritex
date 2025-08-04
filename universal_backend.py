"""
通用MCP后端API - 支持零代码集成多个学术搜索服务
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any, Union
import sys
import os
import asyncio

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from universal_mcp import get_universal_client, universal_search

# FastAPI应用初始化
app = FastAPI(
    title="Universal MCP API", 
    version="2.0.0",
    description="通用MCP学术搜索API - 零代码集成多个数据源"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求/响应模型
class UniversalSearchRequest(BaseModel):
    """通用搜索请求"""
    query: str
    sources: Optional[List[str]] = None
    strategy: Optional[str] = None
    limit: Optional[int] = 20
    category: Optional[str] = None
    year: Optional[str] = None
    venue: Optional[str] = None

class UniversalSearchResponse(BaseModel):
    """通用搜索响应"""
    success: bool
    papers: List[Dict[str, Any]] = []
    total_count: int = 0
    source_stats: Optional[Dict[str, int]] = None
    errors: Optional[List[str]] = None
    strategy: Optional[str] = None
    query: str = ""

class ServiceInfo(BaseModel):
    """服务信息"""
    services: Dict[str, Any]
    strategies: Dict[str, Any]
    total_services: int

class AddServiceRequest(BaseModel):
    """添加服务请求"""
    service_id: str
    service_config: Dict[str, Any]

class ServiceToggleRequest(BaseModel):
    """服务开关请求"""
    service_id: str
    enabled: bool

# API路由
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Universal MCP API is running!",
        "version": "2.0.0",
        "features": [
            "零代码添加新MCP服务",
            "统一数据格式输出", 
            "并行多源搜索",
            "智能去重和排序",
            "预定义搜索策略"
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        client = await get_universal_client()
        services = client.get_available_services()
        enabled_count = sum(1 for s in services.values() if s.get("enabled", True))
        
        return {
            "status": "healthy",
            "total_services": len(services),
            "enabled_services": enabled_count,
            "available_strategies": list(client.get_search_strategies().keys())
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/universal_search", response_model=UniversalSearchResponse)
async def universal_search_endpoint(request: UniversalSearchRequest):
    """
    通用搜索接口 - 支持多源并行搜索
    """
    try:
        # 构建搜索参数
        search_params = {
            "limit": request.limit,
            "category": request.category,
            "year": request.year,
            "venue": request.venue
        }
        
        # 移除None值
        search_params = {k: v for k, v in search_params.items() if v is not None}
        
        # 执行搜索
        result = await universal_search(
            query=request.query,
            sources=request.sources,
            strategy=request.strategy,
            **search_params
        )
        
        return UniversalSearchResponse(
            success=result.get("success", False),
            papers=result.get("papers", []),
            total_count=result.get("total_count", 0),
            source_stats=result.get("source_stats"),
            errors=result.get("errors"),
            strategy=request.strategy,
            query=request.query
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@app.post("/search_by_strategy")
async def search_by_strategy(strategy: str, query: str, limit: int = 20):
    """
    按策略搜索
    """
    try:
        client = await get_universal_client()
        result = await client.search_with_strategy(strategy, query, limit=limit)
        
        return {
            "success": result.get("success", False),
            "papers": result.get("papers", []),
            "total_count": result.get("total_count", 0),
            "source_stats": result.get("source_stats"),
            "strategy": strategy
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略搜索失败: {str(e)}")

@app.post("/search_single_source")
async def search_single_source(source: str, query: str, limit: int = 20, **kwargs):
    """
    单源搜索
    """
    try:
        client = await get_universal_client()
        result = await client.search_service(source, query=query, limit=limit, **kwargs)
        
        return {
            "success": result.get("success", False),
            "papers": [p.to_dict() if hasattr(p, 'to_dict') else p for p in result.get("papers", [])],
            "count": result.get("count", 0),
            "source": source
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"单源搜索失败: {str(e)}")

@app.get("/services", response_model=ServiceInfo)
async def get_services():
    """
    获取所有服务和策略信息
    """
    try:
        client = await get_universal_client()
        services = client.get_available_services()
        strategies = client.get_search_strategies()
        
        return ServiceInfo(
            services=services,
            strategies=strategies,
            total_services=len(services)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务信息失败: {str(e)}")

@app.post("/services/add")
async def add_service(request: AddServiceRequest):
    """
    添加新的MCP服务（动态配置）
    """
    try:
        client = await get_universal_client()
        
        # 动态更新配置
        client.config["mcpServices"][request.service_id] = request.service_config
        
        # 保存配置（如果需要持久化）
        import json
        with open(client.config_file, 'w', encoding='utf-8') as f:
            json.dump(client.config, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"服务 {request.service_id} 添加成功",
            "service": request.service_config
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"添加服务失败: {str(e)}")

@app.post("/services/toggle")
async def toggle_service(request: ServiceToggleRequest):
    """
    启用/禁用服务
    """
    try:
        client = await get_universal_client()
        
        if request.service_id not in client.config.get("mcpServices", {}):
            raise HTTPException(status_code=404, detail=f"服务未找到: {request.service_id}")
        
        # 更新服务状态
        client.config["mcpServices"][request.service_id]["enabled"] = request.enabled
        
        # 保存配置
        import json
        with open(client.config_file, 'w', encoding='utf-8') as f:
            json.dump(client.config, f, indent=2, ensure_ascii=False)
        
        action = "启用" if request.enabled else "禁用"
        return {
            "success": True,
            "message": f"服务 {request.service_id} 已{action}",
            "enabled": request.enabled
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换服务状态失败: {str(e)}")

@app.get("/services/{service_id}/status")
async def get_service_status(service_id: str):
    """
    检查单个服务状态
    """
    try:
        client = await get_universal_client()
        
        # 测试搜索以检查服务状态
        result = await client.search_service(service_id, query="test", limit=1)
        
        return {
            "service_id": service_id,
            "status": "healthy" if result.get("success") else "error",
            "error": result.get("error") if not result.get("success") else None,
            "last_check": "just_now"
        }
        
    except Exception as e:
        return {
            "service_id": service_id,
            "status": "error",
            "error": str(e),
            "last_check": "just_now"
        }

@app.get("/strategies")
async def get_strategies():
    """
    获取所有搜索策略
    """
    try:
        client = await get_universal_client()
        strategies = client.get_search_strategies()
        
        return {
            "strategies": strategies,
            "total_count": len(strategies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略失败: {str(e)}")

@app.post("/strategies/add")
async def add_strategy(strategy_name: str, strategy_config: Dict[str, Any]):
    """
    添加新的搜索策略
    """
    try:
        client = await get_universal_client()
        
        # 添加策略
        if "search_strategies" not in client.config:
            client.config["search_strategies"] = {}
        
        client.config["search_strategies"][strategy_name] = strategy_config
        
        # 保存配置
        import json
        with open(client.config_file, 'w', encoding='utf-8') as f:
            json.dump(client.config, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"策略 {strategy_name} 添加成功",
            "strategy": strategy_config
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"添加策略失败: {str(e)}")

@app.get("/stats")
async def get_stats():
    """
    获取系统统计信息
    """
    try:
        client = await get_universal_client()
        services = client.get_available_services()
        strategies = client.get_search_strategies()
        
        enabled_services = [s for s in services.values() if s.get("enabled", True)]
        
        return {
            "total_services": len(services),
            "enabled_services": len(enabled_services),
            "disabled_services": len(services) - len(enabled_services),
            "total_strategies": len(strategies),
            "service_types": list(set(s.get("base_url", "").split("//")[-1].split("/")[0] for s in services.values() if s.get("base_url"))),
            "config_version": client.config.get("version", "unknown")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

# 兼容性路由（为了保持向后兼容）
@app.post("/search_papers")
async def legacy_search_papers(query: str, limit: int = 10):
    """
    兼容性接口 - 使用快速策略搜索
    """
    try:
        result = await universal_search(query=query, strategy="fast", limit=limit)
        
        return {
            "success": result.get("success", False),
            "data": {"data": result.get("papers", [])},
            "count": result.get("total_count", 0),
            "source": "universal"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"搜索失败: {str(e)}",
            "data": None,
            "count": 0
        }

@app.post("/search_arxiv")
async def legacy_search_arxiv(query: str, max_results: int = 10, category: str = None):
    """
    兼容性接口 - arXiv搜索
    """
    try:
        client = await get_universal_client()
        result = await client.search_service("arxiv", query=query, limit=max_results, category=category)
        
        return {
            "success": result.get("success", False),
            "data": {"data": [p.to_dict() if hasattr(p, 'to_dict') else p for p in result.get("papers", [])]},
            "count": result.get("count", 0),
            "source": "arxiv"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"arXiv搜索失败: {str(e)}",
            "data": None,
            "count": 0,
            "source": "arxiv"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8005)