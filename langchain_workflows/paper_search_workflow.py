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
        self.system_prompt = self._load_system_prompt()
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
    
    def _load_system_prompt(self) -> str:
        """加载专业学术分析系统提示词"""
        try:
            # 优先使用增强版prompt
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "prompts", 
                "enhanced_system_prompt.txt"
            )
            with open(prompt_path, 'r', encoding='utf-8') as f:
                original_prompt = f.read().strip()
                print(f"📄 成功加载增强版学术分析提示词，长度: {len(original_prompt)}")
                return original_prompt
        except Exception as e:
            print(f"❌ 无法加载增强版提示词，尝试原版: {e}")
            # 回退到原版prompt
            try:
                prompt_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), 
                    "prompts", 
                    "refined_system_prompt.txt"
                )
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    original_prompt = f.read().strip()
                    print(f"📄 回退到原版学术分析提示词，长度: {len(original_prompt)}")
                    return original_prompt
            except Exception as e2:
                print(f"❌ 无法加载任何版本的学术分析提示词: {e2}")
                return """你是专业的学术检索分析专家。请分析用户查询，判断是否为学术需求，并提供专业的关键词扩展分析。始终用中文回答。"""
    
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
        """意图分析节点 - 使用专业学术分析Prompt"""
        try:
            query = state.get("query", "")
            user_message = state.get("messages", [])[-1].content if state.get("messages") else query
            
            print(f"🤖 开始智能分析用户请求: {user_message}")
            
            # 直接使用系统提示词和用户输入
            ai_response = await self.llm.simple_chat(
                prompt=user_message,
                system_prompt=self.system_prompt
            )
            
            if not ai_response:
                error_msg = "LLM分析失败，请稍后再试"
                print(f"❌ {error_msg}")
                return {
                    "error_message": error_msg,
                    "current_step": "failed",
                    "is_completed": False,
                    "messages": [AIMessage(content=f"抱歉，分析过程失败：{error_msg}")]
                }
            
            print(f"📝 LLM分析完成，响应长度: {len(ai_response)}")
            
            # 尝试解析是否包含JSON分析结果
            analysis_result = self._extract_json_analysis(ai_response)
            is_academic = analysis_result is not None
            
            # 清理最终回复格式
            print(f"🔍 调试：LLM原始响应: {ai_response[:200]}...")
            final_response = self._final_clean_response(ai_response)
            print(f"🔍 调试：清理后响应: {final_response[:200]}...")
            
            print(f"📊 分析结果: 学术查询={is_academic}")
            
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
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "is_completed": False,
                "messages": [AIMessage(content=f"系统错误：{error_msg}")]
            }
    
    def _extract_json_analysis(self, response: str) -> Optional[Dict[str, Any]]:
        """从LLM响应中提取JSON分析结果"""
        try:
            # 使用更智能的JSON提取方法
            if '"query_analysis"' in response or '"core_concepts"' in response:
                # 查找完整的JSON块（从第一个{到最后一个}）
                json_start = response.find('{')
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
                    
                    if brace_count == 0:  # 找到完整的JSON
                        json_str = response[json_start:json_end]
                        print(f"📝 提取到完整JSON，长度: {len(json_str)}")
                        analysis = json.loads(json_str)
                        print(f"✅ 成功解析JSON分析结果")
                        return analysis
                    else:
                        print(f"⚠️ JSON结构不完整，括号不匹配")
                        return None
            
            # 原有的JSON查找逻辑作为备选
            json_match = re.search(r'\{[\s\S]*?\}', response)
            if json_match:
                json_str = json_match.group()
                analysis = json.loads(json_str)
                print(f"✅ 成功提取JSON分析结果")
                return analysis
            else:
                print("ℹ️ 响应中未包含JSON分析（可能是普通对话）")
                return None
        except Exception as e:
            print(f"⚠️ JSON解析失败: {e}")
            print(f"⚠️ 响应内容前200字符: {response[:200]}")
            return None
    
    def _extract_user_friendly_response(self, response: str) -> str:
        """从LLM响应中提取用户友好的回复部分（保留完整回复用于后续处理）"""
        # 在这个阶段，保留完整响应，让后续的JSON分析和最终清理来处理
        return response.strip()
    
    def _final_clean_response(self, response: str) -> str:
        """最终清理响应，智能处理JSON和用户友好内容"""
        try:
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
            
            if json_end_pos:
                # 学术查询：提取JSON后面的解释部分
                explanation_part = response[json_end_pos:].strip()
                
                # 清理代码块标记和多余格式
                explanation_part = re.sub(r'```[\s\S]*?```', '', explanation_part)
                explanation_part = explanation_part.strip()
                
                # 检查解释内容的质量和长度
                if explanation_part and len(explanation_part) > 100:
                    # 验证是否包含四个必要部分的标识符
                    required_sections = ['🎓', '📊', '🔍', '💡']
                    missing_sections = [section for section in required_sections if section not in explanation_part]
                    
                    if len(missing_sections) == 0:
                        print(f"✅ 学术查询响应完整，包含所有四个部分，长度: {len(explanation_part)}")
                        return explanation_part
                    else:
                        print(f"⚠️ 学术查询解释缺少部分: {missing_sections}")
                        # 如果缺少的部分很少，尝试补充
                        if len(missing_sections) <= 2:
                            return self._enhance_incomplete_explanation(explanation_part, missing_sections)
                        else:
                            print("⚠️ 学术查询解释不完整，使用原始响应")
                            return explanation_part if explanation_part else response.strip()
                else:
                    print("⚠️ 学术查询解释内容不足，使用原始JSON后内容")
                    return explanation_part if explanation_part else "抱歉，未能生成完整的学术分析。"
            else:
                # 普通对话：直接清理格式标记
                cleaned = response.strip()
                # 移除可能的代码块标记
                cleaned = re.sub(r'```[\s\S]*?```', '', cleaned).strip()
                print(f"✅ 普通对话清理完成，长度: {len(cleaned)}")
                return cleaned if cleaned else "抱歉，我无法理解您的问题，请重新表述。"
                    
        except Exception as e:
            print(f"⚠️ 最终清理失败: {e}")
            return "你好！有什么可以帮助你的吗？"
    
    def _enhance_incomplete_explanation(self, explanation: str, missing_sections: List[str]) -> str:
        """增强不完整的学术解释"""
        enhanced = explanation
        
        for section in missing_sections:
            if section == '🎓':
                enhanced += "\n\n🎓 **专业解读**\n已为您完成专业术语分析，相关概念已在上述关键词中体现。"
            elif section == '📊':
                enhanced += "\n\n📊 **现状分析**\n该研究领域目前发展活跃，建议关注最新的研究进展和方法创新。"
            elif section == '🔍':
                enhanced += "\n\n🔍 **搜索策略**\n已采用层次化关键词扩展策略，确保检索的全面性和精准度。"
            elif section == '💡':
                enhanced += "\n\n💡 **学术指导**\n建议从核心概念入手，逐步深入到具体的技术细节和应用场景。"
        
        print(f"✅ 已补充缺失的解释部分: {missing_sections}")
        return enhanced
    
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
    
    async def search_papers(self, query: str, max_results: int = 10, thread_id: str = None, force_search: bool = False, year_from: Optional[int] = None, year_to: Optional[int] = None, sources: Optional[List[str]] = None, allow_search: bool = True) -> Dict[str, Any]:
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

async def chat_with_search_strategy(query: str, thread_id: str = None, force_search: bool = False, max_results: int = 10, year_from: Optional[int] = None, year_to: Optional[int] = None, sources: Optional[List[str]] = None, allow_search: bool = True) -> Dict[str, Any]:
    """智能聊天与搜索策略分析的统一入口"""
    agent = get_intelligent_paper_search_agent()
    return await agent.search_papers(query, max_results, thread_id, force_search, year_from, year_to, sources, allow_search)


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