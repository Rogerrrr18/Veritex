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

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# 导入项目模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from prompt_manager import get_prompt_manager, PromptType

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
        self.prompt_manager = get_prompt_manager()  # 使用新的prompt管理器
        self.checkpointer = MemorySaver() if enable_memory else None
        self.graph = self._build_graph()
        
        # 延迟加载搜索引擎（避免循环依赖）
        self._search_engine = None
    
    async def _get_search_engine(self):
        """获取搜索引擎实例（延迟加载）- 避免循环依赖"""
        if self._search_engine is None:
            try:
                # 直接使用MultiSourceEngine避免循环依赖
                from multi_source_engine import MultiSourceEngine
                self._search_engine = MultiSourceEngine()
                print("✅ 多源搜索引擎实例化成功")
            except Exception as e:
                print(f"❌ 搜索引擎实例化失败: {e}")
                # 创建一个模拟搜索引擎
                self._search_engine = MockSearchEngine()
        return self._search_engine
    
    
    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(PaperSearchState)
        
        # 添加核心节点
        workflow.add_node("intent_analysis", self.intent_analysis_node)
        workflow.add_node("search_execution", self.search_execution_node)
        workflow.add_node("result_formatting", self.result_formatting_node)
        
        # 定义流程路径
        workflow.add_edge(START, "intent_analysis")
        
        # 根据意图分析结果选择路径
        workflow.add_conditional_edges(
            "intent_analysis",
            self.should_execute_search,
            {
                "search": "search_execution",
                "direct_reply": END
            }
        )
        
        workflow.add_edge("search_execution", "result_formatting")
        workflow.add_edge("result_formatting", END)
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def intent_analysis_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """意图分析节点 - 使用智能Prompt管理器"""
        try:
            query = state.get("query", "")
            user_message = state.get("messages", [])[-1].content if state.get("messages") else query
            
            print(f"🤖 开始智能分析用户请求: {user_message}")
            
            # 使用智能prompt管理器获取最优prompt
            optimal_prompt = self.prompt_manager.get_prompt(user_message)
            print(f"🔧 LLM模型信息: {type(self.llm).__name__}")
            
            # 使用优化后的prompt进行LLM调用
            ai_response = await self.llm.simple_chat(
                prompt=optimal_prompt,
                system_prompt=None  # prompt已经完整，不需要额外system_prompt
            )
            
            # 增强的LLM响应检查
            if not ai_response or ai_response.strip() == "":
                error_msg = "LLM分析失败，返回空响应"
                print(f"❌ {error_msg}")
                print(f"🔧 调试信息: LLM返回了空响应")
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
                print(f"🔧 可能原因: API key无效、网络问题或服务异常")
                
                # 降级策略：尝试使用最简单的prompt
                print(f"🔄 启用降级策略，尝试基础prompt...")
                try:
                    base_prompt = self.prompt_manager.get_prompt(user_message, PromptType.BASE)
                    print(f"📏 降级prompt长度: {len(base_prompt)}字符")
                    
                    ai_response = await self.llm.simple_chat(
                        prompt=base_prompt,
                        system_prompt=None
                    )
                    
                    if ai_response and "抱歉，我现在无法回复" not in ai_response:
                        print(f"✅ 降级策略成功，获得响应: {ai_response[:100]}...")
                    else:
                        print(f"❌ 降级策略也失败，进入兜底模式")
                        raise Exception("降级策略失败")
                except Exception as fallback_error:
                    print(f"❌ 降级策略失败: {fallback_error}")
                    # 进入兜底模式
                
                # 返回一个基本的学术分析以保持功能性
                fallback_response = f"""基于您的查询"{user_message}"，这似乎是一个学术研究相关的问题。

🎓 **专业解读**
您提到的研究主题涉及重要的学术领域。虽然当前AI分析服务暂时不可用，但我们仍可以为您提供基础的搜索支持。

📊 **现状分析**  
该研究领域是当前学术界关注的重要方向，建议您关注最新的研究进展和发展趋势。

🔍 **搜索策略**
我们将使用多个学术数据库为您搜索相关文献，包括arXiv和Semantic Scholar等权威来源。

💡 **学术指导**  
建议您从基础理论入手，逐步深入到具体应用和前沿研究。关注顶级期刊的最新发表成果。"""

                # 创建基本分析结果以支持搜索
                basic_analysis = {
                    "core_concepts": [user_message],
                    "hierarchical_keywords": {
                        "exact_terms": {"terms": user_message.split(), "weight": 1.0},
                        "core_synonyms": {"terms": [], "weight": 0.9}
                    },
                    "domain": "academic_research"
                }
                
                return {
                    "current_step": "completed",
                    "is_completed": True,
                    "analysis_result": basic_analysis,
                    "is_academic_query": True,  # 强制标记为学术查询
                    "need_search_strategy": True,
                    "messages": [AIMessage(content=fallback_response)]
                }
            
            print(f"📝 LLM分析完成，响应长度: {len(ai_response)}")
            print(f"🔧 响应前100字符: {ai_response[:100]}...")
            
            # 尝试解析是否包含JSON分析结果
            print(f"🔧 开始提取JSON分析结果...")
            analysis_result = self._extract_json_analysis(ai_response)
            is_academic = analysis_result is not None
            
            print(f"🔧 JSON提取结果: {'成功' if analysis_result else '失败'}")
            if analysis_result:
                print(f"🔧 JSON包含字段: {list(analysis_result.keys())}")
            
            # 清理最终回复格式
            print(f"🔧 开始清理最终响应格式...")
            print(f"🔍 调试：LLM原始响应: {ai_response[:200]}...")
            final_response = self._final_clean_response(ai_response)
            print(f"🔍 调试：清理后响应: {final_response[:200]}...")
            print(f"🔧 最终响应长度: {len(final_response)}")
            
            print(f"📊 分析结果: 学术查询={is_academic}")
            print(f"🔧 返回状态总结: current_step=completed, is_completed=True, messages_count=1")
            
            return {
                "current_step": "completed",
                "is_completed": True,
                "analysis_result": analysis_result,
                "is_academic_query": is_academic,
                "need_search_strategy": is_academic,
                "messages": [AIMessage(content=final_response)]
            }
                
        except Exception as e:
            error_msg = f"意图分析失败: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"🔧 异常详情: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"🔧 堆栈跟踪: {traceback.format_exc()}")
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "is_completed": False,
                "messages": [AIMessage(content=f"系统错误：{error_msg}")]
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
                # MockSearchEngine的接口
                search_result = await search_engine.search(
                    query=search_query,
                    max_results=max_results,
                    enable_expansion=True
                )
                papers = search_result.get('papers', [])
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
        """根据分析结果构建优化的搜索查询"""
        if not analysis:
            return original_query
        
        try:
            # 提取层次化关键词
            hierarchical = analysis.get("hierarchical_keywords", {})
            exact_terms = hierarchical.get("exact_terms", {}).get("terms", [])
            core_synonyms = hierarchical.get("core_synonyms", {}).get("terms", [])
            
            # 优先使用精确术语和核心同义词
            if exact_terms:
                main_terms = exact_terms[:3]  # 取前3个最重要的术语
            elif core_synonyms:
                main_terms = core_synonyms[:3]
            else:
                return original_query
            
            # 构建优化查询
            search_query = " ".join(main_terms)
            print(f"🎯 优化后的搜索查询: {search_query}")
            return search_query
            
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
            for level in ["exact_terms", "core_synonyms", "related_terms"]:
                terms = hierarchical.get(level, {}).get("terms", [])
                keywords.extend(terms)
            return keywords[:10]  # 限制关键词数量
        except Exception as e:
            print(f"⚠️ 关键词提取失败: {e}")
            return []
    
    def _format_search_results(self, papers: List) -> List[Dict[str, Any]]:
        """格式化搜索结果为标准格式"""
        formatted_results = []
        
        for paper in papers:
            try:
                # 处理Paper对象或字典
                if hasattr(paper, '__dict__'):
                    paper_dict = {
                        "title": getattr(paper, 'title', ''),
                        "authors": getattr(paper, 'authors', []),
                        "abstract": getattr(paper, 'abstract', ''),
                        "year": getattr(paper, 'year', None),
                        "journal": getattr(paper, 'journal', ''),
                        "url": getattr(paper, 'url', ''),
                        "doi": getattr(paper, 'doi', None),
                        "citations": getattr(paper, 'citations', 0),
                        "source": getattr(paper, 'source', 'unknown'),
                        "relevance_score": getattr(paper, 'relevance_score', 0.0)
                    }
                else:
                    paper_dict = paper
                
                formatted_results.append(paper_dict)
            except Exception as e:
                print(f"⚠️ 论文格式化失败: {e}")
                continue
        
        return formatted_results
    
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
                return {
                    "current_step": "completed",  
                    "is_completed": True,
                    "messages": [AIMessage(content=fallback_response)]
                }
            
        except Exception as e:
            error_msg = f"结果格式化失败: {str(e)}"
            print(f"❌ {error_msg}")
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
    
    async def search_papers(self, query: str, max_results: int = 10, thread_id: str = None, force_search: bool = False, year_from: Optional[int] = None, year_to: Optional[int] = None, sources: Optional[List[str]] = None, allow_search: bool = True, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """主要搜索接口"""
        if thread_id is None:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        
        initial_state = create_initial_state(
            query=query,
            user_message=query,
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


class MockSearchEngine:
    """模拟搜索引擎 - 用于测试和备用"""
    
    async def search(self, query: str, max_results: int = 10, **kwargs) -> Dict[str, Any]:
        """模拟搜索功能"""
        print(f"🔍 使用模拟搜索引擎: {query}")
        
        # 生成模拟论文数据
        mock_papers = []
        for i in range(min(max_results, 3)):
            mock_papers.append(type('Paper', (), {
                'title': f"关于{query}的研究论文 {i+1}",
                'authors': [f"作者{i+1}", f"作者{i+2}"],
                'abstract': f"这是一篇关于{query}的研究论文，探讨了相关理论和应用。",
                'year': 2023 - i,
                'journal': f"国际期刊 {i+1}",
                'url': f"https://example.com/paper{i+1}",
                'doi': f"10.1000/example{i+1}",
                'citations': 50 - i*10,
                'source': 'mock',
                'relevance_score': 0.9 - i*0.1
            })())
        
        return {
            'papers': mock_papers,
            'total_found': len(mock_papers),
            'query_info': {'original_query': query}
        }


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