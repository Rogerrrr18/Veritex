from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入新的智能搜索系统
from langchain_workflows.paper_search_workflow import get_intelligent_paper_search_agent
from llm_interface import get_universal_llm, get_model_config_manager
from multi_source_engine import Paper
from performance_monitor import track_chat_performance, get_performance_monitor
from prompt_utils import get_chat_conversation_prompt

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
    # 模式：'chat-only' | 'auto-search'
    mode: Optional[str] = None

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
    """统一的论文格式化函数 - 确保数据完整性和一致性"""
    try:
        # 安全获取所有字段，确保类型正确
        formatted_paper = {
            "title": str(paper.title) if paper.title else "",
            "authors": list(paper.authors) if paper.authors and isinstance(paper.authors, (list, tuple)) else [],
            "abstract": str(paper.abstract) if paper.abstract else "",
            "year": int(paper.year) if paper.year is not None and str(paper.year).isdigit() else None,
            "journal": str(paper.journal) if paper.journal else "",
            "url": str(paper.url) if paper.url else "",
            "doi": str(paper.doi) if paper.doi else None,
            "citations": int(paper.citations) if paper.citations is not None else 0,
            "source": str(paper.source) if paper.source else "unknown",
            "relevance_score": float(paper.relevance_score) if paper.relevance_score is not None else 0.0,
            # 附加字段
            "pmid": str(paper.pmid) if hasattr(paper, 'pmid') and paper.pmid else None,
            "keywords": list(paper.keywords) if hasattr(paper, 'keywords') and paper.keywords and isinstance(paper.keywords, (list, tuple)) else None
        }
        
        # 数据验证和清理
        # 确保作者列表中的每个元素都是字符串
        if formatted_paper["authors"]:
            formatted_paper["authors"] = [str(auth) for auth in formatted_paper["authors"] if auth]
        
        # 年份合理性检查
        if formatted_paper["year"] and (formatted_paper["year"] < 1900 or formatted_paper["year"] > 2030):
            formatted_paper["year"] = None
        
        # 引用数非负检查
        if formatted_paper["citations"] < 0:
            formatted_paper["citations"] = 0
        
        # 相关性得分范围检查
        if formatted_paper["relevance_score"] < 0:
            formatted_paper["relevance_score"] = 0.0
        
        return formatted_paper
        
    except Exception as e:
        logger.error(f"论文格式化失败，跳过该论文: {e}")
        # 格式化失败的论文直接跳过，不返回虚假数据
        return None

"""作者数据格式化方法已移除"""

# === 快速意图预筛选函数 ===
def quick_intent_filter(message: str) -> Optional[str]:
    """快速意图预筛选 - 对明显的闲聊直接识别，避免复杂工作流"""
    message_lower = message.lower().strip()
    
    # 明显的问候语和感谢语
    greeting_patterns = [
        "你好", "hello", "hi", "嗨", "哈喽",
        "谢谢", "thank", "感谢",
        "再见", "bye", "拜拜", "88",
        "早上好", "下午好", "晚上好", "晚安"
    ]
    
    # 明显的系统使用咨询
    system_patterns = [
        "怎么用", "如何使用", "使用方法", "操作指南",
        "这是什么", "你是谁", "什么功能", "能做什么"
    ]
    
    # 明显的天气/日常闲聊
    casual_patterns = [
        "天气", "今天", "明天", "心情", "电影", "音乐",
        "吃饭", "睡觉", "工作", "周末", "假期"
    ]
    
    # 短消息通常是闲聊
    if len(message.strip()) <= 10:
        for pattern in greeting_patterns:
            if pattern in message_lower:
                return "闲聊"
    
    # 检查各种闲聊模式
    all_casual_patterns = greeting_patterns + system_patterns + casual_patterns
    for pattern in all_casual_patterns:
        if pattern in message_lower:
            return "闲聊"
    
    return None  # 无法快速判断，需要进入完整工作流

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
        
        # 调用新的智能工作流进行分析（不执行搜索）
        agent = get_intelligent_paper_search_agent()
        result = await agent.search_papers(
            query=request.query,
            mode="chat&plan",  # 使用chat&plan模式，只分析不自动搜索
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
    import time
    start_time = time.time()
    
    try:
        # 转换历史记录格式
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        
        logger.info(f"收到聊天请求: {request.message}")
        
        # 🚀 快速意图预筛选 - 对明显闲聊使用LLM生成自然回复
        quick_intent = quick_intent_filter(request.message)
        if quick_intent == "闲聊":
            logger.info(f"⚡ 快速预筛选命中闲聊，使用LLM生成自然回复")
            
            try:
                # 使用LLM生成自然的闲聊回复
                llm_client = await get_universal_llm()
                prompt = get_chat_conversation_prompt(request.message)
                ai_response = await llm_client.simple_chat(prompt)
                
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
                
                # 跟踪快速闲聊性能
                response_time = time.time() - start_time
                track_chat_performance(
                    request_type="fast_chat_llm",
                    response_time=response_time,
                    llm_calls=1,
                    is_fast_path=True,
                    token_count=estimate_tokens(request.message + ai_response)
                )
                
                logger.info(f"⚡ 快速闲聊完成 (耗时: {response_time:.3f}s, LLM调用: 1次)")
                
                return ChatResponse(
                    response=ai_response,
                    history=response_history,
                    is_academic_query=False,
                    search_results=[],
                    analysis_result=None,
                    token_info={
                        "total_tokens": estimate_tokens(request.message + ai_response),
                        "fast_path": True,
                        "response_time": response_time,
                        "llm_calls": 1
                    }
                )
                
            except Exception as e:
                logger.error(f"快速闲聊LLM调用失败: {e}")
                # 降级到简单预定义回复
                fallback_response = "你好！我是Paper God学术搜索助手，专门帮助您查找和分析学术文献。有什么学术问题我可以帮您解答吗？"
                
                updated_history = history + [
                    {"role": "user", "content": request.message},
                    {"role": "assistant", "content": fallback_response}
                ]
                
                response_history = [
                    ChatMessage(role=msg["role"], content=msg["content"])
                    for msg in updated_history
                ]
                
                response_time = time.time() - start_time
                track_chat_performance(
                    request_type="fast_chat_fallback",
                    response_time=response_time,
                    llm_calls=0,
                    is_fast_path=True,
                    token_count=estimate_tokens(request.message + fallback_response),
                    error_occurred=True
                )
                
                return ChatResponse(
                    response=fallback_response,
                    history=response_history,
                    is_academic_query=False,
                    search_results=[],
                    analysis_result=None,
                    token_info={
                        "total_tokens": estimate_tokens(request.message + fallback_response),
                        "fast_path": True,
                        "response_time": response_time,
                        "llm_calls": 0,
                        "error": str(e)
                    }
                )
        
        # 提取搜索参数
        search_params = request.search_params or {}
        max_results = search_params.get('max_results', 10)
        year_from = search_params.get('year_from')
        year_to = search_params.get('year_to')
        sources = search_params.get('sources')
        
        # 进入完整智能工作流（记录开始时间）
        logger.info(f"🤖 进入完整智能工作流处理")
        workflow_start = time.time()
        
        # 调用优化后的智能工作流（单次调用完成所有处理）
        mode = (request.mode or "chat-only").lower()
        workflow_mode = "auto-search" if mode != "chat-only" else "chat&plan"
        
        agent = get_intelligent_paper_search_agent()
        final_result = await agent.search_papers(
            query=request.message,
            mode=workflow_mode,
            max_results=max_results,
            force_search=False,  # auto-search模式会自动决定是否搜索
            year_from=year_from,
            year_to=year_to,
            sources=sources,
            allow_search=True,  # 允许工作流自主决定搜索执行
            history=history
        )
        
        # 获取最终响应
        ai_response = final_result.get('response', '')
        is_academic = final_result.get('is_academic_query', False)

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
        
        # 计算token信息和性能指标
        token_info = calculate_total_tokens(updated_history)
        total_time = time.time() - start_time
        workflow_time = time.time() - workflow_start
        
        # 添加性能监控信息
        analysis_result = final_result.get('analysis_result')
        has_analysis = bool(analysis_result)
        
        token_info.update({
            "fast_path": False,
            "total_response_time": total_time,
            "workflow_time": workflow_time,
            "llm_calls": 2 if mode != 'chat-only' and is_academic and has_analysis else 1
        })
        
        logger.info(f"📊 请求完成 - 总耗时: {total_time:.3f}s, 工作流耗时: {workflow_time:.3f}s, LLM调用: {token_info['llm_calls']}次")
        
        # 跟踪工作流性能
        request_type = "academic_search" if is_academic else "complex_chat"
        track_chat_performance(
            request_type=request_type,
            response_time=total_time,
            llm_calls=token_info['llm_calls'],
            is_fast_path=False,
            workflow_time=workflow_time,
            token_count=token_info.get('total_tokens', 0)
        )
        
        return ChatResponse(
            response=ai_response,
            history=response_history,
            is_academic_query=is_academic,
            search_results=final_result.get('search_results', []),
            analysis_result=final_result.get('analysis_result'),
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
    """优化后的搜索接口 - 优先使用预扩展关键词，避免重复LLM分析"""
    try:
        logger.info(f"🔍 搜索请求: {req.query}")
        
        # 📊 性能优化：优先使用预扩展的关键词，避免重复LLM调用
        if req.expanded_keywords and req.expanded_keywords.get('hierarchical_keywords'):
            logger.info("✅ 检测到预扩展关键词，直接执行搜索（跳过LLM分析）")
            
            try:
                from multi_source_engine import MultiSourceEngine
                search_engine = MultiSourceEngine()
                
                # 参考Paper-god-beta2: 简化查询构建 - 只用OR连接关键词
                hierarchical = req.expanded_keywords['hierarchical_keywords']
                
                # 收集所有术语
                all_terms = []
                exact_terms = hierarchical.get("exact_terms", {}).get("terms", [])
                core_synonyms = hierarchical.get("core_synonyms", {}).get("terms", [])
                related_terms = hierarchical.get("related_terms", {}).get("terms", [])
                
                # 优先级：精确术语 > 核心同义词 > 相关术语
                all_terms.extend(exact_terms[:2])  # 最多2个精确术语
                all_terms.extend(core_synonyms[:2])  # 最多2个核心同义词
                all_terms.extend(related_terms[:1])  # 最多1个相关术语
                
                # 去重并限制总数
                unique_terms = list(dict.fromkeys(all_terms))[:4]  # 最多4个术语
                
                # 参考Paper-god-beta2: 对包含空格的术语加引号，用OR连接
                if unique_terms:
                    quoted_terms = [
                        f'"{term}"' if ' ' in term else term
                        for term in unique_terms
                    ]
                    search_query = " OR ".join(quoted_terms)
                else:
                    search_query = req.query
                
                logger.info(f"🎯 构建优化查询: {search_query}")
                
                # 执行多源并行搜索
                papers = await search_engine.search_parallel_with_filters(
                    query=search_query,
                    max_results=req.max_results,
                    year_from=req.year_from,
                    year_to=req.year_to,
                    sources=req.sources
                )
                
                logger.info(f"📚 搜索完成，获得 {len(papers)} 篇论文")
                
                # 格式化结果 - 过滤缺少关键信息的论文
                formatted_papers = []
                for paper in papers:
                    # 只有标题不为空的论文才被包含
                    if paper.title and paper.title.strip():
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
                        },
                        "performance": {
                            "skip_llm_analysis": True,  # 标记跳过了LLM分析
                            "direct_search": True,
                            "token_saved": True  # 节省了token
                        }
                    }
                }
                
            except Exception as e:
                logger.error(f"❌ 直接搜索失败: {e}")
                # 出错时仍然记录避免了LLM调用的尝试
                logger.info("⚠️ 直接搜索失败，但已避免了不必要的LLM分析")
                
                # 返回错误而不是回退，避免意外的LLM消耗
                return {
                    "success": False,
                    "error": f"基于预扩展关键词的搜索失败: {str(e)}",
                    "data": {"papers": [], "total_found": 0},
                    "performance": {
                        "attempted_direct_search": True,
                        "avoided_llm_analysis": True
                    }
                }
        
        # 🔄 回退模式：没有预扩展关键词时拆分为「仅分析」→「条件搜索」两阶段
        logger.info("⚠️ 未提供预扩展关键词，先进行关键词扩展分析，再按需执行搜索")
        
        # 阶段1：仅做分析（不执行搜索）
        agent = get_intelligent_paper_search_agent()
        analysis_only = await agent.search_papers(
            query=req.query,
            mode="chat&plan",  # 只分析不自动搜索
            max_results=0,
            force_search=False,
            year_from=req.year_from,
            year_to=req.year_to,
            sources=req.sources,
            allow_search=False
        )
        is_academic = analysis_only.get('is_academic_query', False)
        analysis_result = analysis_only.get('analysis_result')
        
        # 若扩展失败（通常为LLM调用失败）或非学术，跳过搜索
        if not (is_academic and analysis_result):
            logger.warning("🔇 关键词扩展失败或非学术查询，已跳过文献搜索")
            return {
                "success": False,
                "error": analysis_only.get('error_message', '关键词扩展失败或非学术查询，已跳过搜索'),
                "data": {"papers": [], "total_found": 0},
                "query_info": {
                    "original_query": req.query,
                    "is_academic_query": is_academic,
                    "analysis_result": analysis_result
                },
                "performance": {
                    "llm_analysis": bool(analysis_result),
                    "token_consumed": bool(analysis_result),
                    "search_skipped": True
                }
            }
        
        # 阶段2：仅当扩展成功且为学术查询时，执行搜索
        search_result = await agent.search_papers(
            query=req.query,
            mode="auto-search",  # 自动执行搜索
            max_results=req.max_results,
            force_search=True,
            year_from=req.year_from,
            year_to=req.year_to,
            sources=req.sources,
            allow_search=True
        )
        
        if search_result.get('success') and search_result.get('search_results'):
            return {
                "success": True,
                "data": {
                    "papers": search_result['search_results'],
                    "total_found": len(search_result['search_results']),
                    "query_info": {
                        "original_query": req.query,
                        "is_academic_query": search_result.get('is_academic_query', True),
                        "analysis_result": search_result.get('analysis_result') or analysis_result
                    },
                    "performance": {
                        "intelligent_workflow": True,
                        "llm_analysis": True,
                        "token_consumed": True
                    }
                }
            }
        else:
            return {
                "success": False,
                "error": search_result.get('error_message', '智能工作流搜索失败'),
                "data": {"papers": [], "total_found": 0}
            }
            
    except Exception as e:
        logger.error(f"❌ 搜索接口失败: {e}")
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
            "data_sources": ["arxiv", "scholarly", "semantic_scholar"]
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

@app.get("/performance")
async def get_performance_stats():
    """获取性能统计信息"""
    try:
        monitor = get_performance_monitor()
        summary = monitor.get_performance_summary()
        return {
            "success": True,
            "data": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取性能统计失败: {str(e)}",
            "data": {}
        }

@app.post("/performance/reset")
async def reset_performance_stats():
    """重置性能统计"""
    try:
        monitor = get_performance_monitor()
        monitor.reset_stats()
        return {
            "success": True,
            "message": "性能统计已重置"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"重置性能统计失败: {str(e)}"
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
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        timeout_keep_alive=300,  # 保持连接5分钟
        timeout_graceful_shutdown=60,  # 优雅关闭超时60秒
    )