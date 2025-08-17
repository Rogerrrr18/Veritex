"""
智能学术论文搜索工作流 - 集成Paper-god-beta2多源搜索引擎
基于LangGraph v2架构，融合专业关键词扩展与现有搜索系统
"""
import asyncio
import json
import uuid
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

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
            self.should_execute_search_after_analysis,
            {
                "search": "search_execution",
                "end": END
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
        """闲聊对话处理节点"""
        try:
            user_message = state.get("user_message", "")
            print(f"💬 闲聊对话处理: {user_message}")
            
            # 使用简化的prompt工具函数
            from prompt_utils import get_chat_conversation_prompt
            prompt = get_chat_conversation_prompt(user_message)
            
            # 调用LLM生成对话回复
            response = await self.llm.simple_chat(prompt=prompt)
            
            # 明确导入AIMessage避免作用域问题
            from langchain_core.messages import AIMessage
            
            return {
                "current_step": "completed",
                "is_completed": True,
                "analysis_result": None,
                "is_academic_query": False,
                "need_search_strategy": False,
                "messages": [AIMessage(content=response)]
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
    
    async def literature_search_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """文献搜索处理节点"""
        try:
            user_message = state.get("user_message", "")
            mode = state.get("mode", "auto-search")
            print(f"📚 文献搜索处理: {user_message} (模式: {mode})")
            
            # 使用简化的prompt工具函数
            from prompt_utils import get_literature_search_prompt
            prompt = get_literature_search_prompt(user_message, mode=mode)
            
            # 调用LLM进行关键词扩展和搜索分析
            response = await self.llm.simple_chat(prompt=prompt)
            
            # 解析LLM响应中的JSON部分（如果有）
            keywords_analysis = self._extract_json_analysis(response)
            
            # 明确导入AIMessage避免作用域问题
            from langchain_core.messages import AIMessage
            
            return {
                "current_step": "search_ready",
                "is_completed": False,  # 可能还需要执行搜索
                "analysis_result": keywords_analysis,
                "is_academic_query": True,
                "need_search_strategy": True,
                "mode": mode,
                "messages": [AIMessage(content=response)],
                "should_search": mode == "auto-search"  # 标记是否应该自动搜索
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
    
    async def academic_discussion_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """学术探讨处理节点"""
        try:
            user_message = state.get("user_message", "")
            mode = state.get("mode", "auto-search")
            print(f"🎓 学术探讨处理: {user_message} (模式: {mode})")
            
            # 使用简化的prompt工具函数
            from prompt_utils import get_academic_discussion_prompt
            prompt = get_academic_discussion_prompt(user_message, mode=mode)
            
            # 调用LLM进行学术讨论
            response = await self.llm.simple_chat(prompt=prompt)
            
            # 解析可能的关键词信息
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
                "messages": [AIMessage(content=response)],
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
    
    async def _map_intent_to_workflow(self, intent_result, user_message: str, state: PaperSearchState) -> Dict[str, Any]:
        """将新的意图分类结果映射到原有工作流格式"""
        
        if intent_result.intent == "查文献":
            # 触发完整搜索流程 - 生成搜索关键词
            print("🔍 意图：查文献 - 生成搜索关键词")
            
            # 简化的关键词生成（基于用户输入）
            search_keywords = {
                "core_concepts": [user_message.strip()],
                "hierarchical_keywords": {
                    "exact_terms": {"terms": user_message.split(), "weight": 1.0},
                    "core_synonyms": {"terms": [], "weight": 0.9},
                    "related_terms": {"terms": [], "weight": 0.5},
                    "context_terms": {"terms": [], "weight": 0.4}
                },
                "domain": "academic_research",
                "optimized_boolean_query": user_message.strip()
            }
            
            # 局部导入AIMessage
            from langchain_core.messages import AIMessage
            return {
                "current_step": "completed",
                "is_completed": True,
                "analysis_result": search_keywords,
                "is_academic_query": True,
                "need_search_strategy": True,
                "messages": [AIMessage(content=f"理解您要查找关于「{user_message}」的文献，正在为您搜索...")]
            }
        
        elif intent_result.intent == "闲聊":
            # 对话模式，不搜索
            print("💬 意图：闲聊 - 进入对话模式")
            
            # 如果LLM已经生成了回复，使用它；否则生成友好回复
            if intent_result.response:
                response_text = intent_result.response
            else:
                response_text = self._generate_friendly_response(user_message)
            
            # 局部导入AIMessage
            from langchain_core.messages import AIMessage
            return {
                "current_step": "completed",
                "is_completed": True,
                "analysis_result": None,
                "is_academic_query": False,
                "need_search_strategy": False,
                "messages": [AIMessage(content=response_text)]
            }
        
        elif intent_result.intent == "学术探讨":
            # 学术讨论，分析但不自动搜索
            print("🎓 意图：学术探讨 - 提供分析讨论")
            
            # 生成学术讨论回复
            discussion_response = await self._generate_academic_discussion(user_message)
            
            # 提供可选的搜索关键词（用户可手动触发搜索）
            optional_keywords = {
                "core_concepts": [user_message.strip()],
                "hierarchical_keywords": {
                    "exact_terms": {"terms": user_message.split(), "weight": 1.0},
                    "core_synonyms": {"terms": [], "weight": 0.9},
                    "related_terms": {"terms": [], "weight": 0.5},
                    "context_terms": {"terms": [], "weight": 0.4}
                },
                "domain": "academic_discussion"
            }
            
            # 局部导入AIMessage
            from langchain_core.messages import AIMessage
            return {
                "current_step": "completed",
                "is_completed": True,
                "analysis_result": optional_keywords,  # 提供可选关键词
                "is_academic_query": True,
                "need_search_strategy": False,  # 关键：不自动搜索
                "messages": [AIMessage(content=discussion_response)]
            }
        
        else:
            # 默认降级为闲聊
            print("⚠️ 未知意图，降级为闲聊模式")
            # 局部导入AIMessage
            from langchain_core.messages import AIMessage
            return {
                "current_step": "completed",
                "is_completed": True,
                "analysis_result": None,
                "is_academic_query": False,
                "need_search_strategy": False,
                "messages": [AIMessage(content="抱歉，我没有完全理解您的需求。您是想要搜索文献、进行学术讨论，还是有其他需要帮助的地方？")]
            }
    
    def _generate_friendly_response(self, user_message: str) -> str:
        """生成友好的对话回复"""
        message_lower = user_message.lower()
        
        if any(greeting in message_lower for greeting in ["你好", "hello", "hi"]):
            return "你好！我是学术文献搜索助手，可以帮您查找学术论文、进行学术讨论。有什么可以帮助您的吗？"
        elif any(thanks in message_lower for thanks in ["谢谢", "感谢", "thanks"]):
            return "不客气！很高兴能够帮助您。如果您需要查找文献或有学术问题想讨论，随时告诉我。"
        elif any(help_word in message_lower for help_word in ["怎么用", "如何使用", "功能"]):
            return "我可以帮您：\n1. 🔍 搜索学术文献 - 告诉我您要查找的主题\n2. 💭 学术讨论 - 提出学术问题我们一起探讨\n3. 💬 日常对话 - 随时可以聊天交流"
        else:
            return "我明白了。如果您需要搜索学术文献或想讨论学术问题，我很乐意帮助您！"
    
    async def _generate_academic_discussion(self, user_message: str) -> str:
        """生成学术讨论回复"""
        try:
            # 使用LLM生成深度学术讨论
            discussion_prompt = f"""请对以下学术问题提供深入的分析和讨论：

问题：{user_message}

请从以下角度进行分析：
1. 问题的学术背景和重要性
2. 当前研究现状和主要观点
3. 存在的挑战和争议
4. 未来发展方向

回复应该专业但易懂，体现学术深度。"""

            response = await self.llm.simple_chat(discussion_prompt)
            if response and len(response.strip()) > 50:
                return response
            else:
                return self._generate_fallback_discussion(user_message)
                
        except Exception as e:
            print(f"❌ 生成学术讨论失败: {e}")
            return self._generate_fallback_discussion(user_message)
    
    def _generate_fallback_discussion(self, user_message: str) -> str:
        """生成备用学术讨论回复"""
        return f"""关于「{user_message}」这个问题很有深度！

🎓 **学术角度分析**
这是一个值得深入探讨的学术问题，涉及多个研究层面和理论视角。

💭 **思考方向**
我们可以从理论基础、实践应用、技术发展、社会影响等多个维度来分析这个问题。

📚 **建议深入**
如果您想要查找相关的学术文献来深入了解这个问题，我可以帮您搜索最新的研究成果和权威观点。

您希望从哪个角度进一步讨论，或者需要我帮您搜索相关文献吗？"""
    
    async def _process_original_llm_response(self, ai_response: str, user_message: str) -> Dict[str, Any]:
        """处理原有LLM响应的逻辑（兼容旧版本）"""
        
        # 增强的LLM响应检查
        if not ai_response or ai_response.strip() == "":
            error_msg = "LLM分析失败，返回空响应"
            print(f"❌ {error_msg}")
            # 局部导入AIMessage
            from langchain_core.messages import AIMessage
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "is_completed": False,
                "messages": [AIMessage(content=f"抱歉，分析过程失败：{error_msg}")]
            }
        
        # 检查是否返回错误消息 - 启用降级策略
        if "抱歉，我现在无法回复" in ai_response or "请稍后再试" in ai_response:
            error_msg = "LLM API调用失败"
            print(f"❌ {error_msg}: {ai_response[:100]}...")
            
            # 降级策略：提供基础回复
            print("⚠️ LLM回复异常，启用降级策略")
            try:
                # 简单的fallback回复
                fallback_prompt = f"请简单回应用户查询：{user_message}"
                ai_response = await self.llm.simple_chat(prompt=fallback_prompt, system_prompt=None)
                
                if ai_response and "抱歉，我现在无法回复" not in ai_response:
                    print(f"✅ 降级策略成功")
                else:
                    raise Exception("降级策略失败")
            except Exception:
                # 返回基本的学术分析以保持功能性
                    return self._generate_fallback_analysis(user_message)
        
        # 尝试解析JSON分析结果
        analysis_result = self._extract_json_analysis(ai_response)
        is_academic = analysis_result is not None
        
        # 清理最终回复格式
        final_response = self._final_clean_response(ai_response)
        
        # 局部导入AIMessage
        from langchain_core.messages import AIMessage
        return {
            "current_step": "completed",
            "is_completed": True,
            "analysis_result": analysis_result,
            "is_academic_query": is_academic,
            "need_search_strategy": is_academic,
            "messages": [AIMessage(content=final_response)]
        }
    
    def _generate_fallback_analysis(self, user_message: str) -> Dict[str, Any]:
        """生成备用分析结果"""
        
        basic_analysis = {
            "core_concepts": [user_message],
            "hierarchical_keywords": {
                "exact_terms": {"terms": user_message.split(), "weight": 1.0},
                "core_synonyms": {"terms": [], "weight": 0.9},
                "related_terms": {"terms": [], "weight": 0.5},
                "context_terms": {"terms": [], "weight": 0.4}
            },
            "domain": "academic_research"
        }
        
        fallback_response = f"""基于您的查询「{user_message}」，我将为您提供基础的搜索支持。

🔍 **搜索策略**
我们将使用多个学术数据库为您搜索相关文献，包括arXiv和Semantic Scholar等权威来源。

💡 **建议**
如果需要更精确的搜索结果，您可以提供更具体的关键词或研究方向。"""
        
        # 局部导入AIMessage
        from langchain_core.messages import AIMessage
        return {
            "current_step": "completed",
            "is_completed": True,
            "analysis_result": basic_analysis,
            "is_academic_query": True,
            "need_search_strategy": True,
            "messages": [AIMessage(content=fallback_response)]
        }
    
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
    
    def _extract_user_friendly_response(self, response: str) -> str:
        """从LLM响应中提取用户友好的回复部分（保留完整回复用于后续处理）"""
        # 在这个阶段，保留完整响应，让后续的JSON分析和最终清理来处理
        return response.strip()
    
    def _final_clean_response(self, response: str) -> str:
        """最终清理响应，智能处理JSON和用户友好内容"""
        try:
            print(f"🔍 开始清理响应，原始长度: {len(response)}")
            
            # 使用与JSON提取相同的智能逻辑检查是否包含JSON
            json_end_pos = None
            if '"query_analysis"' in response or '"core_concepts"' in response:
                # 查找完整的JSON块（从第一个{到最后一个}）
                json_start = response.find('{')
                if json_start != -1:
                    brace_count = 0
                    
                    for i in range(json_start, len(response)):
                        if response[i] == '{':
                            brace_count += 1
                        elif response[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end_pos = i + 1
                                break
                    print(f"🔍 检测到JSON结构，结束位置: {json_end_pos}")
            
            if json_end_pos:
                # 学术查询：提取JSON后面的解释部分
                explanation_part = response[json_end_pos:].strip()
                
                # 清理代码块标记和多余格式
                explanation_part = re.sub(r'```[\s\S]*?```', '', explanation_part)
                explanation_part = explanation_part.strip()
                
                print(f"🔍 提取到解释部分，长度: {len(explanation_part)}")
                
                # 🔑 关键修改：大幅放宽质量检查条件
                if explanation_part and len(explanation_part) > 30:  # 从100降低到30
                    # 验证是否包含学术解释标识符（放宽要求）
                    required_sections = ['🎓', '📊', '🔍', '💡']
                    missing_sections = [section for section in required_sections if section not in explanation_part]
                    
                    print(f"🔍 质量检查 - 缺失标识符: {len(missing_sections)}/4")
                    
                    if len(missing_sections) == 0:
                        print(f"✅ 学术查询响应完整，包含所有四个部分，长度: {len(explanation_part)}")
                        return explanation_part
                    elif len(missing_sections) <= 3:  # 从2改为3，更宽松
                        print(f"✅ 学术查询响应可接受，缺失少量部分: {missing_sections}")
                        return self._enhance_incomplete_explanation(explanation_part, missing_sections)
                    else:
                        # 即使缺失很多部分，也优先使用原始内容而不是错误消息
                        print(f"⚠️ 学术查询解释不完整但仍可用，长度: {len(explanation_part)}")
                        return self._generate_enhanced_response(explanation_part)
                else:
                    # 🔑 关键修改：改进降级策略
                    print(f"⚠️ 学术查询解释内容较少，尝试优化处理")
                    if explanation_part:
                        print(f"📝 使用现有内容并增强: {explanation_part[:50]}...")
                        return self._generate_enhanced_response(explanation_part)
                    else:
                        print(f"📝 生成智能分析回复基于JSON内容")
                        return self._generate_fallback_explanation(response)
            else:
                # 普通对话：直接清理格式标记
                cleaned = response.strip()
                # 移除可能的代码块标记
                cleaned = re.sub(r'```[\s\S]*?```', '', cleaned).strip()
                # 移除提示性分支标签
                cleaned = re.sub(r'^\s*[#*\-\s]*普通对话模式[:：]?\s*', '', cleaned)
                print(f"✅ 普通对话清理完成，长度: {len(cleaned)}")
                return cleaned if cleaned else "抱歉，我无法理解您的问题，请重新表述。"
                    
        except Exception as e:
            print(f"⚠️ 最终清理失败: {e}")
            # 🔑 关键修改：即使出错也尝试返回有用的内容
            if response and len(response) > 10:
                print("📝 清理失败，返回原始内容的安全版本")
                return response.strip()[:500] + ("..." if len(response) > 500 else "")
            return "你好！我是学术搜索助手，有什么可以帮助你的吗？"
    
    def _enhance_incomplete_explanation(self, explanation: str, missing_sections: List[str]) -> str:
        """增强不完整的学术解释"""
        try:
            print(f"🔧 开始补充缺失的学术解释部分: {missing_sections}")
            enhanced = explanation
            
            # 尝试从现有内容中提取信息来生成更个性化的补充
            content_keywords = self._extract_keywords_from_content(explanation)
            
            for section in missing_sections:
                if section == '🎓':
                    if content_keywords:
                        domain_hint = content_keywords[0] if content_keywords else "学术研究"
                        enhanced += f"\n\n🎓 **专业解读**\n已完成{domain_hint}相关的专业术语分析。这一领域涉及多个重要概念，通过系统化的关键词扩展，我们能够更全面地理解研究主题的核心内容和发展脉络。"
                    else:
                        enhanced += "\n\n🎓 **专业解读**\n已为您完成专业术语分析，相关概念已在上述关键词中体现。这些术语代表了该研究领域的核心概念和前沿发展方向。"
                        
                elif section == '📊':
                    enhanced += "\n\n📊 **现状分析**\n该研究领域目前正处于快速发展阶段，国内外学者在理论创新和技术应用方面都取得了重要进展。建议关注最近3-5年的研究趋势，特别是在方法学创新和跨学科融合方面的突破。"
                    
                elif section == '🔍':
                    enhanced += "\n\n🔍 **搜索策略**\n采用了多层次关键词扩展策略，包括精确术语、核心同义词和相关概念的组合。这种方法能够确保检索结果既有高度的相关性，又具备足够的覆盖面，帮助您发现更多有价值的研究文献。"
                    
                elif section == '💡':
                    if '机理' in explanation or 'mechanism' in explanation.lower():
                        enhanced += "\n\n💡 **学术指导**\n对于机理研究，建议采用理论建模与实验验证相结合的方法。可以关注分子层面的作用机制、动力学分析以及关键影响因素的识别。推荐使用先进的分析表征技术和计算模拟方法来深入理解研究对象的本质规律。"
                    elif '应用' in explanation or 'application' in explanation.lower():
                        enhanced += "\n\n💡 **学术指导**\n在应用研究方面，建议重点关注技术的实用性和可行性。从实验室规模向工业化应用转化时，需要考虑成本效益、环境影响和技术成熟度等因素。建议查阅相关的技术标准和行业报告。"
                    else:
                        enhanced += "\n\n💡 **学术指导**\n建议采用系统性的研究方法，从基础理论出发，结合实证分析，逐步构建完整的知识体系。重点关注方法创新和实际应用价值，同时注意与现有研究的对比和差异化。"
            
            print(f"✅ 已智能补充 {len(missing_sections)} 个缺失的解释部分")
            return enhanced
            
        except Exception as e:
            print(f"⚠️ 智能补充失败，使用基础补充: {e}")
            # 回退到简单补充方式
            enhanced = explanation
            for section in missing_sections:
                if section == '🎓':
                    enhanced += "\n\n🎓 **专业解读**\n已完成专业分析，相关概念已在关键词中体现。"
                elif section == '📊':
                    enhanced += "\n\n📊 **现状分析**\n该研究领域发展活跃，值得深入关注。"
                elif section == '🔍':
                    enhanced += "\n\n🔍 **搜索策略**\n采用智能关键词扩展策略。"
                elif section == '💡':
                    enhanced += "\n\n💡 **学术指导**\n建议从基础概念入手，逐步深入研究。"
            return enhanced
    
    def _extract_keywords_from_content(self, content: str) -> List[str]:
        """从内容中提取关键词来指导补充策略"""
        try:
            if not content:
                return []
            
            # 预定义的学科领域关键词
            domain_keywords = {
                '机械工程': ['机械', '机器', '设备', '制造'],
                '化学工程': ['化学', '反应', '催化', '合成', '分离'],
                '材料科学': ['材料', '复合材料', '纳米', '薄膜', '晶体'],
                '生物医学': ['生物', '医学', '细胞', '基因', '蛋白质', '药物'],
                '计算机科学': ['算法', '计算', '软件', '数据', '网络', '人工智能'],
                '物理学': ['物理', '量子', '光学', '电磁', '热力学'],
                '环境科学': ['环境', '污染', '生态', '可持续', '绿色'],
                '经济管理': ['经济', '管理', '市场', '金融', '企业']
            }
            
            content_lower = content.lower()
            found_domains = []
            
            # 检测学科领域
            for domain, keywords in domain_keywords.items():
                if any(keyword in content_lower for keyword in keywords):
                    found_domains.append(domain)
            
            # 提取其他可能的关键概念
            import re
            # 匹配可能的专业术语（中英文）
            terms = re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}', content)
            
            # 过滤常见词汇
            common_words = {'研究', '分析', '方法', '技术', '系统', '结果', '问题', '发展', '应用', 
                          'research', 'analysis', 'method', 'system', 'result', 'development', 'application'}
            
            meaningful_terms = [term for term in terms if term not in common_words and len(term) > 1]
            
            # 合并结果
            result = found_domains + meaningful_terms[:5]  # 限制返回的关键词数量
            print(f"📝 从内容中提取到关键词: {result[:3]}...")  # 只显示前3个
            
            return result
            
        except Exception as e:
            print(f"⚠️ 关键词提取失败: {e}")
            return []
    
    def _generate_enhanced_response(self, partial_content: str) -> str:
        """基于部分内容生成增强响应"""
        try:
            print(f"🔧 开始增强部分内容，原始长度: {len(partial_content)}")
            
            # 如果内容已经相对完整，直接使用
            if len(partial_content) > 200:
                print(f"✅ 内容相对完整，直接使用")
                return partial_content
            
            # 检查是否已包含一些学术解释标识符
            sections = ['🎓', '📊', '🔍', '💡']
            existing_sections = [s for s in sections if s in partial_content]
            
            if len(existing_sections) > 0:
                print(f"✅ 部分内容包含 {len(existing_sections)} 个学术标识符，适当增强")
                
                # 为现有内容添加总结
                enhanced_content = partial_content
                
                if '🎓' not in partial_content:
                    enhanced_content += "\n\n🎓 **专业解读**\n已完成相关概念的专业分析，核心内容见上述解释。"
                    
                if '💡' not in partial_content:
                    enhanced_content += "\n\n💡 **学术指导**\n建议关注最新研究进展，结合理论基础深入探索该领域的发展趋势。"
                
                return enhanced_content
            else:
                print(f"📝 内容缺少学术标识符，生成基础增强版本")
                # 将现有内容作为专业解读的一部分
                return f"""🎓 **专业解读**
{partial_content}

📊 **现状分析**  
该研究领域目前发展活跃，相关研究不断涌现，值得深入关注。

🔍 **搜索策略**
已采用智能关键词分析，结合多层次搜索策略确保结果的相关性和完整性。

💡 **学术指导**  
建议从基础概念入手，逐步扩展到具体应用和前沿研究方向。关注顶级期刊的最新发表论文。"""
                
        except Exception as e:
            print(f"⚠️ 增强响应生成失败: {e}")
            # 即使增强失败，也返回原始内容而不是错误消息
            return partial_content if partial_content else "✅ 已完成学术分析处理。"
    
    def _generate_fallback_explanation(self, original_response: str) -> str:
        """生成备用的学术解释"""
        try:
            # 尝试从JSON中提取一些信息来生成解释
            analysis = self._extract_json_analysis(original_response)
            if analysis:
                domain = analysis.get('domain', '学术研究')
                core_concepts = analysis.get('core_concepts', [])
                concepts_text = "、".join(core_concepts[:3]) if core_concepts else "相关概念"
                
                return f"""🎓 **专业解读**
已为您分析了{concepts_text}等核心概念，这些术语在{domain}领域中具有重要意义。

📊 **现状分析**
该研究方向目前处于活跃发展阶段，相关研究不断涌现，建议关注最新进展。

🔍 **搜索策略**
采用了多层次关键词扩展方法，结合精确术语和相关概念，确保检索结果的完整性。

💡 **学术指导**
建议从基础概念开始深入学习，逐步扩展到具体应用和前沿研究方向。"""
            else:
                return "✅ 已完成学术分析和关键词扩展。请查看右侧关键词云进行进一步的文献搜索。"
        except:
            return "✅ 已完成学术分析。如需了解更多信息，请提供更详细的查询内容。"
    
    def should_execute_search_after_analysis(self, state: PaperSearchState) -> str:
        """文献搜索节点后的路由决策"""
        mode = state.get("mode", "auto-search")
        should_search = state.get("should_search", False)
        
        print(f"📋 文献搜索后路由: 模式={mode}, 应该搜索={should_search}")
        
        if mode == "auto-search" and should_search:
            print("🔍 自动搜索模式，执行搜索")
            return "search"
        else:
            print("💬 展示关键词分析，等待用户决策")
            return "end"
    
    def should_execute_search_after_discussion(self, state: PaperSearchState) -> str:
        """学术探讨节点后的路由决策"""
        mode = state.get("mode", "auto-search") 
        search_suggestion = state.get("search_suggestion", False)
        
        print(f"🎓 学术探讨后路由: 模式={mode}, 搜索建议={search_suggestion}")
        
        # 学术探讨通常不自动搜索，只在特殊情况下建议
        # 这里暂时都返回 "end"，未来可以根据需要添加更复杂的逻辑
        return "end"
    
    def should_execute_search(self, state: PaperSearchState) -> str:
        """判断是否需要执行搜索"""
        is_academic = state.get("is_academic_query", False)
        need_search = state.get("need_search_strategy", False)
        force_search = state.get("force_search", False)  # 新增强制搜索标志
        allow_search = state.get("allow_search", True)
        
        # 如果设置了强制搜索，且允许搜索，直接执行搜索（用于Search Papers按钮）
        if force_search and allow_search:
            print("🔍 强制搜索模式，执行搜索")
            return "search"
        
        # 正常模式：需要学术分析且需要搜索策略时才执行搜索，且必须允许搜索
        if allow_search and is_academic and need_search:
            print("🔍 判断为学术查询，执行搜索")
            return "search"
        else:
            print("💬 判断为学术分析或普通对话，返回分析结果")
            return "direct_reply"
    
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
        """根据分析结果构建优化的布尔搜索查询"""
        if not analysis:
            return original_query
        
        try:
            # 提取层次化关键词
            hierarchical = analysis.get("hierarchical_keywords", {})
            exact_terms = hierarchical.get("exact_terms", {}).get("terms", [])
            core_synonyms = hierarchical.get("core_synonyms", {}).get("terms", [])
            related_terms = hierarchical.get("related_terms", {}).get("terms", [])
            context_terms = hierarchical.get("context_terms", {}).get("terms", [])
            
            # 构建布尔查询组件
            query_parts = []
            
            # 1. 核心术语组：exact_terms 用 AND 连接（最高优先级，必须出现）
            if exact_terms:
                # 处理多词术语，用引号包围
                quoted_exact = [f'"{term}"' if ' ' in term else term for term in exact_terms[:3]]
                exact_group = " AND ".join(quoted_exact)
                query_parts.append(f"({exact_group})")
            
            # 2. 同义词组：core_synonyms 用 OR 连接（提高召回率）
            if core_synonyms:
                quoted_synonyms = [f'"{term}"' if ' ' in term else term for term in core_synonyms[:4]]
                synonym_group = " OR ".join(quoted_synonyms)
                query_parts.append(f"({synonym_group})")
            
            # 3. 相关词组：related_terms 用 AND 连接（提高精度）
            if related_terms:
                quoted_related = [f'"{term}"' if ' ' in term else term for term in related_terms[:3]]
                related_group = " AND ".join(quoted_related)
                query_parts.append(f"({related_group})")
            
            # 4. 上下文词组：context_terms 用 OR 连接（增加相关性）
            if context_terms:
                quoted_context = [f'"{term}"' if ' ' in term else term for term in context_terms[:2]]
                context_group = " OR ".join(quoted_context)
                query_parts.append(f"({context_group})")
            
            # 如果没有足够的关键词，回退到原始查询
            if not query_parts:
                return original_query
            
            # 组合查询：各组之间用 AND 连接
            boolean_query = " AND ".join(query_parts)
            
            print(f"🎯 构建的布尔查询: {boolean_query}")
            print(f"📊 查询组件: exact_terms={len(exact_terms)}, synonyms={len(core_synonyms)}, related={len(related_terms)}, context={len(context_terms)}")
            
            return boolean_query
            
        except Exception as e:
            print(f"⚠️ 布尔查询构建失败，使用原始查询: {e}")
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
    
    def _build_search_response(self, results: List[Dict[str, Any]], analysis: Dict[str, Any], keywords: List[str]) -> str:
        """构建搜索结果回复"""
        try:
            response_parts = []
            
            # 添加搜索概述
            if analysis and keywords:
                domain = analysis.get("domain", "未知领域")
                response_parts.append(f"🔍 **搜索领域**: {domain}")
                response_parts.append(f"🏷️ **关键词**: {', '.join(keywords[:5])}")
                response_parts.append("")
            
            # 添加结果统计
            response_parts.append(f"📚 **找到 {len(results)} 篇相关论文**：")
            response_parts.append("=" * 50)
            
            # 添加论文列表
            for i, paper in enumerate(results[:10], 1):  # 限制显示10篇
                paper_info = []
                paper_info.append(f"**{i}. {paper.get('title', '无标题')}**")
                
                # 作者信息
                authors = paper.get('authors', [])
                if authors:
                    author_str = ', '.join(authors[:3])
                    if len(authors) > 3:
                        author_str += f" 等 {len(authors)} 位作者"
                    paper_info.append(f"   👤 **作者**: {author_str}")
                
                # 期刊和年份
                journal = paper.get('journal', '')
                year = paper.get('year', '')
                if journal and year:
                    paper_info.append(f"   📖 **期刊**: {journal} ({year})")
                elif journal:
                    paper_info.append(f"   📖 **期刊**: {journal}")
                elif year:
                    paper_info.append(f"   📅 **年份**: {year}")
                
                # 引用数和相关性
                citations = paper.get('citations', 0)
                relevance = paper.get('relevance_score', 0)
                if citations > 0:
                    paper_info.append(f"   📊 **引用**: {citations} 次")
                if relevance > 0:
                    paper_info.append(f"   🎯 **相关性**: {relevance:.2f}")
                
                # 摘要预览
                abstract = paper.get('abstract', '')
                if abstract:
                    preview = abstract[:200] + "..." if len(abstract) > 200 else abstract
                    paper_info.append(f"   📝 **摘要**: {preview}")
                
                # URL
                url = paper.get('url', '')
                if url:
                    paper_info.append(f"   🔗 **链接**: {url}")
                
                response_parts.append('\n'.join(paper_info))
                response_parts.append("")  # 空行分隔
            
            # 添加搜索建议
            if len(results) < 5:
                response_parts.append("💡 **搜索建议**：")
                response_parts.append("- 尝试使用更通用的关键词")
                response_parts.append("- 考虑相关的技术术语")
                response_parts.append("- 扩大时间范围搜索")
            
            return '\n'.join(response_parts)
            
        except Exception as e:
            print(f"❌ 构建搜索回复失败: {e}")
            return f"搜索完成，找到 {len(results)} 篇论文，但格式化过程出现问题。"
    
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
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "response": "处理您的请求时出现错误，请稍后再试。",
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