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
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)
 

from langchain_core.messages import HumanMessage, SystemMessage
# AIMessage将在每个需要的函数内部局部导入以避免作用域冲突
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# 导入项目模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# prompt_manager已删除，使用简化的prompt_utils
# 移除意图分类器导入 - 改为直接模式路由

from llm_interface import get_llm_for_langgraph
from langchain_workflows.state_schemas import PaperSearchState, create_initial_state

class IntelligentPaperSearchAgent:
    """
    智能学术搜索Agent - 集成现有多源搜索引擎
    工作流：START → 模式路由 → 关键词扩展 → 搜索执行 → 结果处理 → END
    """
    
    def __init__(self, enable_memory: bool = True):
        # 简单内存缓存 - 避免重复的LLM调用和搜索
        self._keyword_expansion_cache = {}  # 关键词扩展缓存
        self._cache_ttl = 1800  # 缓存30分钟
        self._max_cache_size = 100  # 最大缓存条目数
        self.enable_memory = enable_memory
        # 使用统一LLM接口
        self.llm = get_llm_for_langgraph()
        
        # 移除意图分类器 - 改为直接模式路由
        logger.info("🚀 [工作流] 智能Agent初始化完成（模式直接路由）")
        
        self.checkpointer = MemorySaver() if enable_memory else None
        self.graph = self._build_graph()
        
        # 延迟加载搜索引擎（避免循环依赖）
        self._search_engine = None
        
        logger.info("💾 [工作流] 智能缓存系统已启用")
    
    async def _get_search_engine(self):
        """获取搜索引擎实例（延迟加载）- 避免循环依赖"""
        if self._search_engine is None:
            try:
                # 使用真实的MultiSourceEngine，删除模拟引擎依赖
                from multi_source_engine import MultiSourceEngine
                self._search_engine = MultiSourceEngine()
                logger.info("🌐 [搜索引擎] 多源引擎实例化成功")
            except Exception as e:
                logger.error(f"❌ [搜索引擎] 实例化失败: {e}")
                raise Exception(f"无法初始化搜索引擎: {e}，请检查依赖包安装")
        return self._search_engine
    
    async def _preheat_search_engine_async(self):
        """异步预热搜索引擎，为后续搜索做准备"""
        try:
            # 并行预热任务：实例化搜索引擎和预加载必要组件
            await self._get_search_engine()
            logger.info("🔥 [搜索引擎] 预热完成")
        except Exception as e:
            logger.warning(f"⚠️ [搜索引擎] 预热失败（不影响主流程）: {e}")
            # 预热失败不抛出异常，不影响主流程
    
    
    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(PaperSearchState)
        
        # 添加核心节点（移除意图分析节点）
        workflow.add_node("chat_conversation", self.chat_conversation_node)
        workflow.add_node("literature_search", self.literature_search_node) 
        workflow.add_node("academic_discussion", self.academic_discussion_node)
        
        # 搜索和结果处理节点
        workflow.add_node("search_execution", self.search_execution_node)
        workflow.add_node("result_formatting", self.result_formatting_node)
        
        # 定义流程路径 - 直接从START根据用户模式路由
        workflow.add_conditional_edges(
            START,
            self.route_by_mode,
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
    
    def route_by_mode(self, state: PaperSearchState) -> str:
        """直接根据用户模式选择路由，移除复杂的意图分析"""
        mode = state.get("mode", "auto-search")
        user_message = state.get("user_message", "")
        
        print(f"模式路由：mode={mode}, message={user_message[:40]}...")
        
        # 快速闲聊预筛选（保留现有逻辑，避免浪费资源）
        quick_intent = self._quick_chat_filter(user_message)
        if quick_intent == "闲聊":
            print("快速识别为闲聊，路由到对话节点")
            return "chat_conversation"
        
        # 直接根据用户选择的模式路由
        if mode == "auto-search":
            print("Auto-search模式 → 直接进入文献搜索")
            return "literature_search"
        else:  # chat&plan 模式
            print("Chat&Plan模式 → 直接进入学术探讨")
            return "academic_discussion"
    
    def _quick_chat_filter(self, message: str) -> Optional[str]:
        """快速闲聊预筛选 - 避免明显的闲聊进入复杂工作流"""
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
        
        # 短消息通常是闲聊
        if len(message.strip()) <= 10:
            for pattern in greeting_patterns:
                if pattern in message_lower:
                    return "闲聊"
        
        # 检查各种闲聊模式
        all_casual_patterns = greeting_patterns + system_patterns
        for pattern in all_casual_patterns:
            if pattern in message_lower:
                return "闲聊"
        
        return None  # 无法快速判断为闲聊
    
    async def chat_conversation_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """优化的闲聊对话处理节点 - 减少LLM调用"""
        try:
            user_message = state.get("user_message", "")
            print(f"闲聊对话处理: {user_message}")
            
            # 🚀 优化策略：对常见闲聊使用预定义回复，减少LLM调用
            quick_response = self._get_quick_chat_response(user_message)
            if quick_response:
                print("使用快速回复")
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
            print("使用LLM生成回复")
            from prompt_utils import get_chat_conversation_prompt
            prompt = get_chat_conversation_prompt(user_message)
            
            # 调用LLM生成对话回复（使用简单聊天超时配置）
            import os
            simple_timeout = float(os.getenv('SIMPLE_CHAT_TIMEOUT', '30.0'))
            response = await self.llm.simple_chat(prompt=prompt, timeout=simple_timeout)
            
            # 🧹 应用统一的消息清洗处理
            cleaned_response = self._final_clean_response(response)
            print("消息清洗完成")
            
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
            print(f"错误: {error_msg}")
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
            print(f"缓存清理失败: {e}")
    
    async def literature_search_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """文献搜索处理节点 - 统一使用关键词扩展流程（支持缓存）"""
        mode = state.get("mode", "auto-search")
        user_message = state.get("user_message", "")
        print(f"文献搜索处理: {user_message} (模式: {mode})")
        
        # 所有模式都使用相同的关键词扩展逻辑
        result = await self._analysis_only_search(state)
        
        # 根据模式调整响应和搜索标记
        if mode == "auto-search":
            # 设置自动搜索标记 - 确保状态正确传递
            result["should_search"] = True
            result["mode"] = mode  # 确保模式也被保持
            
            # 保留原始详细分析内容，不用简单提示覆盖
            # result["messages"]保持不变，保留详细的关键词分析响应
            
            print("auto-search模式：保留详细分析 + 自动搜索")
        else:
            # chat&plan模式保持原有逻辑，等待用户决策
            result["should_search"] = False
            print("chat&plan模式：等待用户决策")
        
        return result
            
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
                    print("命中关键词扩展缓存")
                    
                    from langchain_core.messages import AIMessage
                    cached_response = cached_entry['response']
                    cached_analysis = cached_entry['analysis']
                    
                    # 🧹 对缓存的响应也进行清洗，移除JSON内容
                    cleaned_cached_response = self._final_clean_response(cached_response)
                    print("缓存响应清洗完成")
                    
                    return {
                        "current_step": "search_ready",
                        "is_completed": False,
                        "analysis_result": cached_analysis,
                        "is_academic_query": True,
                        "need_search_strategy": True,
                        "mode": mode,
                        "messages": [AIMessage(content=cleaned_cached_response)],  # 使用清洗后的缓存响应
                        "should_search": False,
                        "cache_hit": True  # 标记缓存命中
                    }
            
            # 使用完整的文献搜索prompt（支持模式化说明）
            from prompt_utils import get_literature_search_prompt
            prompt = get_literature_search_prompt(user_message, mode=mode)
            
            # 调用LLM进行关键词扩展和搜索分析（使用学术搜索超时配置）
            import os
            academic_timeout = float(os.getenv('ACADEMIC_SEARCH_TIMEOUT', '120.0'))
            response = await self.llm.simple_chat(prompt=prompt, timeout=academic_timeout)
            
            # 验证LLM响应
            if not response or len(response.strip()) < 20:
                print("LLM响应异常，使用回退机制")
                
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
            
            # 🧹 清洗响应，移除JSON内容，只保留用户友好的中文内容
            cleaned_response = self._final_clean_response(response)
            print("响应清洗完成")
            
            # 🚀 缓存关键词扩展结果
            if keywords_analysis:
                try:
                    cache_entry = {
                        'timestamp': time.time(),
                        'response': response,  # 缓存原始响应，以便后续清洗
                        'analysis': keywords_analysis,
                        'query': user_message,
                        'mode': mode
                    }
                    self._keyword_expansion_cache[cache_key] = cache_entry
                    print("已缓存关键词扩展结果")
                except Exception as e:
                    print(f"缓存失败: {e}")
            
            from langchain_core.messages import AIMessage
            return {
                "current_step": "search_ready",
                "is_completed": False,
                "analysis_result": keywords_analysis,
                "is_academic_query": True,
                "need_search_strategy": True,
                "mode": mode,
                "messages": [AIMessage(content=cleaned_response)],  # 使用清洗后的响应
                "should_search": False,  # chat&plan模式等待用户决策
                "cache_hit": False  # 标记非缓存结果
            }
            
        except Exception as e:
            error_msg = f"文献搜索分析失败: {str(e)}"
            print(f"错误: {error_msg}")
            from langchain_core.messages import AIMessage
            return {
                "current_step": "failed",
                "is_completed": False,
                "error_message": error_msg,
                "messages": [AIMessage(content="抱歉，文献搜索分析失败，请重新尝试。")]
            }
            
    async def academic_discussion_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """学术探讨处理节点"""
        try:
            user_message = state.get("user_message", "")
            mode = state.get("mode", "auto-search")
            print(f"学术探讨处理: {user_message} (模式: {mode})")
            
            # 使用简化的prompt工具函数
            from prompt_utils import get_academic_discussion_prompt
            prompt = get_academic_discussion_prompt(user_message, mode=mode)
            
            # 并行处理：LLM学术讨论 + 搜索引擎预热
            print("🚀 开始并行LLM学术讨论分析 + 搜索引擎预热")
            import time
            start_time = time.time()
            
            # 使用复杂查询超时配置
            complex_timeout = float(os.getenv('COMPLEX_QUERY_TIMEOUT', '90.0'))
            
            # 并行任务1：LLM学术讨论
            llm_task = asyncio.create_task(
                self.llm.simple_chat(prompt=prompt, timeout=complex_timeout)
            )
            
            # 并行任务2：预热搜索引擎（为可能的后续搜索做准备）
            search_engine_preheat_task = asyncio.create_task(
                self._preheat_search_engine_async()
            )
            
            # 等待LLM响应完成（搜索引擎预热在后台继续）
            response = await llm_task
            end_time = time.time()
            print(f"✅ LLM调用完成，耗时: {end_time - start_time:.2f}秒")
            
            # 检查搜索引擎预热状态（不阻塞主流程）
            try:
                await asyncio.wait_for(search_engine_preheat_task, timeout=0.1)
                print("✅ 搜索引擎预热完成")
            except asyncio.TimeoutError:
                print("⏳ 搜索引擎预热在后台继续...")
            
            # 验证LLM响应 - 如果失败直接抛出异常
            if not response or len(response.strip()) < 20:
                error_msg = f"学术讨论LLM响应无效: 长度={len(response) if response else 0}, 内容='{response}'"
                print(f"错误: {error_msg}")
                raise Exception(error_msg)
            
            # 🧹 应用统一的消息清洗处理
            cleaned_response = self._final_clean_response(response)
            print("学术探讨消息清洗完成")
            
            # 解析可能的关键词信息（恢复原始逻辑）
            keywords_analysis = self._extract_json_analysis(response)
            print(f"学术探讨关键词分析结果: {bool(keywords_analysis)}")
            if keywords_analysis:
                print(f"关键词分析包含的字段: {list(keywords_analysis.keys())}")
            
            # 根据模式决定搜索建议策略
            should_suggest_search = False
            if mode == "auto-search":
                # 在auto-search模式下，学术探讨可以主动建议搜索
                should_suggest_search = bool(keywords_analysis)
            
            # 明确导入AIMessage避免作用域问题
            from langchain_core.messages import AIMessage
            
            # 🎯 新的模式策略：auto-search先返回分析，标记后台搜索
            if mode == "auto-search":
                # auto-search模式：先完成分析阶段，标记需要后台搜索
                is_completed = True  # 分析阶段完成
                need_search = should_suggest_search
                background_search_required = should_suggest_search  # 新增标记
            else:
                # chat&plan模式：只输出分析，不自动搜索
                is_completed = True
                need_search = False
                background_search_required = False
            
            return {
                "current_step": "discussion_completed",
                "is_completed": is_completed,
                "analysis_result": keywords_analysis,
                "is_academic_query": True,
                "need_search_strategy": need_search,
                "mode": mode,
                "messages": [AIMessage(content=cleaned_response)],  # 使用清洗后的响应
                "search_suggestion": should_suggest_search,  # 是否建议搜索
                "background_search_required": background_search_required,  # 新增：是否需要后台搜索
                "query": state.get("query", ""),  # 保存原始查询供后台搜索使用
                "max_results": state.get("max_results", 40)  # 保存搜索数量
            }
            
        except Exception as e:
            error_msg = f"学术讨论失败: {str(e)}"
            print(f"错误: {error_msg}")
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
    
    def _clean_json_string(self, json_str: str) -> str:
        """
        更稳定的JSON字符串清洗，减少格式破坏风险
        - 修复尾随逗号
        - 修复引号问题
        - 保持JSON结构完整性
        """
        try:
            print(f"🧹 开始JSON清洗，原始长度: {len(json_str)}")
            
            # 保存原始JSON用于调试
            original = json_str
            cleaned = json_str.strip()
            
            # 1. 首先尝试直接解析，如果成功则无需清洗
            try:
                json.loads(cleaned)
                print("JSON格式良好，无需清洗")
                return cleaned
            except json.JSONDecodeError:
                print("JSON格式有问题，开始清洗...")
            
            # 2. 修复中文引号（最常见的问题）
            cleaned = re.sub(r'["""]', '"', cleaned)
            cleaned = re.sub(r"['']", '"', cleaned)
            
            # 3. 修复属性名缺少引号的问题（避免固定宽度后瞻问题）
            # 匹配大括号或逗号后的未引号属性名
            cleaned = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', cleaned)
            
            # 4. 修复尾随逗号（分步处理避免冲突）
            # 对象结尾的逗号: ,} -> }
            cleaned = re.sub(r',(\s*})', r'\1', cleaned)
            # 数组结尾的逗号: ,] -> ]
            cleaned = re.sub(r',(\s*\])', r'\1', cleaned)
            
            # 5. 修复多重逗号问题
            cleaned = re.sub(r',\s*,+', ',', cleaned)
            
            # 6. 尝试解析修复后的JSON
            try:
                json.loads(cleaned)
                print("🛠️ JSON清洗成功")
                return cleaned
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON清洗后仍有问题: {e}")
                
                # 7. 最后的修复尝试：移除可能的问题字符
                # 移除非打印字符但保持结构
                cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
                
                try:
                    json.loads(cleaned)
                    print("🔧 深度清洗成功")
                    return cleaned
                except json.JSONDecodeError:
                    print("❌ JSON无法修复，返回原始内容")
                    return original
            
        except Exception as e:
            print(f"JSON清洗处理失败: {e}")
            return json_str
    
    def _extract_json_analysis(self, response: str) -> Optional[Dict[str, Any]]:
        """从LLM响应中提取JSON分析结果，增强错误处理"""
        try:
            print("JSON提取开始")
            
            # 检查是否包含JSON标识符
            has_query_analysis = '"query_analysis"' in response or '"original_query"' in response
            has_core_concepts = '"core_concepts"' in response
            has_hierarchical = '"hierarchical_keywords"' in response
            print(f"JSON标识符检查: {has_query_analysis or has_core_concepts or has_hierarchical}")
            
            # 如果没有明显的JSON标识符，直接返回None
            if not (has_query_analysis or has_core_concepts or has_hierarchical):
                print("未检测到JSON标识符，跳过JSON提取")
                return None
            
            # 方法1：精确大括号匹配
            json_candidates = []
            
            # 查找所有可能的JSON块
            i = 0
            while i < len(response):
                if response[i] == '{':
                    brace_count = 0
                    start_pos = i
                    
                    # 找到匹配的右大括号
                    for j in range(i, len(response)):
                        if response[j] == '{':
                            brace_count += 1
                        elif response[j] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_candidates.append((start_pos, j + 1))
                                i = j + 1
                                break
                    else:
                        # 没找到匹配的右大括号
                        break
                else:
                    i += 1
            
            print(f"找到 {len(json_candidates)} 个JSON候选块")
            
            # 尝试解析每个候选JSON块
            for start, end in json_candidates:
                json_str = response[start:end]
                print(f"尝试解析JSON块 ({start}-{end})，长度: {len(json_str)}")
                
                try:
                    # 首先尝试直接解析
                    analysis = json.loads(json_str)
                    
                    # 验证是否包含预期的关键字段
                    if any(key in analysis for key in ['core_concepts', 'hierarchical_keywords', 'original_query']):
                        print(f"✅ 成功解析有效JSON: {len(analysis)}个字段")
                        return analysis
                except json.JSONDecodeError as e:
                    print(f"直接解析失败: {e}")
                    
                    # 尝试清洗后解析
                    try:
                        cleaned_json = self._clean_json_string(json_str)
                        analysis = json.loads(cleaned_json)
                        
                        # 验证是否包含预期的关键字段
                        if any(key in analysis for key in ['core_concepts', 'hierarchical_keywords', 'original_query']):
                            print(f"✅ 清洗后成功解析JSON: {len(analysis)}个字段")
                            return analysis
                    except json.JSONDecodeError as e:
                        print(f"清洗后解析仍失败: {e}")
                        continue
                except Exception as e:
                    print(f"解析JSON块时发生异常: {e}")
                    continue
            
            # 方法2：正则表达式备选方法（贪婪匹配）
            print("尝试正则表达式方法...")
            json_patterns = [
                r'\{[^{}]*"(?:core_concepts|hierarchical_keywords|original_query)"[^{}]*\{[^{}]*\}[^{}]*\}',  # 嵌套结构
                r'\{[^{}]*"(?:core_concepts|hierarchical_keywords|original_query)"[^{}]*\}',  # 简单结构
                r'\{[\s\S]*?"hierarchical_keywords"[\s\S]*?\}',  # 宽松匹配
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response)
                for match in matches:
                    try:
                        # 直接尝试
                        analysis = json.loads(match)
                        if any(key in analysis for key in ['core_concepts', 'hierarchical_keywords', 'original_query']):
                            print("✅ 正则表达式方法成功")
                            return analysis
                    except:
                        try:
                            # 清洗后尝试
                            cleaned = self._clean_json_string(match)
                            analysis = json.loads(cleaned)
                            if any(key in analysis for key in ['core_concepts', 'hierarchical_keywords', 'original_query']):
                                print("✅ 正则表达式+清洗方法成功")
                                return analysis
                        except:
                            continue
            
            print("❌ 所有JSON提取方法都失败")
            return None
            
        except Exception as e:
            print(f"JSON提取过程发生异常: {type(e).__name__}: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
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
            
            print("消息清洗完成")
            return final_response
                    
        except Exception as e:
            print(f"消息清洗失败: {e}")
            # 安全降级：返回基础清理版本
            return self._safe_fallback_cleaning(response)
    
    def _strip_json_content(self, response: str) -> str:
        """智能剥离JSON内容，保留用户友好的文本"""
        try:
            # 检测JSON存在
            json_indicators = ['"query_analysis"', '"core_concepts"', '"hierarchical_keywords"', '"domain"']
            has_json = any(indicator in response for indicator in json_indicators)
            
            if not has_json:
                print("未检测到JSON内容")
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
                print(f"JSON剥离完成")
                return combined if combined else after_json
            
            return response
            
        except Exception as e:
            print(f"JSON剥离失败: {e}")
            return response
    
    def _enhance_chinese_readability(self, text: str) -> str:
        """优化中文表述和可读性"""
        if not text or len(text) < 10:
            return text
            
        try:
            # 移除多余的格式标记
            cleaned = re.sub(r'```[\s\S]*?```', '', text)
            cleaned = re.sub(r'^\s*[#*\-\s]*普通对话模式[:：]?\s*', '', cleaned, flags=re.MULTILINE)
            
            # 🔧 移除模板相关的元描述语句（增强版）
            # 🎯 模板清理规则 - 针对学术探讨进行优化，减少误删
            template_patterns = [
                # 文献搜索相关的模板语句（保持原有）
                r'关键词扩展结果的JSON格式[（(][^）)]*[）)]?',
                r'按以下格式组织\s*',
                r'如上所示\s*',
                r'JSON关键词数据[（(][^）)]*[）)]?\s*',
                
                # 🎯 针对泄漏问题的精准清理（减少误删学术内容）
                r'## 后续建议\s*[\r\n]*',  # 整个"后续建议"标题块
                r'关键词识别[（(]*内部参考[）)]*\s*.*?(?=\n|$)',  # 关键词识别（内部参考）
                r'内部参考.*?(?=\n|$)',
                r'不输出到回答框.*?(?=\n|$)',
                
                # 星号清理（仅删除多余星号，不删除内容）- 更精确
                r'(?<=：)\s*\*(?=\s*$)',             # 冒号后行尾星号
                r'(?<=。)\s*\*(?=\s*$)',             # 句号后行尾星号
                r'(?<=\w)\*+(?=\s*$)',               # 词汇后的行尾星号
                
                # 清理空的标题行
                r'\n\s*\*\*\s*\*\*\s*\n',
                r'\n\s*###?\s*\n',
                
                # ⚠️ 移除过度清理的规则，保护学术讨论内容
                # 注释掉可能误删学术内容的规则：
                # r'对用户查询的直接分析回复\s*', 
                # r'个性化研究建议[（(][^）)]*[）)]?',
                # r'输出内容结构[:：]\s*',
                # r'后续建议\s*[\r\n]*.*?(?=\n\n|\n##|\n\*\*|$)',
                # r'基于以上讨论，我发现了几个值得深入研究的要点。我可以为您搜索相关的最新文献来补充和深化这个讨论吗？',
            ]
            
            # 🎯 第一步：格式修复（在删除前先修复格式）
            
            # 修复标题格式：分步处理避免冲突
            # Step 1: 处理列表项中的带冒号标题
            cleaned = re.sub(r'• ([^*\n]+)\*(?=[:：])', r'• **\1**', cleaned)  # "• 挑战与前景*：" -> "• **挑战与前景**："
            
            # Step 2: 处理编号列表的标题
            cleaned = re.sub(r'• (\d+\.\s*)([^*\n]+)\*(?=\s*$)', r'• \1**\2**', cleaned)  # "• 1. 标题*" -> "• 1. **标题**"
            
            # Step 3: 处理独立行标题
            cleaned = re.sub(r'(?<=\n)([^*\n•\s]+)\*(?=[:：])', r'**\1**', cleaned)  # "标题*：" -> "**标题**："
            
            # Step 4: 修复列表项开头星号格式问题
            cleaned = re.sub(r'• \*([^*\n]+)', r'• **\1**', cleaned)  # "• *标题" -> "• **标题**"
            cleaned = re.sub(r'(?<=:)\s*\*(?!\*)', ' ', cleaned)  # 冒号后的单个星号
            
            # 🎯 第二步：删除模板语句
            for pattern in template_patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            
            # 优化段落分隔
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
            
            # 确保emoji后有适当间距
            cleaned = re.sub(r'([🎓📊🔍💡🚀📚⚡✨])(\S)', r'\1 \2', cleaned)
            
            # 优化列表格式和智能换行
            cleaned = re.sub(r'\n\s*[-*]\s*', '\n• ', cleaned)
            
            # 🎯 智能换行处理：确保每个要点适当分行（学术探讨专用优化）
            # 在句号后添加换行（如果后面不是列表项或空行）
            cleaned = re.sub(r'([。！？])\s*([^•\n\s])', r'\1\n\n\2', cleaned)
            
            # 确保每个主要要点前有适当间距 - 保持学术探讨的良好分段
            cleaned = re.sub(r'([。])• \*\*', r'\1\n\n• **', cleaned)  # 句号后紧接着的要点前加空行
            cleaned = re.sub(r'(?<!\n\n)• \*\*', '\n\n• **', cleaned)  # 确保每个主要标题前有空行
            
            # 保持emoji和标题的正确格式（学术探讨重点）
            cleaned = re.sub(r'(🎓|📊|💡|🔍|🚀)\s*\*\*([^*]+)\*\*', r'\1 **\2**', cleaned)  # emoji + 加粗标题格式
            
            # 清理多余空行和空白字符
            cleaned = re.sub(r'^\s*\n', '', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
            
            print("中文可读性优化完成（包含模板语句清理）")
            return cleaned.strip()
            
        except Exception as e:
            print(f"中文优化失败: {e}")
            return text
    
    def _ensure_response_quality(self, processed_text: str, original_response: str) -> str:
        """确保响应质量，必要时进行补充"""
        if not processed_text or len(processed_text) < 20:
            print("处理后内容过少，尝试恢复")
            
            # 尝试从原始响应中提取有用内容
            fallback = self._extract_meaningful_content(original_response)
            if len(fallback) > len(processed_text):
                return fallback
        
        # 🎯 泄漏检测和二次清洗
        template_leakage = [
            '后续建议', '关键词识别', '内部参考', 
            '不输出到回答框', 'JSON关键词数据',
            '基于以上讨论，我发现了几个值得深入研究的要点'
        ]
        
        if any(leak in processed_text for leak in template_leakage):
            print("🔍 检测到模板内容泄漏，启动二次清洗")
            processed_text = self._deep_template_cleanup(processed_text)
            print("🧹 二次清洗完成")
        
        # 检查星号泄漏
        import re
        if re.search(r'\*\s*$', processed_text, re.MULTILINE):
            print("🔍 检测到星号泄漏，进行修复")
            processed_text = re.sub(r'\*\s*$', '', processed_text, flags=re.MULTILINE)
            print("⭐ 星号清理完成")
        
        # 检查是否包含基本的学术讨论要素
        if len(processed_text) > 50 and any(indicator in processed_text for indicator in ['🎓', '📊', '🔍', '💡']):
            print("学术讨论内容质量良好")
            return processed_text
        elif len(processed_text) > 100:  # 提高阈值，避免过度增强
            print("基础讨论内容质量可接受")
            return processed_text
        elif len(processed_text) > 30:  # 中等长度内容，检查是否需要增强
            print("内容长度适中")
            return processed_text
        else:
            print("内容质量需要增强")
            return self._generate_enhanced_discussion(processed_text, original_response)
    
    def _deep_template_cleanup(self, text: str) -> str:
        """深度清理模板内容的顽固泄漏"""
        try:
            print("🔧 开始深度模板清理")
            cleaned = text
            
            # 🎯 超级严格的模板清理规则
            deep_patterns = [
                # 各种形式的"后续建议"
                r'(?:##\s*)?后续建议[\s\S]*?(?=\n\n|\n##|\n\*\*|$)',
                r'后续建议.*?(?:\n|$)',
                
                # 各种形式的"关键词识别"
                r'关键词识别[（(]*内部参考[）)]*[\s\S]*?(?=\n\n|\n##|\n\*\*|$)',
                r'关键词识别.*?(?:\n|$)',
                r'内部参考.*?(?:\n|$)',
                
                # 完整的问题段落
                r'基于以上讨论.*?我可以为您搜索相关的最新文献.*?(?:\n|$)',
                
                # 任何包含"你可以看到"的反思段落
                r'你可以看到.*?(?:\n\n|\n##|\n\*\*|$)',
                
                # 清理各种形式的星号泄漏
                r'(?<=\w)\*+(?=\s*$)',  # 词汇后的行尾星号
                r'(?<=[:：])\s*\*+(?=\s*$)',  # 冒号后的行尾星号
                r'^\s*\*+\s*$',  # 单独一行的星号
            ]
            
            for pattern in deep_patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.IGNORECASE)
            
            # 特殊处理：移除空的段落分隔符
            cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
            cleaned = cleaned.strip()
            
            print("🔧 深度清理完成")
            return cleaned
            
        except Exception as e:
            print(f"深度清理失败: {e}")
            return text
    
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
            print(f"增强讨论生成失败: {e}")
            return base_content or "感谢您的学术问题，这是一个很有价值的研究方向。"
    
    # 已移除：不再使用的解释增强与关键词提取辅助函数
    
    # 已移除：_generate_enhanced_response（质量保障流程已足够）
    
    # 已移除：_generate_fallback_explanation（不再需要）
    
    def route_after_literature_search(self, state: PaperSearchState) -> str:
        """文献搜索节点后的路由决策（统一优化版）"""
        mode = state.get("mode", "auto-search")
        should_search = state.get("should_search", False)
        
        # 添加详细调试信息
        print(f"文献搜索后路由: 模式={mode}, 应该搜索={should_search}")
        
        if mode == "auto-search" and should_search:
            print("auto-search模式：自动进入搜索流程")
            return "search"
        elif mode == "auto-search":
            print("auto-search模式异常：缺少搜索标记")
            return "wait_decision"
        else:
            # chat&plan模式
            print("chat&plan模式：展示分析结果")
            return "wait_decision"
    
    def should_execute_search_after_discussion(self, state: PaperSearchState) -> str:
        """学术探讨节点后的路由决策 - 优化为分阶段响应"""
        mode = state.get("mode", "auto-search") 
        search_suggestion = state.get("search_suggestion", False)
        need_search = state.get("need_search_strategy", False)
        is_completed = state.get("is_completed", False)
        
        logger.info(f"🔀 [路由] 模式={mode}, 搜索建议={search_suggestion}, 需要搜索={need_search}, 已完成={is_completed}")
        
        # 🎯 新的auto-search策略：先返回分析结果，标记需要后台搜索
        if mode == "auto-search" and (search_suggestion or need_search):
            logger.info("🚀 [auto-search] 学术分析完成 → 标记后台搜索")
            return "end"  # 先结束工作流，返回分析结果
        else:
            # chat&plan模式或无需搜索的情况
            if is_completed:
                logger.info("✅ [路由] 学术探讨已完成，正常结束流程")
            else:
                logger.info("⚠️ [路由] 学术探讨未完成但无需搜索，强制完成状态")
            return "end"
    
    # 已移除：未使用的路由决策辅助函数 should_execute_search
    
    async def search_execution_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """搜索执行节点 - 调用现有多源搜索引擎，并行优化版本"""
        try:
            query = state.get("query", "")
            max_results = state.get("max_results", 20)
            analysis = state.get("analysis_result", {})
            year_from = state.get("year_from")
            year_to = state.get("year_to")
            sources = state.get("sources")
            
            print(f"🚀 开始并行执行搜索: query={query}, max_results={max_results}")
            
            # 并行任务1：构建搜索查询（CPU密集型）
            search_query_task = asyncio.create_task(
                asyncio.to_thread(self._build_search_query, query, analysis)
            )
            
            # 并行任务2：预热搜索引擎（I/O密集型）
            search_engine_task = asyncio.create_task(self._get_search_engine())
            
            # 等待两个并行任务完成
            search_query, search_engine = await asyncio.gather(
                search_query_task,
                search_engine_task,
                return_exceptions=True
            )
            
            # 检查并行任务是否有异常
            if isinstance(search_query, Exception):
                print(f"❌ 构建搜索查询失败: {search_query}")
                search_query = query  # 降级使用原始查询
            
            if isinstance(search_engine, Exception):
                print(f"❌ 搜索引擎预热失败: {search_engine}")
                raise search_engine
            
            print(f"✅ 并行任务完成 - 搜索查询: {search_query}")
            
            # 获取analysis结果用于统一布尔查询
            analysis = state.get("analysis_result", {})
            
            # MultiSourceEngine使用不同的搜索接口
            if hasattr(search_engine, 'search_parallel_with_filters'):
                # 使用新的带筛选的搜索方法，传递analysis参数
                papers = await search_engine.search_parallel_with_filters(
                    query=search_query,
                    max_results=max_results,
                    year_from=year_from,
                    year_to=year_to,
                    sources=sources,
                    analysis=analysis
                )
            elif hasattr(search_engine, 'search_parallel'):
                # 传递年限参数和analysis参数
                papers = await search_engine.search_parallel(search_query, max_results, analysis=analysis, year_from=year_from, year_to=year_to)
            else:
                # 兜底：使用基础搜索接口（传递年限参数）
                search_result = await search_engine.search_parallel(search_query, max_results, analysis=analysis, year_from=year_from, year_to=year_to)
                papers = search_result if isinstance(search_result, list) else search_result.get('papers', [])
            print(f"搜索完成，找到 {len(papers)} 篇论文")
            
            # 转换为标准格式
            formatted_results = self._format_search_results(papers)
            
            return {
                "current_step": "searched",
                "search_results": formatted_results,
                "search_keywords": self._extract_keywords_from_analysis(analysis)
            }
            
        except Exception as e:
            error_msg = f"搜索执行失败: {str(e)}"
            print(f"错误: {error_msg}")
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "search_results": []
            }
    
    def _smart_quote_term(self, term: str) -> str:
        """智能引号处理 - 识别学术术语模式"""
        if not term or not isinstance(term, str):
            return term
            
        term = term.strip()
        if not term:
            return term
            
        # 学术缩写不加引号 (2-5个大写字母)
        if re.match(r'^[A-Z]{2,5}$', term):
            return term
            
        # 化学式和数学表达式不加引号
        if re.match(r'^[A-Za-z0-9]+[0-9]+$', term) or re.match(r'^[A-Z][a-z]*[0-9]+$', term):
            return term
            
        # 单个单词不加引号
        if not ' ' in term and not '-' in term:
            return term
            
        # 包含空格或连字符的复合术语加引号
        if ' ' in term or '-' in term:
            return f'"{term}"'
            
        return term
    
    def _collect_weighted_terms(self, hierarchical: Dict[str, Any]) -> List[tuple]:
        """收集所有关键词及其权重信息"""
        weighted_terms = []
        
        for level, level_data in hierarchical.items():
            if isinstance(level_data, dict) and 'terms' in level_data and 'weight' in level_data:
                terms = level_data['terms']
                weight = level_data['weight']
                
                # 确保terms是列表
                if isinstance(terms, str):
                    terms = [terms]
                elif not isinstance(terms, list):
                    continue
                    
                # 添加每个术语及其权重
                for term in terms:
                    if term and isinstance(term, str) and term.strip():
                        weighted_terms.append((term.strip(), weight, level))
        
        # 按权重排序（降序）
        weighted_terms.sort(key=lambda x: x[1], reverse=True)
        return weighted_terms

    def _build_search_query(self, original_query: str, analysis: Optional[Dict[str, Any]]) -> str:
        """基于权重驱动的智能布尔查询构建"""
        if not analysis:
            return original_query
        
        try:
            # 🎯 优先使用LLM返回的优化布尔查询
            if analysis.get("optimized_boolean_query"):
                optimized_query = analysis["optimized_boolean_query"]
                search_strategy = analysis.get("search_strategy", "balanced")
                print(f"🎯 使用LLM优化布尔查询: {optimized_query}")
                print(f"📈 搜索策略: {search_strategy}")
                return optimized_query
            
            # 🔄 备用方案：权重驱动的动态查询构建
            search_strategy = analysis.get("search_strategy", "balanced")
            hierarchical = analysis.get("hierarchical_keywords", {})
            
            if not hierarchical:
                print("⚠️ 无分层关键词数据，使用原始查询")
                return original_query
            
            # 收集所有权重化的术语
            weighted_terms = self._collect_weighted_terms(hierarchical)
            
            if not weighted_terms:
                print("⚠️ 无有效关键词，使用原始查询")
                return original_query
            
            print(f"🔍 权重驱动构建查询，策略: {search_strategy}")
            print(f"📊 可用术语: {len(weighted_terms)}个")
            
            # 🎯 根据策略和权重动态构建查询
            if search_strategy == "precision_focused":
                # 🎯 精准策略：1核心+1灵活 → "核心术语" AND ("灵活术语1" OR "灵活术语2")
                
                # 选择1个最重要的核心术语（来自exact_terms，权重1.0）
                exact_terms = [term for term, weight, level in weighted_terms if level == "exact_terms"]
                core_terms = [term for term, weight, level in weighted_terms if level == "core_synonyms"]
                
                if exact_terms:
                    # 使用权重最高的exact_term作为核心
                    core_term = exact_terms[0]
                    core_quoted = self._smart_quote_term(core_term)
                    
                    # 从core_synonyms中选择1-2个作为灵活补充
                    if core_terms:
                        flexible_terms = core_terms[:2]  # 最多2个灵活术语
                        flexible_quoted = [self._smart_quote_term(term) for term in flexible_terms]
                        
                        if len(flexible_quoted) == 1:
                            final_query = f"{core_quoted} AND {flexible_quoted[0]}"
                        else:
                            flexible_part = " OR ".join(flexible_quoted)
                            final_query = f"{core_quoted} AND ({flexible_part})"
                        
                        print(f"🎯 精准策略: 1核心({core_term}) + {len(flexible_terms)}灵活术语")
                    else:
                        # 如果没有core_synonyms，使用另一个exact_term作为补充
                        if len(exact_terms) > 1:
                            second_term = exact_terms[1]
                            second_quoted = self._smart_quote_term(second_term)
                            final_query = f"{core_quoted} AND {second_quoted}"
                            print(f"🎯 精准策略: 2个核心术语")
                        else:
                            final_query = core_quoted
                            print(f"🎯 精准策略: 单一核心术语")
                else:
                    # 回退：使用权重最高的术语
                    if len(weighted_terms) >= 2:
                        top_two = [term for term, _, _ in weighted_terms[:2]]
                        quoted_terms = [self._smart_quote_term(term) for term in top_two]
                        final_query = f"{quoted_terms[0]} AND {quoted_terms[1]}"
                        print(f"🎯 精准策略回退: 使用前2个高权重术语")
                    else:
                        top_term = weighted_terms[0][0] if weighted_terms else "machine learning"
                        final_query = self._smart_quote_term(top_term)
                        print(f"🎯 精准策略最小回退: 单一术语")
                    
            elif search_strategy == "recall_focused":
                # 召回策略：使用权重≥0.4的所有术语，OR连接
                all_terms = [term for term, weight, level in weighted_terms if weight >= 0.4]
                all_terms = all_terms[:8]  # 防止查询过长
                
                if all_terms:
                    quoted_terms = [self._smart_quote_term(term) for term in all_terms]
                    final_query = " OR ".join(quoted_terms)
                    print(f"🔍 召回策略: 使用{len(all_terms)}个术语扩大搜索范围")
                else:
                    # 使用所有可用术语
                    all_terms = [term for term, _, _ in weighted_terms[:6]]
                    quoted_terms = [self._smart_quote_term(term) for term in all_terms]
                    final_query = " OR ".join(quoted_terms)
                    print(f"🔍 召回策略回退: 使用前{len(all_terms)}个术语")
                    
            else:  # balanced 平衡策略
                # ⚖️ 平衡策略：四层结构 → exact(内部OR) OR core AND related OR context
                
                # 按层级分组术语
                exact_terms = [term for term, weight, level in weighted_terms if level == "exact_terms"]
                core_terms = [term for term, weight, level in weighted_terms if level == "core_synonyms"]
                related_terms = [term for term, weight, level in weighted_terms if level == "related_terms"]
                context_terms = [term for term, weight, level in weighted_terms if level == "context_terms"]
                
                query_parts = []
                
                # 1. exact_terms 内部OR连接
                if exact_terms:
                    exact_quoted = [self._smart_quote_term(term) for term in exact_terms[:3]]  # 限制数量
                    if len(exact_quoted) == 1:
                        exact_part = exact_quoted[0]
                    else:
                        exact_part = f"({' OR '.join(exact_quoted)})"
                    query_parts.append(exact_part)
                    print(f"⚖️ exact层: {len(exact_quoted)}个术语")
                
                # 2. core_synonyms 作为AND必需项
                if core_terms:
                    core_quoted = [self._smart_quote_term(term) for term in core_terms[:2]]  # 限制数量
                    core_part = " AND ".join(core_quoted)
                    
                    # 3. related_terms 作为OR扩展
                    extensions = []
                    if related_terms:
                        related_quoted = [self._smart_quote_term(term) for term in related_terms[:3]]
                        related_part = " OR ".join(related_quoted)
                        extensions.append(f"({related_part})")
                        print(f"⚖️ related层: {len(related_quoted)}个术语")
                    
                    # 4. context_terms 作为OR补充
                    if context_terms:
                        context_quoted = [self._smart_quote_term(term) for term in context_terms[:2]]
                        context_part = " OR ".join(context_quoted)
                        extensions.append(f"({context_part})")
                        print(f"⚖️ context层: {len(context_quoted)}个术语")
                    
                    # 组合core + extensions
                    if extensions:
                        extension_part = " OR ".join(extensions)
                        core_and_ext = f"({core_part}) AND ({extension_part})"
                    else:
                        core_and_ext = core_part
                    
                    query_parts.append(core_and_ext)
                    print(f"⚖️ core层: {len(core_quoted)}个术语")
                
                # 最终组合：exact OR (core AND related/context)
                if len(query_parts) == 2:
                    final_query = f"{query_parts[0]} OR ({query_parts[1]})"
                elif len(query_parts) == 1:
                    final_query = query_parts[0]
                else:
                    # 回退策略：使用权重最高的术语
                    top_terms = [term for term, _, _ in weighted_terms[:4]]
                    if len(top_terms) >= 2:
                        quoted_terms = [self._smart_quote_term(term) for term in top_terms]
                        final_query = f"{quoted_terms[0]} AND ({' OR '.join(quoted_terms[1:])})"
                        print(f"⚖️ 平衡策略回退: 1核心 + {len(quoted_terms)-1}扩展")
                    else:
                        final_query = self._smart_quote_term(top_terms[0]) if top_terms else "machine learning"
                        print(f"⚖️ 平衡策略最小回退: 单一术语")
                
                print(f"⚖️ 平衡策略完成: {len(query_parts)}个部分组合")
            
            print(f"✅ 构建完成 - {search_strategy}: {final_query}")
            return final_query
            
        except Exception as e:
            print(f"❌ 查询构建失败，使用原始查询: {e}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
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
            print(f"关键词提取失败: {e}")
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
                    print(f"未知格式的论文对象 (索引 {i}): {type(paper)}")
                    continue
                
                # 数据完整性验证和清理
                paper_dict = self._validate_and_clean_paper_data(paper_dict, i)
                
                formatted_results.append(paper_dict)
                
            except Exception as e:
                print(f"错误: 论文格式化失败 (索引 {i}): {e}")
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
                    print(f"使用备用格式保存论文 {i+1}")
                except:
                    print(f"无法处理论文 {i+1}，跳过")
                    continue
        
        print(f"论文格式化完成: {len(formatted_results)}/{len(papers)} 篇成功处理")
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
            print(f"获取属性 {attr_name} 失败: {e}")
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
            print(f"论文数据验证失败 (索引 {index}): {e}")
            return paper_dict
    
    async def result_formatting_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """结果格式化节点 - 保持原有的学术分析内容，不覆盖"""
        try:
            search_results = state.get("search_results", [])
            analysis = state.get("analysis_result", {})
            keywords = state.get("search_keywords", [])
            
            print(f"保持原有学术分析内容，搜索到 {len(search_results)} 个结果")
            
            # 🔑 重要修改：保持原有的详细学术指导内容
            # 保持原有的详细分析内容，让用户看到完整的专业解读
            existing_messages = state.get("messages", [])
            if existing_messages:
                print("保持现有的详细学术分析内容")
                return {
                    "current_step": "completed",
                    "is_completed": True
                    # 🔑 关键：不设置messages字段，保持原有内容
                }
            else:
                # 备用响应（正常情况下不会到这里）
                fallback_response = "✅ 已完成学术分析和关键词扩展。请查看右侧关键词云进行进一步的文献搜索。"
                print("使用备用响应")
                # 局部导入AIMessage
                from langchain_core.messages import AIMessage
                return {
                    "current_step": "completed",  
                    "is_completed": True,
                    "messages": [AIMessage(content=fallback_response)]
                }
            
        except Exception as e:
            error_msg = f"结果格式化失败: {str(e)}"
            print(f"错误: {error_msg}")
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
            
            return {
                "keyword_cache_size": len(self._keyword_expansion_cache),
                "cache_ttl_minutes": self._cache_ttl // 60,
                "max_cache_size": self._max_cache_size,
                "total_cache_entries": len(self._keyword_expansion_cache)
            }
        except:
            return {"error": "获取缓存统计失败"}
    
    def clear_cache(self) -> bool:
        """清空所有缓存"""
        try:
            self._keyword_expansion_cache.clear()
            print("所有缓存已清空")
            return True
        except Exception as e:
            print(f"清空缓存失败: {e}")
            return False
    
    def _extract_technical_terms_from_chinese(self, query: str) -> List[str]:
        """从中文查询中提取技术术语，转换为英文学术搜索词"""
        import re
        
        # 常见的中文技术术语到英文的映射
        tech_translations = {
            "Ni基": ["nickel-based", "Ni-based"],
            "光热": ["photothermal", "solar thermal"],
            "甲烷": ["methane", "CH4"],
            "干重整": ["dry reforming", "carbon dioxide reforming"],
            "甲烷干重整": ["methane dry reforming", "CH4 dry reforming", "carbon dioxide reforming of methane"],
            "催化剂": ["catalyst", "catalysts"],
            "发展现状": ["current development", "recent advances", "state of art"],
            "研究进展": ["research progress", "recent developments"],
            "纳米": ["nano", "nanoparticle"],
            "材料": ["material", "materials"],
            "合成": ["synthesis", "preparation"],
            "表征": ["characterization"],
            "性能": ["performance", "activity"],
            "机制": ["mechanism"],
            "反应": ["reaction"],
            "活性": ["activity", "catalytic activity"]
        }
        
        extracted_terms = []
        query_lower = query.lower()
        
        # 直接匹配技术术语
        for chinese_term, english_terms in tech_translations.items():
            if chinese_term in query:
                extracted_terms.extend(english_terms)
        
        # 如果没有找到专门的技术术语，尝试分解查询
        if not extracted_terms:
            # 提取可能的化学元素符号
            chemical_elements = re.findall(r'\b[A-Z][a-z]?\b', query)
            if chemical_elements:
                extracted_terms.extend(chemical_elements)
            
            # 如果还是没有，至少提供一些通用的学术术语
            if "研究" in query or "分析" in query or "查询" in query:
                extracted_terms.extend(["research", "study", "analysis"])
        
        # 去重并返回
        unique_terms = list(dict.fromkeys(extracted_terms))  # 保持顺序去重
        
        if unique_terms:
            print(f"中文术语转换: {query} → {unique_terms}")
        else:
            # 最后的回退：使用原始查询的英文描述
            unique_terms = ["research", "study"]
            print(f"无法识别专业术语，使用通用学术词汇: {unique_terms}")
        
        return unique_terms
    
    async def search_papers(self, query: str, max_results: int = 20, thread_id: str = None, mode: str = "auto-search", force_search: bool = False, year_from: Optional[int] = None, year_to: Optional[int] = None, sources: Optional[List[str]] = None, allow_search: bool = True, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
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
            logger.warning(f"⚠️ [工作流] 注入历史失败: {e}")
        
        logger.info(f"🎯 [工作流] 启动 → 查询: {query[:40]}...")
        
        config = {"configurable": {"thread_id": thread_id}} if self.enable_memory else {}
        
        try:
            # 为LangGraph工作流添加超时控制
            import os
            workflow_timeout = float(os.getenv('ACADEMIC_SEARCH_TIMEOUT', '120.0'))
            
            final_state = await asyncio.wait_for(
                self.graph.ainvoke(initial_state, config),
                timeout=workflow_timeout
            )
            
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
            
            logger.info(f"✅ [工作流] {'完成' if result['success'] else '失败'}")
            return result
            
        except asyncio.TimeoutError:
            timeout_msg = f"学术查询超时（{workflow_timeout}秒），可能由于网络或服务器繁忙。"
            logger.warning(f"⚠️ [工作流] 执行超时: {timeout_msg}")
            
            return {
                "success": False,
                "response": "抱歉，查询超时了。请稍后重试或尝试使用更简单的关键词。",
                "error_message": timeout_msg,
                "thread_id": thread_id,
                "query": query,
                "search_results": [],
                "analysis_result": None,
                "is_academic_query": True,
                "need_search_strategy": False
            }
            
        except Exception as e:
            error_msg = f"工作流执行错误: {str(e)}"
            error_str = str(e).lower()
            
            # 检查是否是CAPTCHA相关错误
            if 'captcha' in error_str or 'blocked' in error_str:
                user_friendly_msg = "搜索服务暂时受限，请稍等片刻后重试，或尝试使用其他关键词。"
                print(f"CAPTCHA限制: {error_msg}")
            else:
                user_friendly_msg = "处理您的请求时出现错误，请稍后再试。"
                print(f"错误: {error_msg}")
                import traceback
                print(f"详细错误堆栈: {traceback.format_exc()}")
            
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

async def chat_with_search_strategy(query: str, thread_id: str = None, force_search: bool = False, max_results: int = 20, year_from: Optional[int] = None, year_to: Optional[int] = None, sources: Optional[List[str]] = None, allow_search: bool = True, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
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
    
    print("智能搜索工作流测试完成")


if __name__ == "__main__":
    asyncio.run(test_intelligent_agent())