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
        self._cache_ttl = 1800  # 缓存30分钟
        self._max_cache_size = 100  # 最大缓存条目数
        self.enable_memory = enable_memory
        # 使用统一LLM接口
        self.llm = get_llm_for_langgraph()
        
        # 使用优化的LLM意图分类器
        self.intent_classifier = get_intent_classifier()
        print("使用优化的LLM意图分类器")
        
        self.checkpointer = MemorySaver() if enable_memory else None
        self.graph = self._build_graph()
        
        # 延迟加载搜索引擎（避免循环依赖）
        self._search_engine = None
        
        print("智能缓存系统已启用")
    
    async def _get_search_engine(self):
        """获取搜索引擎实例（延迟加载）- 避免循环依赖"""
        if self._search_engine is None:
            try:
                # 使用真实的MultiSourceEngine，删除模拟引擎依赖
                from multi_source_engine import MultiSourceEngine
                self._search_engine = MultiSourceEngine()
                print("多源搜索引擎实例化成功")
            except Exception as e:
                print(f"搜索引擎实例化失败: {e}")
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
            
            print(f"开始分析用户请求: {user_message}")
            
            # 使用Embedding + LLM精排分类器
            intent_result = await self.intent_classifier.classify_intent(user_message)
            print(f"意图分类结果: {intent_result.intent} (置信度: {intent_result.confidence:.3f})")
            
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
            print(f"错误: {error_msg}")
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
            print("未找到意图分析结果，默认进入对话模式")
            return "chat_conversation"
        
        intent = intent_result.get("intent", "闲聊")
        print(f"路由决策：意图 '{intent}' → 对应处理节点")
        
        if intent == "闲聊":
            return "chat_conversation"
        elif intent == "查文献":
            return "literature_search"
        elif intent == "学术探讨":
            return "academic_discussion"
        else:
            print(f"未知意图 '{intent}'，默认进入对话模式")
            return "chat_conversation"
    
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
            
            # 调用LLM生成对话回复（设置较短超时）
            response = await self.llm.simple_chat(prompt=prompt, timeout=45.0)
            
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
            
            # 调用LLM进行关键词扩展和搜索分析
            response = await self.llm.simple_chat(prompt=prompt, timeout=60.0)
            
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
            
            # 调用LLM进行学术讨论（增加超时时间）
            print("开始LLM学术讨论分析")
            import time
            start_time = time.time()
            
            response = await self.llm.simple_chat(prompt=prompt, timeout=60.0)  # 增加到60秒
            end_time = time.time()
            print(f"LLM调用完成，耗时: {end_time - start_time:.2f}秒")
            
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
            
            # 根据模式决定搜索建议策略
            should_suggest_search = False
            if mode == "auto-search":
                # 在auto-search模式下，学术探讨可以主动建议搜索
                should_suggest_search = bool(keywords_analysis)
            
            # 明确导入AIMessage避免作用域问题
            from langchain_core.messages import AIMessage
            
            # 根据模式决定是否继续搜索流程
            if mode == "auto-search":
                # auto-search模式：输出深度分析 + 自动继续文献检索
                is_completed = False
                need_search = should_suggest_search
            else:
                # chat&plan模式：只输出分析，不自动搜索
                is_completed = True
                need_search = False
            
            return {
                "current_step": "discussion_completed",
                "is_completed": is_completed,
                "analysis_result": keywords_analysis,
                "is_academic_query": True,
                "need_search_strategy": need_search,
                "mode": mode,
                "messages": [AIMessage(content=cleaned_response)],  # 使用清洗后的响应
                "search_suggestion": should_suggest_search  # 是否建议搜索
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
        清洗JSON字符串，修复常见的LLM生成格式问题
        - 移除尾随逗号
        - 修复引号问题
        - 处理换行和空格
        """
        try:
            print(f"🧹 开始JSON清洗，原始长度: {len(json_str)}")
            
            # 保存原始JSON用于调试
            original = json_str
            
            # 1. 基础清理：移除多余空白但保持结构
            cleaned = re.sub(r'\n\s*\n', '\n', json_str)
            cleaned = re.sub(r'^\s+', '', cleaned, flags=re.MULTILINE)
            
            # 2. 修复最常见问题：尾随逗号
            # 对象中的尾随逗号: },} -> }}
            cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
            
            # 数组中的尾随逗号: ,] -> ]
            cleaned = re.sub(r',(\s*\])', r'\1', cleaned)
            
            # 对象属性后的尾随逗号: ,"key" -> "key" 或 ,} -> }
            cleaned = re.sub(r',(\s*})', r'\1', cleaned)
            
            # 3. 修复引号问题（中文引号转换）
            cleaned = re.sub(r'["""]', '"', cleaned)
            cleaned = re.sub(r"['']", '"', cleaned)
            
            # 4. 确保属性名都有引号
            cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)
            
            # 5. 修复多重逗号问题
            cleaned = re.sub(r',\s*,', ',', cleaned)
            
            # 6. 处理数组中的逗号问题
            # 修复 ["item1", "item2",] 这种情况
            cleaned = re.sub(r',(\s*\])', r'\1', cleaned)
            
            # 7. 最后检查：移除对象结尾的多余逗号
            # {..., } -> {...}
            cleaned = re.sub(r',(\s*})(?!\s*[,\]\}])', r'\1', cleaned)
            
            if cleaned != original:
                print(f"🛠️ JSON已清洗，修复了格式问题")
                # 省略详细预览
            else:
                print("JSON格式良好")
            
            return cleaned
            
        except Exception as e:
            print(f"JSON清洗失败: {e}")
            return json_str
    
    def _extract_json_analysis(self, response: str) -> Optional[Dict[str, Any]]:
        """从LLM响应中提取JSON分析结果"""
        try:
            print("JSON提取开始")
            
            # 检查是否包含JSON标识符
            has_query_analysis = '"query_analysis"' in response
            has_core_concepts = '"core_concepts"' in response
            print(f"JSON标识符检查: {has_query_analysis or has_core_concepts}")
            
            # 使用更智能的JSON提取方法
            if has_query_analysis or has_core_concepts:
                # 查找完整的JSON块（从第一个{到最后一个}）
                json_start = response.find('{')
                print(f"JSON开始位置: {json_start}")
                
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
                    
                    print(f"JSON结束位置: {json_end}")
                    
                    if brace_count == 0:  # 找到完整的JSON
                        json_str = response[json_start:json_end]
                        print(f"提取到完整JSON，长度: {len(json_str)}")
                        
                        # 🛠️ JSON清洗 - 修复常见格式问题
                        cleaned_json = self._clean_json_string(json_str)
                        
                        analysis = json.loads(cleaned_json)
                        print(f"成功解析JSON结果: {len(analysis)}个字段")
                        return analysis
                    else:
                        print("JSON结构不完整，尝试备选方法")
                        # 尝试找到最大的有效JSON块
                        for end_pos in range(len(response) - 1, json_start, -1):
                            if response[end_pos] == '}':
                                try_json = response[json_start:end_pos + 1]
                                try:
                                    analysis = json.loads(try_json)
                                    print("备选方法成功解析JSON")
                                    return analysis
                                except:
                                    continue
                        print("备选方法也失败")
                        return None
            
            # 原有的JSON查找逻辑作为备选
            print("使用正则表达式备选方法")
            json_match = re.search(r'\{[\s\S]*?\}', response)
            if json_match:
                json_str = json_match.group()
                print(f"正则表达式找到JSON")
                
                # 🛠️ JSON清洗 - 修复常见格式问题
                cleaned_json = self._clean_json_string(json_str)
                
                analysis = json.loads(cleaned_json)
                print("备选方法成功提取JSON结果")
                return analysis
            else:
                print("响应中未包含JSON分析")
                return None
        except json.JSONDecodeError as je:
            print(f"JSON解析错误: {je}")
            return None
        except Exception as e:
            print(f"JSON提取失败: {type(e).__name__}: {e}")
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
            template_patterns = [
                # 文献搜索相关的模板语句
                r'关键词扩展结果的JSON格式[（(][^）)]*[）)]?',
                r'对用户查询的直接分析回复\s*',
                r'个性化研究建议[（(][^）)]*[）)]?',
                r'按以下格式组织\s*',
                r'如上所示\s*',
                r'输出内容结构[:：]\s*',
                r'\d+\.\s*\*\*[^*]*\*\*[（(][^）)]*[）)]?\s*',
                r'JSON关键词数据[（(][^）)]*[）)]?\s*',
                
                # 🎯 针对泄漏问题的精准清理
                r'## 后续建议\s*[\r\n]*',  # 整个"后续建议"标题块
                r'后续建议\s*[\r\n]*.*?(?=\n\n|\n##|\n\*\*|$)',  # 后续建议内容块
                r'关键词识别[（(]*内部参考[）)]*\s*.*?(?=\n|$)',  # 关键词识别（内部参考）
                r'关键词识别\s*.*?(?=\n|$)',  # 普通关键词识别
                r'内部参考.*?(?=\n|$)',
                r'不输出到回答框.*?(?=\n|$)',
                
                # 星号清理（仅删除多余星号，不删除内容）
                r'(?<=：)\s*\*(?=\s*$)',             # 冒号后行尾星号
                r'(?<=。)\s*\*(?=\s*$)',             # 句号后行尾星号
                r'(?<=\w)\*+(?=\s*$)',               # 词汇后的行尾星号
                
                # 特殊的模板语句
                r'基于以上讨论，我发现了几个值得深入研究的要点。我可以为您搜索相关的最新文献来补充和深化这个讨论吗？',
                
                # 清理空的标题行
                r'\n\s*\*\*\s*\*\*\s*\n',
                r'\n\s*###?\s*\n',
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
            
            # 🎯 智能换行处理：确保每个要点适当分行
            # 在句号后添加换行（如果后面不是列表项或空行）
            cleaned = re.sub(r'([。！？])\s*([^•\n\s])', r'\1\n\n\2', cleaned)
            
            # 确保每个主要要点前有适当间距
            cleaned = re.sub(r'([。])• \*\*', r'\1\n\n• **', cleaned)  # 句号后紧接着的要点前加空行
            cleaned = re.sub(r'(?<!\n\n)• \*\*', '\n\n• **', cleaned)  # 确保每个主要标题前有空行
            
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
        """学术探讨节点后的路由决策"""
        mode = state.get("mode", "auto-search") 
        search_suggestion = state.get("search_suggestion", False)
        need_search = state.get("need_search_strategy", False)
        
        print(f"学术探讨后路由: 模式={mode}, 搜索建议={search_suggestion}, 需要搜索={need_search}")
        
        # 在auto-search模式下，如果有搜索建议则继续搜索流程
        if mode == "auto-search" and (search_suggestion or need_search):
            print("auto-search模式：学术探讨后继续搜索")
            return "search"
        else:
            print("学术探讨完成，结束流程")
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
            
            print(f"开始执行搜索: query={query}, max_results={max_results}")
            
            # 构建搜索查询
            search_query = self._build_search_query(query, analysis)
            print(f"构建的搜索查询: {search_query}")
            
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
    
    def _build_search_query(self, original_query: str, analysis: Optional[Dict[str, Any]]) -> str:
        """使用LLM返回的优化布尔查询和搜索策略"""
        if not analysis:
            return original_query
        
        try:
            # 优先使用LLM返回的优化布尔查询
            if analysis.get("optimized_boolean_query"):
                optimized_query = analysis["optimized_boolean_query"]
                search_strategy = analysis.get("search_strategy", "balanced")
                print(f"🎯 使用LLM优化布尔查询: {optimized_query}")
                print(f"📈 搜索策略: {search_strategy}")
                return optimized_query
            
            # 备用方案：如果LLM没有返回布尔查询，则基于search_strategy构建查询
            search_strategy = analysis.get("search_strategy", "balanced")
            hierarchical = analysis.get("hierarchical_keywords", {})
            exact_terms = hierarchical.get("exact_terms", {}).get("terms", [])
            core_synonyms = hierarchical.get("core_synonyms", {}).get("terms", [])
            related_terms = hierarchical.get("related_terms", {}).get("terms", [])
            context_terms = hierarchical.get("context_terms", {}).get("terms", [])
            
            print(f"⚠️ LLM未返回布尔查询，基于策略构建: {search_strategy}")
            
            # 根据搜索策略构建查询
            if search_strategy == "precision_focused":
                # 精准策略：使用AND连接核心术语
                all_terms = []
                all_terms.extend(exact_terms[:2])
                all_terms.extend(core_synonyms[:1])
                
                if all_terms:
                    quoted_terms = [f'"{term}"' if ' ' in term else term for term in all_terms]
                    final_query = " AND ".join(quoted_terms)
                else:
                    final_query = original_query
                    
            elif search_strategy == "recall_focused":
                # 召回策略：使用OR连接所有相关术语
                all_terms = []
                all_terms.extend(exact_terms[:2])
                all_terms.extend(core_synonyms[:3])
                all_terms.extend(related_terms[:2])
                
                if all_terms:
                    quoted_terms = [f'"{term}"' if ' ' in term else term for term in all_terms]
                    final_query = " OR ".join(quoted_terms)
                else:
                    final_query = original_query
                    
            else:  # balanced 平衡策略
                # 平衡策略：核心术语AND连接，相关术语OR扩展
                core_terms = []
                core_terms.extend(exact_terms[:2])
                core_terms.extend(core_synonyms[:1])
                
                if core_terms:
                    quoted_core = [f'"{term}"' if ' ' in term else term for term in core_terms]
                    core_query = " AND ".join(quoted_core)
                    
                    # 添加可选的相关术语
                    optional_terms = related_terms[:2] + context_terms[:1]
                    if optional_terms:
                        quoted_optional = [f'"{term}"' if ' ' in term else term for term in optional_terms]
                        optional_query = " OR ".join(quoted_optional)
                        final_query = f"({core_query}) OR ({optional_query})"
                    else:
                        final_query = core_query
                else:
                    final_query = original_query
            
            print(f"构建的{search_strategy}查询: {final_query}")
            return final_query
            
        except Exception as e:
            print(f"查询构建失败，使用原始查询: {e}")
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
            
            # 🔑 重要修改：不覆盖intent_analysis_node生成的详细学术指导
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
            print(f"注入历史失败: {e}")
        
        print(f"启动智能学术搜索工作流 - 查询: {query}")
        
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
            
            print(f"工作流完成: {'成功' if result['success'] else '失败'}")
            return result
            
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
    
    print("智能搜索工作流测试完成")


if __name__ == "__main__":
    asyncio.run(test_intelligent_agent())