from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入新的智能搜索系统
from langchain_workflows.paper_search_workflow import chat_with_search_strategy
from llm_interface import get_universal_llm, get_model_config_manager
from multi_source_engine import Paper

app = FastAPI(
    title="Paper God API - 智能对话版",
    description="学术文献智能搜索系统 - 集成LLM对话与专业关键词扩展",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 移除旧的搜索引擎实例化，改为使用智能工作流

# 聊天相关模型
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    # 新增：搜索参数（可选）
    search_params: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    history: List[ChatMessage]
    is_academic_query: bool = False
    search_results: Optional[List[Dict[str, Any]]] = None
    analysis_result: Optional[Dict[str, Any]] = None
    token_info: Optional[Dict[str, Any]] = None

# 关键词扩展请求/响应模型
class KeywordExpansionRequest(BaseModel):
    query: str

class KeywordExpansionResponse(BaseModel):
    success: bool
    original_query: str
    is_academic_query: bool
    analysis_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

# 保留搜索请求模型以兼容现有前端  
class SearchRequest(BaseModel):
    query: str
    max_results: int = 20
    enable_expansion: bool = True
    year_from: Optional[int] = None  # 起始年份筛选
    year_to: Optional[int] = None    # 结束年份筛选
    sources: Optional[List[str]] = None  # 指定数据源
    # 新增：预扩展的关键词（从关键词扩展步骤获得）
    expanded_keywords: Optional[Dict[str, Any]] = None

# 轻量埋点与注册请求模型
class RegisterRequest(BaseModel):
    invite_code: str
    user_id: str

class LogActionRequest(BaseModel):
    user_id: str
    action: str
    payload: Optional[str] = None
    ts: Optional[int] = None

# 作者分析相关请求模型
"""作者分析相关请求模型已移除"""

def format_paper_for_api(paper: Paper) -> Dict[str, Any]:
    return {
        "title": paper.title or "",
        "authors": paper.authors or [],
        "abstract": paper.abstract or "",
        "year": paper.year,
        "journal": paper.journal or "",
        "url": paper.url or "",
        "doi": paper.doi,
        "citations": paper.citations or 0,
        "source": paper.source,
        "relevance_score": paper.relevance_score or 0.0
    }

"""作者数据格式化方法已移除"""

# === 工具函数 ===
def estimate_tokens(text: str) -> int:
    """估算文本的token数量"""
    if not text:
        return 0
    
    import re
    
    # 中文字符按1.5个token计算，英文单词按1.3个token计算
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    other_chars = len(text) - chinese_chars - english_words
    
    return int(chinese_chars * 1.5 + english_words * 1.3 + other_chars * 0.5)

def calculate_total_tokens(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算对话历史的总token数"""
    total_tokens = 0
    message_count = len(history)
    
    for message in history:
        content = message.get('content', '')
        total_tokens += estimate_tokens(content)
    
    return {
        "total_tokens": total_tokens,
        "message_count": message_count,
        "average_tokens_per_message": total_tokens / message_count if message_count > 0 else 0,
        "estimated_cost_usd": total_tokens * 0.000002  # 估算成本，实际根据模型定价调整
    }

# === 关键词扩展接口 ===
@app.post("/expand_keywords", response_model=KeywordExpansionResponse)
async def expand_keywords_api(request: KeywordExpansionRequest):
    """独立的关键词扩展接口 - 仅进行智能分析，不执行搜索"""
    try:
        logger.info(f"关键词扩展请求: {request.query}")
        
        # 调用智能工作流进行分析（不执行搜索）
        result = await chat_with_search_strategy(
            query=request.query,
            force_search=False,  # 关键：不强制搜索
            max_results=0,  # 不需要搜索结果
            allow_search=False  # 禁止自动搜索，只做分析
        )
        
        # 检查是否为学术查询
        is_academic = result.get('is_academic_query', False)
        analysis_result = result.get('analysis_result', {})
        
        if is_academic and analysis_result:
            return KeywordExpansionResponse(
                success=True,
                original_query=request.query,
                is_academic_query=True,
                analysis_result=analysis_result
            )
        else:
            # 非学术查询或分析失败
            return KeywordExpansionResponse(
                success=False,
                original_query=request.query,
                is_academic_query=is_academic,
                error_message="不是学术查询或关键词分析失败"
            )
            
    except Exception as e:
        logger.error(f"关键词扩展失败: {e}")
        return KeywordExpansionResponse(
            success=False,
            original_query=request.query,
            is_academic_query=False,
            error_message=f"关键词扩展服务错误: {str(e)}"
        )

# === 新的聊天接口 ===
@app.get("/chat")
async def chat_get_info():
    """处理意外的GET请求到chat端点"""
    return {
        "message": "Chat endpoint only supports POST requests",
        "usage": "Send POST request with message and history fields",
        "example": {
            "message": "your question here",
            "history": []
        }
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """统一聊天接口 - 智能判断学术搜索还是普通对话"""
    try:
        # 转换历史记录格式
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        
        logger.info(f"收到聊天请求: {request.message}")
        
        # 提取搜索参数
        search_params = request.search_params or {}
        max_results = search_params.get('max_results', 10)
        year_from = search_params.get('year_from')
        year_to = search_params.get('year_to')
        sources = search_params.get('sources')
        
        # 调用智能工作流（仅分析，不强制搜索）
        result = await chat_with_search_strategy(
            query=request.message, 
            force_search=False,
            max_results=max_results,
            year_from=year_from,
            year_to=year_to,
            sources=sources,
            allow_search=False  # 聊天阶段不许自动搜索
        )
        
        # 处理新的响应格式
        ai_response = result.get('response', '')
        is_academic = result.get('is_academic_query', False)
        
        # 仅保留分析内容，不再插入停用提示
        
        # 构建完整的对话历史
        updated_history = history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": result.get('response', '')}
        ]
        
        # 转换回响应格式
        response_history = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in updated_history
        ]
        
        # 计算token信息
        token_info = calculate_total_tokens(updated_history)
        
        return ChatResponse(
            response=ai_response,
            history=response_history,
            is_academic_query=is_academic,
            search_results=result.get('search_results', []),
            analysis_result=result.get('analysis_result'),
            token_info=token_info
        )
        
    except Exception as e:
        logger.error(f"聊天服务错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"聊天服务错误: {str(e)}")

@app.post("/analytics/register")
async def analytics_register(req: RegisterRequest):
    """前端邀请码注册上报（轻量，无持久化）"""
    try:
        logger.info(f"[analytics] register user={req.user_id} code={req.invite_code}")
        return {"success": True}
    except Exception as e:
        logger.error(f"analytics register error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/analytics/log_action")
async def analytics_log_action(req: LogActionRequest):
    """前端用户行为上报（轻量，无持久化）"""
    try:
        logger.info(f"[analytics] action user={req.user_id} type={req.action} payload={req.payload} ts={req.ts}")
        return {"success": True}
    except Exception as e:
        logger.error(f"analytics log_action error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/search_papers")
async def search_papers_api(req: SearchRequest):
    """优化后的搜索接口 - 使用预扩展的关键词或重新分析"""
    try:
        logger.info(f"搜索请求: {req.query}")
        
        # 如果有预扩展的关键词，直接使用
        if req.expanded_keywords and req.expanded_keywords.get('hierarchical_keywords'):
            logger.info("使用预扩展的关键词执行搜索")
            
            # 直接调用多源搜索引擎，避免重复LLM分析
            try:
                from multi_source_engine import MultiSourceEngine
                search_engine = MultiSourceEngine(enable_mcp=False)
                
                # 从预扩展关键词构建查询
                hierarchical = req.expanded_keywords['hierarchical_keywords']
                exact_terms = hierarchical.get("exact_terms", {}).get("terms", [])
                core_synonyms = hierarchical.get("core_synonyms", {}).get("terms", [])
                
                if exact_terms:
                    search_query = " ".join(exact_terms[:3])
                elif core_synonyms:
                    search_query = " ".join(core_synonyms[:3])  
                else:
                    search_query = req.query
                
                logger.info(f"使用构建的查询: {search_query}")
                
                # 执行搜索
                papers = await search_engine.search_parallel_with_filters(
                    query=search_query,
                    max_results=req.max_results,
                    year_from=req.year_from,
                    year_to=req.year_to,
                    sources=req.sources
                )
                
                # 格式化结果
                formatted_papers = []
                for paper in papers:
                    formatted_papers.append({
                        "title": paper.title,
                        "authors": paper.authors,
                        "abstract": paper.abstract,
                        "year": paper.year,
                        "journal": paper.journal, 
                        "url": paper.url,
                        "doi": paper.doi,
                        "citations": paper.citations,
                        "source": paper.source,
                        "relevance_score": paper.relevance_score
                    })
                
                await search_engine.close()
                
                return {
                    "success": True,
                    "data": {
                        "papers": formatted_papers,
                        "total_found": len(formatted_papers),
                        "query_info": {
                            "original_query": req.query,
                            "search_query": search_query,
                            "is_academic_query": True,
                            "analysis_result": req.expanded_keywords,
                            "used_preexpanded_keywords": True
                        }
                    }
                }
            except Exception as e:
                logger.error(f"直接搜索失败，回退到智能工作流: {e}")
                # 如果直接搜索失败，回退到原有逻辑
        
        # 没有预扩展关键词，使用智能工作流（包含重新分析）
        logger.info("使用智能工作流执行搜索（包含关键词分析）")
        result = await chat_with_search_strategy(
            query=req.query, 
            force_search=True,
            max_results=req.max_results,
            year_from=req.year_from,
            year_to=req.year_to,
            sources=req.sources
        )
        
        if result.get('success') and result.get('search_results'):
            return {
                "success": True,
                "data": {
                    "papers": result['search_results'],
                    "total_found": len(result['search_results']),
                    "query_info": {
                        "original_query": req.query,
                        "is_academic_query": result.get('is_academic_query', True),
                        "analysis_result": result.get('analysis_result')
                    },
                    "performance": {
                        "intelligent_workflow": True,
                        "llm_analysis": True
                    }
                }
            }
        else:
            return {
                "success": False,
                "error": result.get('error_message', '搜索失败'),
                "data": {"papers": [], "total_found": 0}
            }
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {"papers": [], "total_found": 0}
        }

"""作者分析API接口已移除"""

# ================ 原有API接口 ================

@app.get("/health")
async def health_check():
    """健康检查 - 检查LLM和搜索系统状态"""
    try:
        # 检查LLM系统
        config_manager = get_model_config_manager()
        llm_client = await get_universal_llm()
        model_info = llm_client.get_model_info()
        
        return {
            "status": "healthy",
            "version": "3.0.0",
            "features": {
                "intelligent_chat": True,
                "academic_analysis": True,
                "paper_search": True,
                "keyword_expansion": True,
                "langraph_workflow": True
            },
            "llm_system": {
                "active_model": model_info.get("active_model"),
                "available_models": model_info.get("available_models", []),
                "model_name": model_info.get("model_name")
            },
            "data_sources": ["arxiv", "google_scholar", "crossref", "pubmed"]
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e),
            "version": "3.0.0"
        }

@app.get("/")
async def root():
    return {
        "message": "Paper God API - 智能对话式学术搜索系统",
        "version": "3.0.0",
        "features": [
            "智能对话交互",
            "专业学术分析",
            "层次化关键词扩展", 
            "多源文献搜索",
            "LangGraph工作流"
        ],
        "endpoints": {
            "/chat": "智能对话接口（推荐）", 
            "/search_papers": "论文搜索（兼容）", 
            "/health": "健康检查",
            "/models": "模型管理"
        }
    }

@app.get("/models")
async def get_models():
    """获取可用LLM模型列表"""
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

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    try:
        llm_client = await get_universal_llm()
        await llm_client.close()
        logger.info("LLM客户端资源已清理")
    except Exception as e:
        logger.error(f"资源清理失败: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)