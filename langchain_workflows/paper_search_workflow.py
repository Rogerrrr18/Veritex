"""
智能学术论文搜索工作流 - 集成Paper-god-beta2多源搜索引擎
基于LangGraph v2架构，融合专业关键词扩展与现有搜索系统
"""
import asyncio
import json
import uuid
import re
import time
import hashlib
from typing import Dict, Any, List, Optional
 

from langchain_core.messages import HumanMessage, SystemMessage
# AIMessage将在每个需要的函数内部局部导入以避免作用域冲突
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# 导入项目模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# prompt_manager已删除，使用简化的prompt_utils
from llm_intent_classifier import get_intent_classifier

from llm_interface import get_llm_for_langgraph
from langchain_workflows.state_schemas import PaperSearchState, create_initial_state

class IntelligentPaperSearchAgent:
    """
    智能学术搜索Agent - 集成现有多源搜索引擎
    工作流：START → 意图分析 → 关键词扩展 → 搜索执行 → 结果处理 → END
    """
    
    def __init__(self, enable_memory: bool = True):
        # 简单内存缓存 - 避免重复的LLM调用和搜索
        self._keyword_expansion_cache = {}  # 关键词扩展缓存
        self._search_results_cache = {}     # 搜索结果缓存
        self._cache_ttl = 1800  # 缓存30分钟
        self._max_cache_size = 100  # 最大缓存条目数
        self.enable_memory = enable_memory
        # 使用统一LLM接口
        self.llm = get_llm_for_langgraph()
        
        # 使用优化的LLM意图分类器
        self.intent_classifier = get_intent_classifier()
        print("✅ 使用优化的LLM意图分类器（已移除embedding步骤）")
        
        self.checkpointer = MemorySaver() if enable_memory else None
        self.graph = self._build_graph()
        
        # 延迟加载搜索引擎（避免循环依赖）
        self._search_engine = None
        
        print("✅ 智能缓存系统已启用 - 30分钟TTL，最大100条目")
    
    async def _get_search_engine(self):
        """获取搜索引擎实例（延迟加载）- 避免循环依赖"""
        if self._search_engine is None:
            try:
                # 使用真实的MultiSourceEngine，删除模拟引擎依赖
                from multi_source_engine import MultiSourceEngine
                self._search_engine = MultiSourceEngine()
                print("✅ 多源搜索引擎实例化成功")
            except Exception as e:
                print(f"❌ 搜索引擎实例化失败: {e}")
                raise Exception(f"无法初始化搜索引擎: {e}，请检查依赖包安装")
        return self._search_engine
    
    
    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(PaperSearchState)
        
        # 添加核心节点
        workflow.add_node("intent_analysis", self.intent_analysis_node)
        
        # 三个意图专门处理节点
        workflow.add_node("chat_conversation", self.chat_conversation_node)
        workflow.add_node("literature_search", self.literature_search_node) 
        workflow.add_node("academic_discussion", self.academic_discussion_node)
        
        # 搜索和结果处理节点
        workflow.add_node("search_execution", self.search_execution_node)
        workflow.add_node("result_formatting", self.result_formatting_node)
        
        # 定义流程路径
        workflow.add_edge(START, "intent_analysis")
        
        # 根据意图分析结果分发到对应节点
        workflow.add_conditional_edges(
            "intent_analysis",
            self.route_by_intent,
            {
                "chat_conversation": "chat_conversation",
                "literature_search": "literature_search", 
                "academic_discussion": "academic_discussion"
            }
        )
        
        # 闲聊对话直接结束
        workflow.add_edge("chat_conversation", END)
        
        # 文献搜索和学术讨论的后续路径
        workflow.add_conditional_edges(
            "literature_search",
            self.route_after_literature_search,
            {
                "search": "search_execution",  # chat&plan模式下可能需要的路径（保留兼容性）
                "completed": END,  # auto-search模式完成后直接结束
                "wait_decision": END  # chat&plan模式等待用户决策
            }
        )
        
        workflow.add_conditional_edges(
            "academic_discussion", 
            self.should_execute_search_after_discussion,
            {
                "search": "search_execution",
                "end": END
            }
        )
        
        workflow.add_edge("search_execution", "result_formatting")
        workflow.add_edge("result_formatting", END)
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def intent_analysis_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """意图分析节点 - Embedding + LLM精排版本"""
        try:
            query = state.get("query", "")
            user_message = state.get("messages", [])[-1].content if state.get("messages") else query
            
            print(f"🤖 开始智能分析用户请求: {user_message}")
            
            # 使用Embedding + LLM精排分类器
            intent_result = await self.intent_classifier.classify_intent(user_message)
            print(f"🔧 意图分类结果: {intent_result.intent} (置信度: {intent_result.confidence:.3f})")
            
            # 将意图结果保存到state中供后续节点使用
            return {
                "current_step": "intent_analyzed",
                "is_completed": False,
                "intent_result": {
                    "intent": intent_result.intent,
                    "confidence": float(intent_result.confidence),  # 转换为Python float
                    "method": intent_result.method,
                    "reasoning": intent_result.reasoning or ""
                },
                "analysis_result": None,
                "is_academic_query": intent_result.intent in ["查文献", "学术探讨"],
                "need_search_strategy": intent_result.intent == "查文献"
            }
                
        except Exception as e:
            error_msg = f"意图分析失败: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"🔧 异常详情: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"🔧 堆栈跟踪: {traceback.format_exc()}")
            # 局部导入AIMessage
            from langchain_core.messages import AIMessage
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "is_completed": False,
                "messages": [AIMessage(content=f"系统错误：{error_msg}")]
            }
    
    def route_by_intent(self, state: PaperSearchState) -> str:
        """根据意图分析结果路由到对应的处理节点"""
        intent_result = state.get("intent_result")
        
        if not intent_result:
            print("⚠️ 未找到意图分析结果，默认进入对话模式")
            return "chat_conversation"
        
        intent = intent_result.get("intent", "闲聊")
        print(f"🎯 路由决策：意图 '{intent}' → 对应处理节点")
        
        if intent == "闲聊":
            return "chat_conversation"
        elif intent == "查文献":
            return "literature_search"
        elif intent == "学术探讨":
            return "academic_discussion"
        else:
            print(f"⚠️ 未知意图 '{intent}'，默认进入对话模式")
            return "chat_conversation"
    
    async def chat_conversation_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """优化的闲聊对话处理节点 - 减少LLM调用"""
        try:
            user_message = state.get("user_message", "")
            print(f"💬 闲聊对话处理: {user_message}")
            
            # 🚀 优化策略：对常见闲聊使用预定义回复，减少LLM调用
            quick_response = self._get_quick_chat_response(user_message)
            if quick_response:
                print(f"⚡ 使用快速闲聊回复，跳过LLM调用")
                from langchain_core.messages import AIMessage
                return {
                    "current_step": "completed",
                    "is_completed": True,
                    "analysis_result": None,
                    "is_academic_query": False,
                    "need_search_strategy": False,
                    "messages": [AIMessage(content=quick_response)],
                    "fast_chat": True  # 标记为快速聊天
                }
            
            # 对复杂闲聊才使用LLM
            print(f"🤖 复杂闲聊，使用LLM生成回复")
            from prompt_utils import get_chat_conversation_prompt
            prompt = get_chat_conversation_prompt(user_message)
            
            # 调用LLM生成对话回复（设置较短超时）
            response = await self.llm.simple_chat(prompt=prompt, timeout=45.0)
            
            # 🧹 应用统一的消息清洗处理
            cleaned_response = self._final_clean_response(response)
            print(f"📝 闲聊消息清洗完成，清洗前: {len(response)} 字符，清洗后: {len(cleaned_response)} 字符")
            
            # 明确导入AIMessage避免作用域问题
            from langchain_core.messages import AIMessage
            
            return {
                "current_step": "completed",
                "is_completed": True,
                "analysis_result": None,
                "is_academic_query": False,
                "need_search_strategy": False,
                "messages": [AIMessage(content=cleaned_response)],  # 使用清洗后的响应
                "fast_chat": False  # 标记为LLM聊天
            }
            
        except Exception as e:
            error_msg = f"对话处理失败: {str(e)}"
            print(f"❌ {error_msg}")
            from langchain_core.messages import AIMessage
            return {
                "current_step": "failed",
                "is_completed": False,
                "error_message": error_msg,
                "messages": [AIMessage(content="抱歉，我现在无法正常对话，请稍后重试。")]
            }
    
    def _get_quick_chat_response(self, user_message: str) -> Optional[str]:
        """快速闲聊回复生成器 - 避免LLM调用"""
        message_lower = user_message.lower().strip()
        
        # 预定义的快速回复映射
        quick_responses = {
            "你好": "你好！我是Paper God，一个学术文献搜索助手。有什么学术问题可以帮您解答吗？",
            "hello": "Hello! I'm Paper God, an academic literature search assistant. How can I help you with academic research?",
            "hi": "Hi there! I'm here to help you find academic papers and research. What are you looking for?",
            "谢谢": "不客气！如果您需要查找学术文献或有其他问题，随时可以告诉我。",
            "thank": "You're welcome! Feel free to ask if you need help with academic research.",
            "感谢": "不用谢！我随时准备为您的学术研究提供帮助。",
            "再见": "再见！下次有学术问题欢迎随时找我。",
            "bye": "Goodbye! Feel free to come back anytime for academic research help.",
            "拜拜": "拜拜！期待下次为您提供学术搜索服务。",
            "天气": "我是专注于学术文献搜索的AI助手，不太了解天气情况。不过我可以帮您查找相关的学术论文！",
            "怎么用": "我是学术搜索助手，您可以直接告诉我您要查找的研究主题，我会帮您搜索相关的学术论文。",
            "你是谁": "我是Paper God，专门帮助研究者查找和分析学术文献的AI助手。您有什么学术问题需要帮助吗？",
            "什么功能": "我的主要功能是帮您搜索学术论文、扩展关键词、分析研究趋势。您可以直接告诉我研究主题，我来帮您找相关文献！"
        }
        
        # 检查是否匹配预定义回复
        for keyword, response in quick_responses.items():
            if keyword in message_lower:
                return response
        
        # 检查是否是简单的肯定/否定回复
        if message_lower in ["是", "好", "嗯", "ok", "好的", "行", "可以"]:
            return "好的！有什么学术问题我可以帮您解答吗？"
        
        if message_lower in ["不", "没有", "算了", "不用", "no"]:
            return "好的，如果之后有学术研究需要帮助，随时可以找我！"
        
        return None  # 无法快速处理，需要LLM
    
    def _get_cache_key(self, query: str, mode: str = None, max_results: int = None) -> str:
        """生成缓存键"""
        try:
            # 标准化查询
            normalized_query = query.strip().lower()
            # 包含关键参数生成唯一键
            key_data = f"{normalized_query}|{mode or 'default'}|{max_results or 10}"
            return hashlib.md5(key_data.encode('utf-8')).hexdigest()[:16]
        except:
            return hashlib.md5(query.encode('utf-8', errors='ignore')).hexdigest()[:16]
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """检查缓存是否有效"""
        if not cache_entry or 'timestamp' not in cache_entry:
            return False
        return (time.time() - cache_entry['timestamp']) < self._cache_ttl
    
    def _clean_expired_cache(self, cache_dict: Dict):
        """清理过期缓存"""
        try:
            current_time = time.time()
            expired_keys = [
                key for key, entry in cache_dict.items()
                if not entry or 'timestamp' not in entry or 
                (current_time - entry['timestamp']) >= self._cache_ttl
            ]
            for key in expired_keys:
                cache_dict.pop(key, None)
            
            # 如果缓存过大，删除最旧的条目
            if len(cache_dict) > self._max_cache_size:
                sorted_items = sorted(cache_dict.items(), key=lambda x: x[1].get('timestamp', 0))
                items_to_remove = len(cache_dict) - self._max_cache_size
                for i in range(items_to_remove):
                    cache_dict.pop(sorted_items[i][0], None)
                    
        except Exception as e:
            print(f"⚠️ 缓存清理失败: {e}")
    
    async def literature_search_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """文献搜索处理节点 - 根据模式选择不同的处理策略（支持缓存）"""
        mode = state.get("mode", "auto-search")
        user_message = state.get("user_message", "")
        print(f"📚 文献搜索处理: {user_message} (模式: {mode})")
        
        if mode == "auto-search":
            # 自动搜索模式：整合分析+搜索执行
            return await self._integrated_auto_search(state)
        else:
            # chat&plan模式：仅做分析，等待用户决策
            return await self._analysis_only_search(state)
            
    async def _analysis_only_search(self, state: PaperSearchState) -> Dict[str, Any]:
        """仅分析模式 - 用于chat&plan模式（支持关键词扩展缓存）"""
        try:
            user_message = state.get("user_message", "")
            mode = state.get("mode", "chat&plan")
            
            # 🚀 检查关键词扩展缓存
            cache_key = self._get_cache_key(user_message, mode, 0)
            
            self._clean_expired_cache(self._keyword_expansion_cache)
            
            if cache_key in self._keyword_expansion_cache:
                cached_entry = self._keyword_expansion_cache[cache_key]
                if self._is_cache_valid(cached_entry):
                    print(f"⚡ 命中关键词扩展缓存，跳过LLM分析")
                    
                    from langchain_core.messages import AIMessage
                    cached_response = cached_entry['response']
                    cached_analysis = cached_entry['analysis']
                    
                    return {
                        "current_step": "search_ready",
                        "is_completed": False,
                        "analysis_result": cached_analysis,
                        "is_academic_query": True,
                        "need_search_strategy": True,
                        "mode": mode,
                        "messages": [AIMessage(content=cached_response)],
                        "should_search": False,
                        "cache_hit": True  # 标记缓存命中
                    }
            
            # 使用完整的文献搜索prompt（支持模式化说明）
            from prompt_utils import get_literature_search_prompt
            prompt = get_literature_search_prompt(user_message, mode=mode)
            
            # 调用LLM进行关键词扩展和搜索分析
            response = await self.llm.simple_chat(prompt=prompt, timeout=60.0)
            
            # 验证LLM响应
            if not response or len(response.strip()) < 20:
                print(f"⚠️ LLM响应过短或为空，长度: {len(response) if response else 0}")
                print(f"⚠️ 使用回退机制处理查询: {user_message}")
                
                # 提供基本的关键词提取作为回退
                fallback_analysis = {
                    "original_query": user_message,
                    "core_concepts": [user_message.strip()],
                    "domain": "学术研究",
                    "hierarchical_keywords": {
                        "exact_terms": {"terms": [user_message.strip()], "weight": 1.0}
                    }
                }
                
                from langchain_core.messages import AIMessage
                return {
                    "current_step": "search_ready",
                    "is_completed": False,
                    "analysis_result": fallback_analysis,
                    "is_academic_query": True,
                    "need_search_strategy": True,
                    "mode": mode,
                    "messages": [AIMessage(content=f"已为您分析查询：{user_message}，请选择是否执行搜索。")],
                    "should_search": False,  # chat&plan模式不自动搜索
                    "is_fallback": True
                }
            
            # 解析LLM响应中的JSON部分
            keywords_analysis = self._extract_json_analysis(response)
            
            # 🚀 缓存关键词扩展结果
            if keywords_analysis:
                try:
                    cache_entry = {
                        'timestamp': time.time(),
                        'response': response,
                        'analysis': keywords_analysis,
                        'query': user_message,
                        'mode': mode
                    }
                    self._keyword_expansion_cache[cache_key] = cache_entry
                    print(f"💾 已缓存关键词扩展结果")
                except Exception as e:
                    print(f"⚠️ 缓存关键词扩展失败: {e}")
            
            from langchain_core.messages import AIMessage
            return {
                "current_step": "search_ready",
                "is_completed": False,
                "analysis_result": keywords_analysis,
                "is_academic_query": True,
                "need_search_strategy": True,
                "mode": mode,
                "messages": [AIMessage(content=response)],
                "should_search": False,  # chat&plan模式等待用户决策
                "cache_hit": False  # 标记非缓存结果
            }
            
        except Exception as e:
            error_msg = f"文献搜索分析失败: {str(e)}"
            print(f"❌ {error_msg}")
            from langchain_core.messages import AIMessage
            return {
                "current_step": "failed",
                "is_completed": False,
                "error_message": error_msg,
                "messages": [AIMessage(content="抱歉，文献搜索分析失败，请重新尝试。")]
            }
            
    async def _integrated_auto_search(self, state: PaperSearchState) -> Dict[str, Any]:
        """整合搜索模式 - 用于auto-search模式，一次性完成分析+搜索（支持全程缓存）"""
        try:
            user_message = state.get("user_message", "")
            mode = "auto-search"
            max_results = state.get("max_results", 10)
            year_from = state.get("year_from")
            year_to = state.get("year_to")
            sources = state.get("sources")
            
            print(f"🚀 整合搜索模式：分析+搜索一体化执行")
            
            # 🚀 检查完整搜索结果缓存
            full_cache_key = self._get_cache_key(user_message, mode, max_results)
            
            self._clean_expired_cache(self._search_results_cache)
            
            if full_cache_key in self._search_results_cache:
                cached_entry = self._search_results_cache[full_cache_key]
                if self._is_cache_valid(cached_entry):
                    print(f"⚡ 命中完整搜索结果缓存，跳过所有LLM和搜索调用")
                    
                    from langchain_core.messages import AIMessage
                    return {
                        "current_step": "completed",
                        "is_completed": True,
                        "analysis_result": cached_entry['analysis_result'],
                        "search_results": cached_entry['search_results'],
                        "search_keywords": cached_entry['search_keywords'],
                        "is_academic_query": True,
                        "mode": mode,
                        "messages": [AIMessage(content=cached_entry['response'])],
                        "should_search": False,
                        "cache_hit": True,
                        "cache_type": "full_search"
                    }
            
            # 第一步：关键词扩展分析（先检查部分缓存）
            keywords_analysis = None
            analysis_response = None
            
            # 检查关键词扩展缓存
            keyword_cache_key = self._get_cache_key(user_message, mode, 0)
            
            if keyword_cache_key in self._keyword_expansion_cache:
                cached_entry = self._keyword_expansion_cache[keyword_cache_key]
                if self._is_cache_valid(cached_entry):
                    print(f"⚡ 命中关键词扩展缓存，跳过LLM分析")
                    analysis_response = cached_entry['response']
                    keywords_analysis = cached_entry['analysis']
            
            # 如果缓存未命中，执行LLM分析
            if not keywords_analysis:
                from prompt_utils import get_literature_search_prompt
                prompt = get_literature_search_prompt(user_message, mode=mode)
                
                print(f"🔍 步骤1：关键词扩展分析（LLM调用）")
                analysis_response = await self.llm.simple_chat(prompt=prompt, timeout=60.0)
                
                # 解析分析结果
                if analysis_response and len(analysis_response.strip()) > 20:
                    keywords_analysis = self._extract_json_analysis(analysis_response)
                    
                    # 缓存关键词扩展结果
                    if keywords_analysis:
                        try:
                            cache_entry = {
                                'timestamp': time.time(),
                                'response': analysis_response,
                                'analysis': keywords_analysis,
                                'query': user_message,
                                'mode': mode
                            }
                            self._keyword_expansion_cache[keyword_cache_key] = cache_entry
                            print(f"💾 已缓存关键词扩展结果")
                        except Exception as e:
                            print(f"⚠️ 缓存关键词扩展失败: {e}")
            else:
                print(f"⚡ 使用缓存的关键词扩展")
            
            # keywords_analysis已在上面处理
            
            # 如果分析失败，使用基本回退
            if not keywords_analysis:
                print(f"⚠️ 分析失败，使用基本查询: {user_message}")
                keywords_analysis = {
                    "original_query": user_message,
                    "core_concepts": [user_message.strip()],
                    "domain": "学术研究",
                    "hierarchical_keywords": {
                        "exact_terms": {"terms": [user_message.strip()], "weight": 1.0}
                    }
                }
            
            # 第二步：基于分析结果执行搜索
            print(f"🔍 步骤2：执行并行搜索")
            search_query = self._build_search_query(user_message, keywords_analysis)
            print(f"📋 构建的搜索查询: {search_query}")
            
            # 获取搜索引擎并执行搜索
            search_engine = await self._get_search_engine()
            
            papers = []
            if hasattr(search_engine, 'search_parallel_with_filters'):
                papers = await search_engine.search_parallel_with_filters(
                    query=search_query,
                    max_results=max_results,
                    year_from=year_from,
                    year_to=year_to,
                    sources=sources
                )
            elif hasattr(search_engine, 'search_parallel'):
                papers = await search_engine.search_parallel(search_query, max_results)
            else:
                search_result = await search_engine.search_parallel(search_query, max_results)
                papers = search_result if isinstance(search_result, list) else search_result.get('papers', [])
                
            print(f"📚 搜索完成，找到 {len(papers)} 篇论文")
            
            # 第三步：格式化结果
            formatted_results = self._format_search_results(papers)
            search_keywords = self._extract_keywords_from_analysis(keywords_analysis)
            
            # 生成整合的响应消息
            from langchain_core.messages import AIMessage
            result_message = self._build_integrated_response(
                analysis_response, len(papers), search_keywords
            )
            
            # 🚀 缓存完整搜索结果
            try:
                full_cache_entry = {
                    'timestamp': time.time(),
                    'response': result_message,
                    'analysis_result': keywords_analysis,
                    'search_results': formatted_results,
                    'search_keywords': search_keywords,
                    'query': user_message,
                    'mode': mode,
                    'max_results': max_results
                }
                self._search_results_cache[full_cache_key] = full_cache_entry
                print(f"💾 已缓存完整搜索结果（{len(papers)}篇论文）")
            except Exception as e:
                print(f"⚠️ 缓存搜索结果失败: {e}")
            
            return {
                "current_step": "completed",
                "is_completed": True,  # auto-search模式直接完成
                "analysis_result": keywords_analysis,
                "search_results": formatted_results,
                "search_keywords": search_keywords,
                "is_academic_query": True,
                "mode": mode,
                "messages": [AIMessage(content=result_message)],
                "should_search": False,  # 已经完成搜索
                "cache_hit": False  # 标记非缓存结果
            }
            
        except Exception as e:
            error_msg = f"整合搜索失败: {str(e)}"
            print(f"❌ {error_msg}")
            from langchain_core.messages import AIMessage
            return {
                "current_step": "failed",
                "is_completed": False,
                "error_message": error_msg,
                "messages": [AIMessage(content=f"抱歉，搜索过程中出现错误：{error_msg}")]
            }
    
    def _build_integrated_response(self, analysis_response: str, paper_count: int, keywords: list) -> str:
        """构建整合搜索的响应消息"""
        try:
            # 提取分析响应中的有用信息，但简化展示
            response_lines = []
            
            # 简洁的搜索完成信息
            response_lines.append(f"🔍 已完成智能文献搜索，共找到 {paper_count} 篇相关论文。")
            
            # 展示关键词（如果有）
            if keywords:
                response_lines.append(f"\n📋 使用的搜索关键词: {', '.join(keywords[:5])}")
            
            # 简化的分析说明
            response_lines.append("\n✅ 已为您优化搜索策略并完成文献检索，详细结果请查看下方列表。")
            
            return "\n".join(response_lines)
        except:
            return f"✅ 搜索完成，找到 {paper_count} 篇相关论文。"
    
    async def academic_discussion_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """学术探讨处理节点"""
        try:
            user_message = state.get("user_message", "")
            mode = state.get("mode", "auto-search")
            print(f"🎓 学术探讨处理: {user_message} (模式: {mode})")
            
            # 使用简化的prompt工具函数
            from prompt_utils import get_academic_discussion_prompt
            prompt = get_academic_discussion_prompt(user_message, mode=mode)
            
            # 调用LLM进行学术讨论（增加超时时间）
            print(f"🤖 开始LLM学术讨论分析...")
            import time
            start_time = time.time()
            
            response = await self.llm.simple_chat(prompt=prompt, timeout=60.0)  # 增加到60秒
            end_time = time.time()
            print(f"✅ LLM调用完成，耗时: {end_time - start_time:.2f}秒，响应长度: {len(response) if response else 0}字符")
            
            # 验证LLM响应 - 如果失败直接抛出异常
            if not response or len(response.strip()) < 20:
                error_msg = f"学术讨论LLM响应无效: 长度={len(response) if response else 0}, 内容='{response}'"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # 🧹 应用统一的消息清洗处理
            cleaned_response = self._final_clean_response(response)
            print(f"📝 学术探讨消息清洗完成，清洗前: {len(response)} 字符，清洗后: {len(cleaned_response)} 字符")
            
            # 解析可能的关键词信息（恢复原始逻辑）
            keywords_analysis = self._extract_json_analysis(response)
            
            # 根据模式决定搜索建议策略
            should_suggest_search = False
            if mode == "auto-search":
                # 在auto-search模式下，学术探讨可以主动建议搜索
                should_suggest_search = bool(keywords_analysis)
            
            # 明确导入AIMessage避免作用域问题
            from langchain_core.messages import AIMessage
            
            return {
                "current_step": "discussion_completed",
                "is_completed": True,  # 学术探讨通常不需要后续搜索，除非用户主动要求
                "analysis_result": keywords_analysis,
                "is_academic_query": True,
                "need_search_strategy": False,  # 默认不自动搜索
                "mode": mode,
                "messages": [AIMessage(content=cleaned_response)],  # 使用清洗后的响应
                "search_suggestion": should_suggest_search  # 是否建议搜索
            }
            
        except Exception as e:
            error_msg = f"学术讨论失败: {str(e)}"
            print(f"❌ {error_msg}")
            from langchain_core.messages import AIMessage
            return {
                "current_step": "failed",
                "is_completed": False,
                "error_message": error_msg,
                "messages": [AIMessage(content="抱歉，学术讨论处理失败，请重新尝试。")]
            }
    
    # 已弃用：_map_intent_to_workflow 保留在版本历史中；当前工作流直接由节点路由函数驱动
    
    # 已移除：_generate_friendly_response（由快速闲聊逻辑取代）
    
    # 已移除：_generate_academic_discussion 与其备用逻辑（当前在节点中直接处理）
    
    # 已移除：旧版响应处理与备用分析逻辑（现有节点已覆盖同等回退）
    
    def _extract_json_analysis(self, response: str) -> Optional[Dict[str, Any]]:
        """从LLM响应中提取JSON分析结果"""
        try:
            print(f"🔧 JSON提取开始，响应总长度: {len(response)}")
            
            # 检查是否包含JSON标识符
            has_query_analysis = '"query_analysis"' in response
            has_core_concepts = '"core_concepts"' in response
            print(f"🔧 JSON标识符检查: query_analysis={has_query_analysis}, core_concepts={has_core_concepts}")
            
            # 使用更智能的JSON提取方法
            if has_query_analysis or has_core_concepts:
                # 查找完整的JSON块（从第一个{到最后一个}）
                json_start = response.find('{')
                print(f"🔧 JSON开始位置: {json_start}")
                
                if json_start != -1:
                    brace_count = 0
                    json_end = json_start
                    
                    for i in range(json_start, len(response)):
                        if response[i] == '{':
                            brace_count += 1
                        elif response[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    
                    print(f"🔧 JSON结束位置: {json_end}, 括号匹配状态: {'完整' if brace_count == 0 else '不完整'}")
                    
                    if brace_count == 0:  # 找到完整的JSON
                        json_str = response[json_start:json_end]
                        print(f"📝 提取到完整JSON，长度: {len(json_str)}")
                        print(f"🔧 JSON内容预览: {json_str[:150]}...")
                        
                        analysis = json.loads(json_str)
                        print(f"✅ 成功解析JSON分析结果，包含 {len(analysis)} 个顶级字段")
                        print(f"🔧 JSON字段: {list(analysis.keys())}")
                        return analysis
                    else:
                        print(f"⚠️ JSON结构不完整，括号不匹配，brace_count={brace_count}")
                        print(f"🔧 尝试备选解析方法...")
                        # 尝试找到最大的有效JSON块
                        for end_pos in range(len(response) - 1, json_start, -1):
                            if response[end_pos] == '}':
                                try_json = response[json_start:end_pos + 1]
                                try:
                                    analysis = json.loads(try_json)
                                    print(f"✅ 备选方法成功解析JSON，长度: {len(try_json)}")
                                    return analysis
                                except:
                                    continue
                        print(f"⚠️ 备选方法也失败")
                        return None
            
            # 原有的JSON查找逻辑作为备选
            print(f"🔧 使用正则表达式备选方法...")
            json_match = re.search(r'\{[\s\S]*?\}', response)
            if json_match:
                json_str = json_match.group()
                print(f"🔧 正则表达式找到JSON，长度: {len(json_str)}")
                analysis = json.loads(json_str)
                print(f"✅ 备选方法成功提取JSON分析结果")
                return analysis
            else:
                print("ℹ️ 响应中未包含JSON分析（可能是普通对话）")
                return None
        except json.JSONDecodeError as je:
            print(f"⚠️ JSON解析错误: {je}")
            print(f"⚠️ 错误位置: 行{je.lineno}, 列{je.colno}")
            print(f"⚠️ 问题JSON内容: {response[max(0, je.pos-50):je.pos+50]}")
            return None
        except Exception as e:
            print(f"⚠️ JSON提取失败: {type(e).__name__}: {e}")
            print(f"⚠️ 响应内容前200字符: {response[:200]}")
            return None
    
    # 已移除：_extract_user_friendly_response（不再需要单独提取）
    
    def _final_clean_response(self, response: str) -> str:
        """最终清理响应，统一处理JSON剥离和中文用户友好展示"""
        try:
            print(f"🧹 开始消息清洗，原始长度: {len(response)}")
            
            # 第一步：检测并剥离JSON内容
            cleaned_response = self._strip_json_content(response)
            
            # 第二步：优化中文表述和格式
            user_friendly_response = self._enhance_chinese_readability(cleaned_response)
            
            # 第三步：验证和质量保证
            final_response = self._ensure_response_quality(user_friendly_response, response)
            
            print(f"✅ 消息清洗完成，最终长度: {len(final_response)}")
            return final_response
                    
        except Exception as e:
            print(f"⚠️ 消息清洗失败: {e}")
            # 安全降级：返回基础清理版本
            return self._safe_fallback_cleaning(response)
    
    def _strip_json_content(self, response: str) -> str:
        """智能剥离JSON内容，保留用户友好的文本"""
        try:
            # 检测JSON存在
            json_indicators = ['"query_analysis"', '"core_concepts"', '"hierarchical_keywords"', '"domain"']
            has_json = any(indicator in response for indicator in json_indicators)
            
            if not has_json:
                print("📝 未检测到JSON内容，直接处理")
                return response
            
            # 查找JSON边界
            json_start = response.find('{')
            if json_start == -1:
                return response
            
            brace_count = 0
            json_end_pos = None
            
            for i in range(json_start, len(response)):
                if response[i] == '{':
                    brace_count += 1
                elif response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end_pos = i + 1
                        break
            
            if json_end_pos:
                # 提取JSON前后的用户友好内容
                before_json = response[:json_start].strip()
                after_json = response[json_end_pos:].strip()
                
                # 清理代码块标记
                after_json = re.sub(r'```[\s\S]*?```', '', after_json).strip()
                
                # 组合前后内容
                combined = (before_json + "\n\n" + after_json).strip()
                print(f"🔍 JSON剥离完成，提取内容长度: {len(combined)}")
                return combined if combined else after_json
            
            return response
            
        except Exception as e:
            print(f"⚠️ JSON剥离失败: {e}")
            return response
    
    def _enhance_chinese_readability(self, text: str) -> str:
        """优化中文表述和可读性"""
        if not text or len(text) < 10:
            return text
            
        try:
            # 移除多余的格式标记
            cleaned = re.sub(r'```[\s\S]*?```', '', text)
            cleaned = re.sub(r'^\s*[#*\-\s]*普通对话模式[:：]?\s*', '', cleaned, flags=re.MULTILINE)
            
            # 优化段落分隔
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
            
            # 确保emoji后有适当间距
            cleaned = re.sub(r'([🎓📊🔍💡🚀📚⚡✨])(\S)', r'\1 \2', cleaned)
            
            # 优化列表格式
            cleaned = re.sub(r'\n\s*[-*]\s*', '\n• ', cleaned)
            
            print(f"📝 中文可读性优化完成")
            return cleaned.strip()
            
        except Exception as e:
            print(f"⚠️ 中文优化失败: {e}")
            return text
    
    def _ensure_response_quality(self, processed_text: str, original_response: str) -> str:
        """确保响应质量，必要时进行补充"""
        if not processed_text or len(processed_text) < 20:
            print(f"⚠️ 处理后内容过少，尝试从原始响应恢复")
            
            # 尝试从原始响应中提取有用内容
            fallback = self._extract_meaningful_content(original_response)
            if len(fallback) > len(processed_text):
                return fallback
        
        # 检查是否包含基本的学术讨论要素
        if len(processed_text) > 50 and any(indicator in processed_text for indicator in ['🎓', '📊', '🔍', '💡']):
            print(f"✅ 学术讨论内容质量良好")
            return processed_text
        elif len(processed_text) > 100:  # 提高阈值，避免过度增强
            print(f"✅ 基础讨论内容质量可接受")
            return processed_text
        elif len(processed_text) > 30:  # 中等长度内容，检查是否需要增强
            print(f"📝 内容长度适中，保持原样")
            return processed_text
        else:
            print(f"⚠️ 内容质量需要增强")
            return self._generate_enhanced_discussion(processed_text, original_response)
    
    def _safe_fallback_cleaning(self, response: str) -> str:
        """安全降级清理方案"""
        if not response:
            return "抱歉，我无法生成完整的回复，请重新尝试。"
        
        # 基础清理
        cleaned = response.strip()
        cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
        cleaned = re.sub(r'\{[\s\S]*?\}', '', cleaned)  # 简单移除大括号内容
        cleaned = cleaned.strip()
        
        return cleaned if len(cleaned) > 10 else response[:200]
    
    def _extract_meaningful_content(self, text: str) -> str:
        """从文本中提取有意义的内容"""
        if not text:
            return ""
        
        # 按段落分割，保留较长的非JSON段落
        paragraphs = text.split('\n')
        meaningful_parts = []
        
        for para in paragraphs:
            para = para.strip()
            if (len(para) > 20 and 
                not para.startswith('{') and 
                not '"' in para[:10] and
                '🎓' in para or '📊' in para or '🔍' in para or '💡' in para or len(para) > 50):
                meaningful_parts.append(para)
        
        return '\n\n'.join(meaningful_parts)
    
    def _generate_enhanced_discussion(self, base_content: str, original_response: str) -> str:
        """生成增强的学术讨论内容"""
        try:
            # 从原始响应尝试提取主题
            topic_hints = re.findall(r'["""]([^"""]+)["""]', original_response)
            topic = topic_hints[0] if topic_hints else "该学术问题"
            
            enhanced = base_content if base_content else f"关于{topic}的学术探讨："
            
            if '🎓' not in enhanced:
                enhanced += f"\n\n🎓 **专业分析**\n这是一个值得深入研究的学术问题，涉及多个理论层面和实践应用。"
            
            if '📊' not in enhanced:
                enhanced += f"\n\n📊 **研究现状**\n当前在这一领域的研究正在快速发展，国内外都有重要进展。"
            
            if '💡' not in enhanced:
                enhanced += f"\n\n💡 **研究建议**\n建议从多角度进行综合分析，结合理论研究和实证分析。"
            
            return enhanced
            
        except Exception as e:
            print(f"⚠️ 增强讨论生成失败: {e}")
            return base_content or "感谢您的学术问题，这是一个很有价值的研究方向。"
    
    # 已移除：不再使用的解释增强与关键词提取辅助函数
    
    # 已移除：_generate_enhanced_response（质量保障流程已足够）
    
    # 已移除：_generate_fallback_explanation（不再需要）
    
    def route_after_literature_search(self, state: PaperSearchState) -> str:
        """文献搜索节点后的路由决策（优化版）"""
        mode = state.get("mode", "auto-search")
        is_completed = state.get("is_completed", False)
        should_search = state.get("should_search", False)
        
        print(f"📋 文献搜索后路由: 模式={mode}, 已完成={is_completed}, 应该搜索={should_search}")
        
        if mode == "auto-search":
            if is_completed:
                print("✅ auto-search模式已完成整合搜索，直接结束")
                return "completed"
            elif should_search:
                print("🔍 auto-search模式降级，执行传统搜索")
                return "search"
            else:
                print("⚠️ auto-search模式异常，等待决策")
                return "wait_decision"
        else:
            # chat&plan模式
            print("💬 chat&plan模式，展示分析结果等待用户决策")
            return "wait_decision"
    
    def should_execute_search_after_discussion(self, state: PaperSearchState) -> str:
        """学术探讨节点后的路由决策"""
        mode = state.get("mode", "auto-search") 
        search_suggestion = state.get("search_suggestion", False)
        
        print(f"🎓 学术探讨后路由: 模式={mode}, 搜索建议={search_suggestion}")
        
        # 学术探讨通常不自动搜索，只在特殊情况下建议
        # 这里暂时都返回 "end"，未来可以根据需要添加更复杂的逻辑
        return "end"
    
    # 已移除：未使用的路由决策辅助函数 should_execute_search
    
    async def search_execution_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """搜索执行节点 - 调用现有多源搜索引擎"""
        try:
            query = state.get("query", "")
            max_results = state.get("max_results", 10)
            analysis = state.get("analysis_result", {})
            year_from = state.get("year_from")
            year_to = state.get("year_to")
            sources = state.get("sources")
            
            print(f"🔍 开始执行搜索: query={query}, max_results={max_results}")
            
            # 构建搜索查询
            search_query = self._build_search_query(query, analysis)
            print(f"📋 构建的搜索查询: {search_query}")
            
            # 获取搜索引擎并执行搜索
            search_engine = await self._get_search_engine()
            
            # MultiSourceEngine使用不同的搜索接口
            if hasattr(search_engine, 'search_parallel_with_filters'):
                # 使用新的带筛选的搜索方法
                papers = await search_engine.search_parallel_with_filters(
                    query=search_query,
                    max_results=max_results,
                    year_from=year_from,
                    year_to=year_to,
                    sources=sources
                )
            elif hasattr(search_engine, 'search_parallel'):
                papers = await search_engine.search_parallel(search_query, max_results)
            else:
                # 兜底：使用基础搜索接口
                search_result = await search_engine.search_parallel(search_query, max_results)
                papers = search_result if isinstance(search_result, list) else search_result.get('papers', [])
            print(f"📚 搜索完成，找到 {len(papers)} 篇论文")
            
            # 转换为标准格式
            formatted_results = self._format_search_results(papers)
            
            return {
                "current_step": "searched",
                "search_results": formatted_results,
                "search_keywords": self._extract_keywords_from_analysis(analysis)
            }
            
        except Exception as e:
            error_msg = f"搜索执行失败: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "search_results": []
            }
    
    def _build_search_query(self, original_query: str, analysis: Optional[Dict[str, Any]]) -> str:
        """根据分析结果构建简化且有效的搜索查询"""
        if not analysis:
            return original_query
        
        try:
            # 提取层次化关键词
            hierarchical = analysis.get("hierarchical_keywords", {})
            exact_terms = hierarchical.get("exact_terms", {}).get("terms", [])
            core_synonyms = hierarchical.get("core_synonyms", {}).get("terms", [])
            related_terms = hierarchical.get("related_terms", {}).get("terms", [])
            context_terms = hierarchical.get("context_terms", {}).get("terms", [])
            
            # 简化策略：构建多层次查询，从严格到宽松
            all_important_terms = []
            
            # 1. 优先使用核心术语（exact_terms 和 core_synonyms）
            if exact_terms:
                # 只取前2个最重要的精确术语
                quoted_exact = [f'"{term}"' if ' ' in term else term for term in exact_terms[:2]]
                all_important_terms.extend(quoted_exact)
            
            if core_synonyms and len(all_important_terms) < 3:
                # 如果核心术语不够，补充同义词
                quoted_synonyms = [f'"{term}"' if ' ' in term else term for term in core_synonyms[:2]]
                all_important_terms.extend(quoted_synonyms)
            
            # 2. 如果仍然没有足够术语，添加相关术语
            if len(all_important_terms) < 2 and related_terms:
                quoted_related = [f'"{term}"' if ' ' in term else term for term in related_terms[:1]]
                all_important_terms.extend(quoted_related)
            
            # 3. 构建简化查询
            if len(all_important_terms) >= 2:
                # 使用前2-3个最重要的术语，用AND连接
                main_query = " AND ".join(all_important_terms[:3])
                
                # 如果有额外的同义词，作为可选扩展（用OR）
                optional_terms = []
                remaining_synonyms = core_synonyms[2:4] if len(core_synonyms) > 2 else []
                if remaining_synonyms:
                    optional_terms.extend([f'"{term}"' if ' ' in term else term for term in remaining_synonyms])
                
                if optional_terms:
                    # 组合主查询和可选术语
                    optional_group = " OR ".join(optional_terms)
                    final_query = f"({main_query}) AND ({optional_group})"
                else:
                    final_query = main_query
                    
            elif len(all_important_terms) == 1:
                # 如果只有一个术语，尝试添加同义词扩展
                main_term = all_important_terms[0]
                if core_synonyms:
                    # 添加同义词选择
                    synonyms = [f'"{term}"' if ' ' in term else term for term in core_synonyms[:3]]
                    all_terms = [main_term] + synonyms
                    final_query = " OR ".join(all_terms)
                else:
                    final_query = main_term
            else:
                # 回退到原始查询
                final_query = original_query
            
            print(f"🎯 构建的简化查询: {final_query}")
            print(f"📊 查询组件: 使用核心术语={len(all_important_terms)}, 总可用关键词={len(exact_terms) + len(core_synonyms) + len(related_terms)}")
            
            return final_query
            
        except Exception as e:
            print(f"⚠️ 查询构建失败，使用原始查询: {e}")
            return original_query
    
    def _extract_keywords_from_analysis(self, analysis: Optional[Dict[str, Any]]) -> List[str]:
        """从分析结果中提取关键词列表"""
        if not analysis:
            return []
        
        keywords = []
        try:
            hierarchical = analysis.get("hierarchical_keywords", {})
            for level in ["exact_terms", "core_synonyms", "related_terms", "context_terms"]:
                terms = hierarchical.get(level, {}).get("terms", [])
                keywords.extend(terms)
            return keywords[:10]  # 限制关键词数量
        except Exception as e:
            print(f"⚠️ 关键词提取失败: {e}")
            return []
    
    def _format_search_results(self, papers: List) -> List[Dict[str, Any]]:
        """格式化搜索结果为标准格式 - 确保元信息完整性"""
        formatted_results = []
        
        for i, paper in enumerate(papers):
            try:
                # 处理Paper对象或字典
                if hasattr(paper, '__dict__'):
                    # Paper对象转换为字典，确保所有字段都被正确提取
                    paper_dict = {
                        "title": self._safe_get_attr(paper, 'title', ''),
                        "authors": self._safe_get_attr(paper, 'authors', []),
                        "abstract": self._safe_get_attr(paper, 'abstract', ''),
                        "year": self._safe_get_attr(paper, 'year', None),
                        "journal": self._safe_get_attr(paper, 'journal', ''),
                        "url": self._safe_get_attr(paper, 'url', ''),
                        "doi": self._safe_get_attr(paper, 'doi', None),
                        "citations": self._safe_get_attr(paper, 'citations', 0),
                        "source": self._safe_get_attr(paper, 'source', 'unknown'),
                        "relevance_score": self._safe_get_attr(paper, 'relevance_score', 0.0),
                        # 附加字段
                        "pmid": self._safe_get_attr(paper, 'pmid', None),
                        "keywords": self._safe_get_attr(paper, 'keywords', None)
                    }
                elif isinstance(paper, dict):
                    # 字典格式，确保包含所有必要字段
                    paper_dict = {
                        "title": paper.get('title', ''),
                        "authors": paper.get('authors', []),
                        "abstract": paper.get('abstract', ''),
                        "year": paper.get('year', None),
                        "journal": paper.get('journal', ''),
                        "url": paper.get('url', ''),
                        "doi": paper.get('doi', None),
                        "citations": paper.get('citations', 0),
                        "source": paper.get('source', 'unknown'),
                        "relevance_score": paper.get('relevance_score', 0.0),
                        "pmid": paper.get('pmid', None),
                        "keywords": paper.get('keywords', None)
                    }
                else:
                    print(f"⚠️ 未知格式的论文对象 (索引 {i}): {type(paper)}")
                    continue
                
                # 数据完整性验证和清理
                paper_dict = self._validate_and_clean_paper_data(paper_dict, i)
                
                formatted_results.append(paper_dict)
                
            except Exception as e:
                print(f"❌ 论文格式化失败 (索引 {i}): {e}")
                # 尝试生成一个最小化的有效条目，避免完全丢失数据
                try:
                    fallback_dict = {
                        "title": str(paper) if hasattr(paper, '__str__') else f"论文 {i+1}",
                        "authors": [],
                        "abstract": "",
                        "year": None,
                        "journal": "",
                        "url": "",
                        "doi": None,
                        "citations": 0,
                        "source": "unknown",
                        "relevance_score": 0.0,
                        "pmid": None,
                        "keywords": None,
                        "_processing_error": str(e)  # 记录错误信息
                    }
                    formatted_results.append(fallback_dict)
                    print(f"⚠️ 使用备用格式保存论文 {i+1}")
                except:
                    print(f"❌ 完全无法处理论文 {i+1}，跳过")
                    continue
        
        print(f"✅ 论文格式化完成: {len(formatted_results)}/{len(papers)} 篇成功处理")
        return formatted_results
    
    def _safe_get_attr(self, obj, attr_name: str, default_value):
        """安全获取对象属性，避免属性访问错误"""
        try:
            value = getattr(obj, attr_name, default_value)
            # 特殊处理一些可能的空值情况
            if value is None:
                return default_value
            if isinstance(value, str) and value.strip() == "":
                return default_value if default_value != "" else ""
            return value
        except Exception as e:
            print(f"⚠️ 获取属性 {attr_name} 失败: {e}")
            return default_value
    
    def _validate_and_clean_paper_data(self, paper_dict: Dict[str, Any], index: int) -> Dict[str, Any]:
        """验证和清理论文数据，确保完整性"""
        try:
            # 确保标题不为空
            if not paper_dict.get('title') or paper_dict['title'].strip() == "":
                paper_dict['title'] = f"未知标题 #{index + 1}"
            
            # 确保作者是列表格式
            if not isinstance(paper_dict.get('authors'), list):
                authors = paper_dict.get('authors', '')
                if isinstance(authors, str) and authors.strip():
                    # 尝试解析字符串格式的作者
                    paper_dict['authors'] = [auth.strip() for auth in authors.split(',')]
                else:
                    paper_dict['authors'] = []
            
            # 清理并验证数值字段
            try:
                citations = paper_dict.get('citations', 0)
                paper_dict['citations'] = int(citations) if citations is not None else 0
            except (ValueError, TypeError):
                paper_dict['citations'] = 0
            
            try:
                year = paper_dict.get('year')
                if year is not None:
                    year_int = int(year)
                    # 年份合理性检查
                    if 1900 <= year_int <= 2030:
                        paper_dict['year'] = year_int
                    else:
                        paper_dict['year'] = None
                else:
                    paper_dict['year'] = None
            except (ValueError, TypeError):
                paper_dict['year'] = None
            
            try:
                score = paper_dict.get('relevance_score', 0.0)
                paper_dict['relevance_score'] = float(score) if score is not None else 0.0
            except (ValueError, TypeError):
                paper_dict['relevance_score'] = 0.0
            
            # 确保字符串字段不为None
            for field in ['abstract', 'journal', 'url', 'source']:
                if paper_dict.get(field) is None:
                    paper_dict[field] = ""
            
            # 确保DOI字段格式正确
            doi = paper_dict.get('doi')
            if doi and not isinstance(doi, str):
                paper_dict['doi'] = str(doi)
            
            return paper_dict
            
        except Exception as e:
            print(f"⚠️ 论文数据验证失败 (索引 {index}): {e}")
            return paper_dict
    
    async def result_formatting_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """结果格式化节点 - 保持原有的学术分析内容，不覆盖"""
        try:
            search_results = state.get("search_results", [])
            analysis = state.get("analysis_result", {})
            keywords = state.get("search_keywords", [])
            
            print(f"📋 保持原有学术分析内容，搜索到 {len(search_results)} 个结果")
            
            # 🔑 重要修改：不覆盖intent_analysis_node生成的详细学术指导
            # 保持原有的详细分析内容，让用户看到完整的专业解读
            existing_messages = state.get("messages", [])
            if existing_messages:
                print(f"✅ 保持现有的详细学术分析内容")
                return {
                    "current_step": "completed",
                    "is_completed": True
                    # 🔑 关键：不设置messages字段，保持原有内容
                }
            else:
                # 备用响应（正常情况下不会到这里）
                fallback_response = "✅ 已完成学术分析和关键词扩展。请查看右侧关键词云进行进一步的文献搜索。"
                print(f"⚠️ 使用备用响应")
                # 局部导入AIMessage
                from langchain_core.messages import AIMessage
                return {
                    "current_step": "completed",  
                    "is_completed": True,
                    "messages": [AIMessage(content=fallback_response)]
                }
            
        except Exception as e:
            error_msg = f"结果格式化失败: {str(e)}"
            print(f"❌ {error_msg}")
            # 局部导入AIMessage
            from langchain_core.messages import AIMessage
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "is_completed": False,
                "messages": [AIMessage(content=f"结果处理出错：{error_msg}")]
            }
    
    # 已移除：未使用的结果构建辅助函数 _build_search_response
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            self._clean_expired_cache(self._keyword_expansion_cache)
            self._clean_expired_cache(self._search_results_cache)
            
            return {
                "keyword_cache_size": len(self._keyword_expansion_cache),
                "search_cache_size": len(self._search_results_cache),
                "cache_ttl_minutes": self._cache_ttl // 60,
                "max_cache_size": self._max_cache_size,
                "total_cache_entries": len(self._keyword_expansion_cache) + len(self._search_results_cache)
            }
        except:
            return {"error": "获取缓存统计失败"}
    
    def clear_cache(self) -> bool:
        """清空所有缓存"""
        try:
            self._keyword_expansion_cache.clear()
            self._search_results_cache.clear()
            print("🗑️ 所有缓存已清空")
            return True
        except Exception as e:
            print(f"⚠️ 清空缓存失败: {e}")
            return False
    
    async def search_papers(self, query: str, max_results: int = 10, thread_id: str = None, mode: str = "auto-search", force_search: bool = False, year_from: Optional[int] = None, year_to: Optional[int] = None, sources: Optional[List[str]] = None, allow_search: bool = True, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """主要搜索接口"""
        if thread_id is None:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        
        initial_state = create_initial_state(
            query=query,
            user_message=query,
            mode=mode,  # 传递模式参数
            max_results=max_results,
            force_search=force_search,  # 传递强制搜索标志
            allow_search=allow_search,
            year_from=year_from,
            year_to=year_to,
            sources=sources
        )

        # 注入历史对话（最近20条）
        try:
            if history and isinstance(history, list) and len(history) > 0:
                from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
                converted_messages: List = []
                for item in history[-20:]:
                    role = (item.get('role') or '').lower()
                    content = item.get('content') or ''
                    if not content:
                        continue
                    if role == 'user':
                        converted_messages.append(HumanMessage(content=content))
                    elif role == 'assistant':
                        converted_messages.append(AIMessage(content=content))
                    elif role == 'system':
                        converted_messages.append(SystemMessage(content=content))
                if converted_messages:
                    initial_state['messages'] = converted_messages
        except Exception as e:
            print(f"⚠️ 注入历史失败: {e}")
        
        print(f"🚀 启动智能学术搜索工作流 - 查询: {query}")
        
        config = {"configurable": {"thread_id": thread_id}} if self.enable_memory else {}
        
        try:
            final_state = await self.graph.ainvoke(initial_state, config)
            
            messages = final_state.get("messages", [])
            is_completed = final_state.get("is_completed", False)
            error_message = final_state.get("error_message")
            
            final_response = ""
            if messages:
                # 导入AIMessage避免作用域错误
                from langchain_core.messages import AIMessage
                ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
                if ai_messages:
                    # 直接使用已经清理过的响应
                    final_response = ai_messages[-1].content
            
            result = {
                "success": is_completed and not error_message,
                "response": final_response,
                "error_message": error_message,
                "thread_id": thread_id,
                "query": query,
                "search_results": final_state.get("search_results", []),  # 返回搜索结果
                "analysis_result": final_state.get("analysis_result"),
                "is_academic_query": final_state.get("is_academic_query", False),
                "need_search_strategy": final_state.get("need_search_strategy", False)
            }
            
            print(f"✅ 工作流完成: {'成功' if result['success'] else '失败'}")
            return result
            
        except Exception as e:
            error_msg = f"工作流执行错误: {str(e)}"
            error_str = str(e).lower()
            
            # 检查是否是CAPTCHA相关错误
            if 'captcha' in error_str or 'blocked' in error_str:
                user_friendly_msg = "搜索服务暂时受限，请稍等片刻后重试，或尝试使用其他关键词。"
                print(f"⚠️ CAPTCHA限制: {error_msg}")
            else:
                user_friendly_msg = "处理您的请求时出现错误，请稍后再试。"
                print(f"❌ {error_msg}")
                import traceback
                print(f"🔧 详细错误堆栈: {traceback.format_exc()}")
            
            return {
                "success": False,
                "response": user_friendly_msg,
                "error_message": error_msg,
                "thread_id": thread_id,
                "query": query,
                "search_results": [],  # 错误情况下返回空结果
                "analysis_result": None,
                "is_academic_query": False,
                "need_search_strategy": False
            }


# 模拟搜索引擎已删除 - 仅使用真实数据源


# 全局实例和便捷函数
_intelligent_agent = None

def get_intelligent_paper_search_agent(enable_memory: bool = True) -> IntelligentPaperSearchAgent:
    """获取智能搜索Agent实例"""
    global _intelligent_agent
    if _intelligent_agent is None:
        _intelligent_agent = IntelligentPaperSearchAgent(enable_memory=enable_memory)
    return _intelligent_agent

async def chat_with_search_strategy(query: str, thread_id: str = None, force_search: bool = False, max_results: int = 10, year_from: Optional[int] = None, year_to: Optional[int] = None, sources: Optional[List[str]] = None, allow_search: bool = True, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """智能聊天与搜索策略分析的统一入口"""
    agent = get_intelligent_paper_search_agent()
    return await agent.search_papers(query, max_results, thread_id, force_search, year_from, year_to, sources, allow_search, history)


# 测试功能
async def test_intelligent_agent():
    """测试智能搜索Agent"""
    print("🧪 测试智能学术搜索工作流")
    print("=" * 50)
    
    # 测试1: 学术查询
    result1 = await chat_with_search_strategy("机器学习算法研究")
    print(f"测试1 - 学术查询: 成功={result1['success']}")
    print(f"是否为学术查询: {result1['is_academic_query']}")
    print(f"回答预览: {result1['response'][:200]}...")
    print()
    
    # 测试2: 普通对话
    result2 = await chat_with_search_strategy("你好，今天天气怎么样？")  
    print(f"测试2 - 普通对话: 成功={result2['success']}")
    print(f"是否为学术查询: {result2['is_academic_query']}")
    print(f"回答预览: {result2['response'][:200]}...")
    
    print("✅ 智能搜索工作流测试完成")


if __name__ == "__main__":
    asyncio.run(test_intelligent_agent())