from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging
import json
import asyncio
import re
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
from prompt_utils import get_chat_conversation_prompt, get_multi_turn_conversation_prompt
from conversation_manager import get_conversation_manager

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
    # 新增：对话ID支持多轮对话
    conversation_id: Optional[str] = None
    # 搜索参数（可选）
    search_params: Optional[Dict[str, Any]] = None
    # 模式：'chat-only' | 'auto-search'
    mode: Optional[str] = None
    # 流式传输模式（统一使用流式传输，提升用户体验）
    stream: Optional[bool] = True

class ChatResponse(BaseModel):
    response: str
    history: List[ChatMessage]
    conversation_id: Optional[str] = None
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
async def execute_background_search(
    query: str,
    max_results: int = 40,
    analysis_result: Optional[Dict] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    sources: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """执行后台搜索任务 - 使用统一搜索逻辑"""
    try:
        logger.info(f"🔍 [后台搜索] 开始执行: {query[:40]}... | 数量: {max_results}")
        
        # 使用统一的多源搜索引擎
        from multi_source_engine import MultiSourceEngine
        search_engine = MultiSourceEngine()
        
        # 构建搜索查询 - 复用手动搜索的逻辑
        search_query = query
        if analysis_result and analysis_result.get('optimized_boolean_query'):
            search_query = analysis_result['optimized_boolean_query']
            logger.info(f"🎯 [后台搜索] 使用优化查询: {search_query}")
        
        # 执行多源并行搜索，传递auto-search模式
        search_results = await search_engine.search_parallel_with_filters(
            query=search_query,
            max_results=max_results,
            year_from=year_from,
            year_to=year_to,
            sources=sources,  # ['scholar_dock', 'arxiv']
            analysis=analysis_result,
            mode="auto-search"  # 指定auto-search模式，使用50:50配比
        )
        
        logger.info(f"📚 [后台搜索] 完成，获得 {len(search_results)} 篇论文")
        
        # 格式化结果
        formatted_papers = []
        for paper in search_results:
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
        
        # 安全关闭搜索引擎
        if search_engine:
            await search_engine.close()
        
        return formatted_papers
        
    except Exception as e:
        logger.error(f"❌ [后台搜索] 执行失败: {e}")
        raise e

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
        logger.info(f"🔍 [关键词扩展] 查询: {request.query[:40]}...")
        
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
        logger.error(f"❌ [关键词扩展] 失败: {e}")
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

def smart_chunk_text(text: str, max_chunk_size: int = 50) -> List[str]:
    """
    智能分割文本，避免破坏markdown格式
    优先在句子边界、段落边界分割，避免在markdown标记中间断开
    """
    if not text:
        return []
    
    chunks = []
    current_chunk = ""
    
    # 按段落分割（双换行）
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        # 如果段落为空，跳过
        if not paragraph.strip():
            continue
            
        # 如果当前段落很短，直接加入当前chunk
        if len(paragraph) <= max_chunk_size:
            if current_chunk and len(current_chunk + paragraph) > max_chunk_size:
                # 当前chunk已满，开始新chunk
                chunks.append(current_chunk)
                current_chunk = paragraph + '\n\n'
            else:
                current_chunk += paragraph + '\n\n'
        else:
            # 段落太长，需要进一步分割
            # 先保存当前chunk
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # 按句子分割长段落
            sentences = re.split(r'([。！？\.\!\?]\s*)', paragraph)
            temp_chunk = ""
            
            for i in range(0, len(sentences), 2):
                if i + 1 < len(sentences):
                    sentence = sentences[i] + sentences[i + 1]
                else:
                    sentence = sentences[i]
                
                if not sentence.strip():
                    continue
                    
                if len(temp_chunk + sentence) <= max_chunk_size:
                    temp_chunk += sentence
                else:
                    if temp_chunk:
                        chunks.append(temp_chunk)
                    temp_chunk = sentence
            
            if temp_chunk:
                current_chunk = temp_chunk + '\n\n'
    
    # 添加最后的chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return [chunk for chunk in chunks if chunk.strip()]

async def generate_stream_response(
    message: str,
    history: List[Dict[str, str]],
    search_params: Dict[str, Any],
    mode: str
):
    """生成流式响应"""
    try:
        # 🚀 快速意图预筛选 - 对明显闲聊使用LLM生成自然回复
        quick_intent = quick_intent_filter(message)
        if quick_intent == "闲聊":
            logger.info("🚀 [闲聊模式] 快速预筛选 → LLM生成回复")
            
            # 使用LLM流式生成自然的闲聊回复
            llm_client = await get_universal_llm()
            prompt = get_chat_conversation_prompt(message)
            
            messages = [{"role": "user", "content": prompt}]
            
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'data': {}})}\n\n"
            
            try:
                # 流式生成响应
                async for chunk in llm_client.chat_completion_stream(messages):
                    if chunk:
                        yield f"data: {json.dumps({'type': 'content', 'data': {'content': chunk}})}\n\n"
                        # 移除人工延迟以提升响应速度
                
                # 发送完成事件
                yield f"data: {json.dumps({'type': 'done', 'data': {'is_academic_query': False}})}\n\n"
                
            except Exception as e:
                logger.error(f"❌ [闲聊模式] LLM调用失败: {e}")
                fallback_response = "你好！我是Veritex智能助手，专门帮助您查找和分析学术文献。有什么学术问题我可以帮您解答吗？"
                yield f"data: {json.dumps({'type': 'content', 'data': {'content': fallback_response}})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'data': {'is_academic_query': False, 'error': str(e)}})}\n\n"
                
        else:
            # 复杂流程：学术查询处理
            logger.info("🧠 [学术模式] 启动智能工作流")
            
            yield f"data: {json.dumps({'type': 'start', 'data': {}})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'data': {'message': '正在分析您的学术查询...'}})}\n\n"
            
            # 提取搜索参数
            max_results = search_params.get('max_results', 20)
            year_from = search_params.get('year_from')
            year_to = search_params.get('year_to')
            sources = search_params.get('sources')
            
            # 调用智能工作流
            workflow_mode = "auto-search" if mode != "chat-only" else "chat&plan"
            
            agent = get_intelligent_paper_search_agent()
            final_result = await agent.search_papers(
                query=message,
                mode=workflow_mode,
                max_results=max_results,
                force_search=False,
                year_from=year_from,
                year_to=year_to,
                sources=sources,
                allow_search=True,
                history=history
            )
            
            # 获取完整响应
            ai_response = final_result.get('response', '')
            is_academic = final_result.get('is_academic_query', False)
            background_search_required = final_result.get('background_search_required', False)
            
            # 分段发送响应内容
            if ai_response:
                # 智能分割，避免破坏markdown格式
                chunks = smart_chunk_text(ai_response)
                
                for chunk in chunks:
                    yield f"data: {json.dumps({'type': 'content', 'data': {'content': chunk}})}\n\n"
            
            # 🎯 检查是否需要后台搜索（auto-search模式）
            if background_search_required and workflow_mode == "auto-search":
                logger.info("🚀 [后台搜索] 启动后台搜索任务")
                
                # 发送分析完成事件，提示用户可以查看分析结果
                yield f"data: {json.dumps({'type': 'analysis_done', 'data': {'is_academic_query': is_academic, 'analysis_result': final_result.get('analysis_result'), 'background_search_pending': True}})}\n\n"
                
                # 启动后台搜索任务
                try:
                    yield f"data: {json.dumps({'type': 'status', 'data': {'message': '正在后台搜索文献，请稍候...'}})}\n\n"
                    
                    # 执行后台搜索，使用统一的搜索逻辑，但指定auto-search模式
                    search_result = await execute_background_search(
                        query=message,
                        max_results=max_results,
                        analysis_result=final_result.get('analysis_result'),
                        year_from=year_from,
                        year_to=year_to,
                        sources=['scholar_dock', 'arxiv']  # 明确指定数据源
                    )
                    
                    # 发送搜索完成事件
                    yield f"data: {json.dumps({'type': 'search_done', 'data': {'search_results': search_result, 'show_report_button': True}})}\n\n"
                    
                except Exception as search_error:
                    logger.error(f"❌ [后台搜索] 搜索失败: {search_error}")
                    yield f"data: {json.dumps({'type': 'search_error', 'data': {'error': str(search_error)}})}\n\n"
            else:
                # 发送完成事件和其他数据（非auto-search模式或无需搜索）
                yield f"data: {json.dumps({'type': 'done', 'data': {'is_academic_query': is_academic, 'search_results': final_result.get('search_results', []), 'analysis_result': final_result.get('analysis_result')}})}\n\n"
            
    except Exception as e:
        logger.error(f"❌ [系统] 单轮流式响应失败: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e)}})}\n\n"

async def generate_stream_response_with_conversation(
    message: str,
    history: List[Dict[str, str]],
    search_params: Dict[str, Any],
    mode: str,
    conversation_id: str
):
    """生成流式响应并保存到对话管理器"""
    conversation_manager = get_conversation_manager()
    ai_response_parts = []  # 收集AI回复内容
    
    try:
        # 🔧 智能多轮对话：保持上下文同时进行意图分析
        is_multi_turn = False
        if conversation_id:
            conversation = await conversation_manager.get_conversation(conversation_id)
            if conversation and len(conversation.messages) > 1:
                is_multi_turn = True
                logger.info(f"🔄 [多轮对话] ID: {conversation_id[:8]}... 保持上下文")
        
        # 🚀 始终进行快速意图预筛选
        quick_intent = quick_intent_filter(message)
        
        if quick_intent == "闲聊":
            # 闲聊处理：支持多轮对话上下文
            logger.info(f"🚀 [闲聊模式] {'多轮' if is_multi_turn else '单轮'}对话")
            
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'data': {}})}\n\n"
            
            try:
                llm_client = await get_universal_llm()
                
                if is_multi_turn:
                    # 多轮对话：使用上下文
                    system_prompt = get_multi_turn_conversation_prompt(user_query=message)
                    async for chunk in llm_client.chat_with_history_stream(
                        message=message,
                        conversation_id=conversation_id or "default", 
                        system_prompt=system_prompt
                    ):
                        if chunk:
                            ai_response_parts.append(chunk)
                            yield f"data: {json.dumps({'type': 'content', 'data': {'content': chunk}})}\n\n"
                else:
                    # 单轮对话：使用闲聊prompt
                    prompt = get_chat_conversation_prompt(message)
                    messages = [{"role": "user", "content": prompt}]
                    async for chunk in llm_client.chat_completion_stream(messages):
                        if chunk:
                            ai_response_parts.append(chunk)
                            yield f"data: {json.dumps({'type': 'content', 'data': {'content': chunk}})}\n\n"
                
                # 保存完整的AI回复
                full_response = "".join(ai_response_parts)
                if full_response:
                    await conversation_manager.add_message_to_conversation(
                        conversation_id, 
                        "assistant", 
                        full_response
                    )
                
                # 发送完成事件
                yield f"data: {json.dumps({'type': 'done', 'data': {'is_academic_query': False, 'conversation_id': conversation_id, 'multi_turn_mode': is_multi_turn}})}\n\n"
                return
                
            except Exception as e:
                logger.error(f"❌ [闲聊模式] LLM流式调用失败: {e}")
                fallback_response = "你好！我是Veritex智能助手，专门帮助您查找和分析学术文献。有什么学术问题我可以帮您解答吗？"
                
                # 保存降级回复
                await conversation_manager.add_message_to_conversation(
                    conversation_id, 
                    "assistant", 
                    fallback_response
                )
                
                yield f"data: {json.dumps({'type': 'content', 'data': {'content': fallback_response}})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'data': {'is_academic_query': False, 'conversation_id': conversation_id, 'error': str(e)}})}\n\n"
                return
                
        else:
            # 学术查询处理：支持多轮对话上下文
            logger.info(f"🧠 [学术模式] {'多轮' if is_multi_turn else '单轮'}对话 → 智能工作流")
            
            yield f"data: {json.dumps({'type': 'start', 'data': {}})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'data': {'message': '正在分析您的学术查询...'}})}\n\n"
            
            # 提取搜索参数
            max_results = search_params.get('max_results', 20)
            year_from = search_params.get('year_from')
            year_to = search_params.get('year_to')
            sources = search_params.get('sources')
            
            # 调用智能工作流，传递conversation_id支持多轮对话
            workflow_mode = "auto-search" if mode != "chat-only" else "chat&plan"
            
            agent = get_intelligent_paper_search_agent()
            final_result = await agent.search_papers(
                query=message,
                mode=workflow_mode,
                max_results=max_results,
                force_search=False,
                year_from=year_from,
                year_to=year_to,
                sources=sources,
                allow_search=True,
                history=history
            )
            
            # 获取完整响应
            ai_response = final_result.get('response', '')
            is_academic = final_result.get('is_academic_query', False)
            
            # 分段发送响应内容
            if ai_response:
                # 保存AI回复
                await conversation_manager.add_message_to_conversation(
                    conversation_id, 
                    "assistant", 
                    ai_response
                )
                
                # 智能分割，避免破坏markdown格式
                chunks = smart_chunk_text(ai_response)
                
                for chunk in chunks:
                    yield f"data: {json.dumps({'type': 'content', 'data': {'content': chunk}})}\n\n"
            
            # 发送完成事件和其他数据
            yield f"data: {json.dumps({'type': 'done', 'data': {'is_academic_query': is_academic, 'conversation_id': conversation_id, 'search_results': final_result.get('search_results', []), 'analysis_result': final_result.get('analysis_result')}})}\n\n"
            
    except Exception as e:
        logger.error(f"❌ [系统] 多轮流式响应失败: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e), 'conversation_id': conversation_id}})}\n\n"

@app.post("/chat")
async def chat(request: ChatRequest):
    """统一聊天接口 - 支持多轮对话和流式响应"""
    import time
    start_time = time.time()
    
    # 获取对话管理器
    conversation_manager = get_conversation_manager()
    
    # 处理对话ID
    conversation_id = request.conversation_id
    conversation = None
    
    if conversation_id:
        # 获取现有对话
        conversation = await conversation_manager.get_conversation(conversation_id)
        if not conversation:
            logger.warning(f"对话不存在: {conversation_id}")
            conversation_id = None
    
    if not conversation:
        # 创建新对话
        conversation = await conversation_manager.create_conversation()
        conversation_id = conversation.conversation_id
        logger.info(f"创建新对话: {conversation_id}")
    
    # 将用户消息添加到对话历史
    await conversation_manager.add_message_to_conversation(
        conversation_id, 
        "user", 
        request.message
    )
    
    # 获取完整的对话历史（优先使用管理器中的历史）
    conversation = await conversation_manager.get_conversation(conversation_id)
    if conversation and conversation.messages:
        # 使用对话管理器中的历史记录
        history = [{"role": msg.role, "content": msg.content} for msg in conversation.messages[:-1]]  # 排除刚添加的用户消息
    else:
        # 降级使用请求中的历史记录
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
    
    logger.info(f"📨 [请求] ID: {conversation_id[:8] if conversation_id else 'new'}... | 消息: {request.message[:30]}... | 流式: {request.stream}")
    
    # 统一使用流式传输，提供最佳用户体验
    search_params = request.search_params or {}
    mode = (request.mode or "chat-only").lower()
    
    return StreamingResponse(
        generate_stream_response_with_conversation(
            request.message, history, search_params, mode, conversation_id
        ),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

# === 对话管理API接口 ===

@app.get("/conversations")
async def list_conversations(
    limit: int = 20, 
    offset: int = 0,
    archived: Optional[bool] = None,
    search: Optional[str] = None
):
    """获取对话列表"""
    try:
        conversation_manager = get_conversation_manager()
        conversations = await conversation_manager.list_conversations(
            limit=limit,
            offset=offset,
            archived=archived,
            search_query=search
        )
        return {
            "success": True,
            "conversations": [conv.dict() for conv in conversations],
            "total": len(conversations)
        }
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取对话列表失败: {str(e)}")

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取特定对话详情"""
    try:
        conversation_manager = get_conversation_manager()
        conversation = await conversation_manager.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        return {
            "success": True,
            "conversation": conversation.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取对话详情失败: {str(e)}")

@app.post("/conversations")
async def create_conversation(title: Optional[str] = None):
    """创建新对话"""
    try:
        conversation_manager = get_conversation_manager()
        from models.conversation import ConversationCreateRequest
        
        request = ConversationCreateRequest(title=title) if title else None
        conversation = await conversation_manager.create_conversation(request)
        
        return {
            "success": True,
            "conversation_id": conversation.conversation_id,
            "conversation": conversation.dict()
        }
    except Exception as e:
        logger.error(f"创建对话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建对话失败: {str(e)}")

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    try:
        conversation_manager = get_conversation_manager()
        success = await conversation_manager.delete_conversation(conversation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        return {
            "success": True,
            "message": "对话删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除对话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除对话失败: {str(e)}")

@app.put("/conversations/{conversation_id}/archive")
async def archive_conversation(conversation_id: str):
    """归档对话"""
    try:
        conversation_manager = get_conversation_manager()
        success = await conversation_manager.archive_conversation(conversation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="对话不存在")
        
        return {
            "success": True,
            "message": "对话归档成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"归档对话失败: {e}")
        raise HTTPException(status_code=500, detail=f"归档对话失败: {str(e)}")

@app.get("/conversations/stats")
async def get_conversation_stats():
    """获取对话统计信息"""
    try:
        conversation_manager = get_conversation_manager()
        stats = await conversation_manager.get_conversation_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"获取对话统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取对话统计失败: {str(e)}")

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
        logger.info(f"🔍 [搜索] 查询: {req.query[:40]}... | 数量: {req.max_results}")
        
        # 📊 性能优化：优先使用预扩展的关键词，避免重复LLM调用
        if req.expanded_keywords and req.expanded_keywords.get('hierarchical_keywords'):
            logger.info("✅ [搜索] 使用预扩展关键词，跳过LLM分析")
            
            try:
                # 🚀 优先尝试优化搜索，失败时降级到原始搜索
                search_results = None
                search_engine = None
                
                # 使用统一的多源搜索引擎
                from multi_source_engine import MultiSourceEngine
                search_engine = MultiSourceEngine()
                
                try:
                    # 使用LLM返回的优化布尔查询和搜索策略
                    hierarchical = req.expanded_keywords['hierarchical_keywords']
                    
                    # 优先使用LLM提供的优化布尔查询
                    if req.expanded_keywords.get('optimized_boolean_query'):
                        search_query = req.expanded_keywords['optimized_boolean_query']
                        search_strategy = req.expanded_keywords.get('search_strategy', 'balanced')
                        logger.info(f"🎯 使用LLM优化布尔查询: {search_query}")
                        logger.info(f"📈 搜索策略: {search_strategy}")
                    else:
                        # 🔄 备用方案：权重驱动的查询构建（与工作流保持一致）
                        logger.info("⚠️ LLM未返回布尔查询，使用权重驱动构建")
                        
                        # 使用paper_search_workflow中的智能构建逻辑
                        from langchain_workflows.paper_search_workflow import IntelligentPaperSearchAgent
                        temp_agent = IntelligentPaperSearchAgent()
                        
                        # 构建分析数据结构
                        analysis_data = {
                            "hierarchical_keywords": hierarchical,
                            "search_strategy": req.expanded_keywords.get('search_strategy', 'balanced')
                        }
                        
                        search_query = temp_agent._build_search_query(req.query, analysis_data)
                        logger.info(f"🔧 权重驱动查询构建: {search_query}")
                    
                    logger.info(f"🎯 构建优化查询: {search_query}")
                    
                    # 执行多源并行搜索（传递analysis参数用于统一布尔查询）
                    search_results = await search_engine.search_parallel_with_filters(
                        query=search_query,
                        max_results=req.max_results,
                        year_from=req.year_from,
                        year_to=req.year_to,
                        sources=req.sources,
                        analysis=analysis_data
                    )
                except Exception as search_error:
                    logger.error(f"❌ 搜索执行失败: {search_error}")
                    search_results = []
                
                logger.info(f"📚 搜索完成，获得 {len(search_results)} 篇论文")
                
                # 格式化结果 - 过滤缺少关键信息的论文
                formatted_papers = []
                for paper in search_results:
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
                
                # 安全关闭搜索引擎
                if search_engine:
                    await search_engine.close()
                
                return {
                    "success": True,
                    "data": {
                        "papers": formatted_papers,
                        "total_found": len(formatted_papers),
                        "query_info": {
                            "original_query": req.query,
                            "search_query": locals().get('search_query', req.query),
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
            "data_sources": ["arxiv", "scholar_dock", "semantic_scholar"]
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
    """获取增强的性能统计信息 - 整合AI_SCI_DOG优化"""
    try:
        stats = {
            "timestamp": datetime.now().isoformat(),
            "success": True
        }
        
        # 原有性能监控器统计
        try:
            monitor = get_performance_monitor()
            summary = monitor.get_performance_summary()
            stats["original_monitor"] = summary
        except Exception as e:
            logger.warning(f"获取原始性能监控失败: {e}")
        
        
        # 智能重试处理器统计
        try:
            from smart_retry_handler import get_retry_handler, get_fallback_handler
            retry_handler = get_retry_handler()
            fallback_handler = get_fallback_handler()
            
            stats["retry_handler"] = retry_handler.get_retry_stats()
            stats["fallback_handler"] = fallback_handler.get_health_status()
        except Exception as e:
            logger.warning(f"获取重试处理器统计失败: {e}")
        
        # 系统资源统计
        try:
            import psutil
            stats["system_resources"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent,
                "network_connections": len(psutil.net_connections())
            }
        except Exception as e:
            logger.warning(f"获取系统资源统计失败: {e}")
            
        return stats
        
    except Exception as e:
        return {
            "success": False,
            "error": f"获取性能统计失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
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

@app.post("/search_papers/batch")
async def batch_search_papers(request: Dict[str, Any]):
    """批量搜索接口 - 参考AI_SCI_DOG优化"""
    try:
        queries = request.get("queries", [])
        if not queries:
            raise ValueError("查询列表不能为空")
        
        options = request.get("options", {})
        max_concurrent = options.get("max_concurrent", 3)
        limit_per_query = options.get("limit", 10)
        
        logger.info(f"🔄 开始批量搜索 - 查询数: {len(queries)}, 并发数: {max_concurrent}")
        
        # 使用统一的多源搜索引擎执行批量搜索  
        try:
            from multi_source_engine import MultiSourceEngine
            engine = MultiSourceEngine()
            
            # 分批处理查询以控制并发
            batch_results = []
            for i in range(0, len(queries), max_concurrent):
                batch = queries[i:i + max_concurrent]
                
                # 并发执行批量搜索
                batch_tasks = []
                for query in batch:
                    task = asyncio.create_task(
                        engine.search_parallel(
                            query=query,
                            max_results=limit_per_query
                        )
                    )
                    batch_tasks.append(task)
                
                batch_papers = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for j, papers in enumerate(batch_papers):
                    if isinstance(papers, Exception):
                        batch_results.append({
                            "papers": [],
                            "error": str(papers),
                            "response_time": 0.0,
                            "source": "multi_source_engine"
                        })
                    else:
                        batch_results.append({
                            "papers": papers,
                            "error": None,
                            "response_time": 2.0,  # 估算值
                            "source": "multi_source_engine"
                        })
                
                # 批次间延迟
                if i + max_concurrent < len(queries):
                    await asyncio.sleep(1.0)
                    
            await engine.close()
            
            # 转换结果格式
            formatted_results = []
            for i, result in enumerate(batch_results):
                formatted_result = {
                    "query": queries[i],
                    "success": result["error"] is None,
                    "paper_count": len(result["papers"]) if result["papers"] else 0,
                    "response_time": result["response_time"],
                    "source": result["source"]
                }
                
                if result["error"]:
                    formatted_result["error"] = result["error"]
                else:
                    # 格式化论文数据
                    papers = []
                    for paper in result["papers"]:
                        papers.append({
                            "title": paper.title,
                            "authors": paper.authors,
                            "abstract": paper.abstract,
                            "year": paper.year,
                            "journal": paper.journal,
                            "url": paper.url,
                            "citations": paper.citations,
                            "source": paper.source
                        })
                    formatted_result["papers"] = papers
                
                formatted_results.append(formatted_result)
            
            # 统计信息
            successful_searches = sum(1 for r in formatted_results if r["success"])
            total_papers = sum(r["paper_count"] for r in formatted_results)
            
            return {
                "success": True,
                "results": formatted_results,
                "summary": {
                    "total_queries": len(queries),
                    "successful_searches": successful_searches,
                    "failed_searches": len(queries) - successful_searches,
                    "total_papers_found": total_papers,
                    "average_papers_per_query": total_papers / len(queries) if queries else 0
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 批量搜索失败: {e}")
            return {
                "success": False,
                "error": f"批量搜索执行失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ 批量搜索请求处理失败: {e}")
        return {
            "success": False, 
            "error": f"请求处理失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
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