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
                self._search_engine = MultiSourceEngine(enable_mcp=False)
                print("✅ 多源搜索引擎实例化成功")
            except Exception as e:
                print(f"❌ 搜索引擎实例化失败: {e}")
                # 创建一个模拟搜索引擎
                self._search_engine = MockSearchEngine()
        return self._search_engine
    
    def _load_system_prompt(self) -> str:
        """加载专业学术分析系统提示词"""
        try:
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "prompts", 
                "refined_system_prompt.txt"
            )
            with open(prompt_path, 'r', encoding='utf-8') as f:
                original_prompt = f.read().strip()
                print(f"📄 成功加载专业学术分析提示词，长度: {len(original_prompt)}")
                return original_prompt
        except Exception as e:
            print(f"❌ 无法加载学术分析提示词: {e}")
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
            final_response = self._final_clean_response(ai_response)
            
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
            # 首先检查是否包含JSON（学术查询的标志）
            json_match = re.search(r'\{[\s\S]*?\}', response)
            
            if json_match:
                # 学术查询：提取JSON后面的解释部分
                json_end_pos = json_match.end()
                explanation_part = response[json_end_pos:].strip()
                
                # 清理代码块标记
                explanation_part = re.sub(r'```[\s\S]*?```', '', explanation_part)
                explanation_part = explanation_part.strip()
                
                if explanation_part and len(explanation_part) > 10:
                    print(f"✅ 学术查询响应清理完成，提取解释部分，长度: {len(explanation_part)}")
                    return explanation_part
                else:
                    print("⚠️ 学术查询缺少解释部分，使用默认回复")
                    return "已完成学术分析。如需查看具体论文搜索结果，请等待搜索完成。"
            else:
                # 普通对话：直接清理格式标记
                cleaned = response.strip()
                # 移除可能的代码块标记
                cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
                cleaned = cleaned.strip()
                
                if cleaned and len(cleaned) > 5:
                    print(f"✅ 普通对话响应清理完成，长度: {len(cleaned)}")
                    return cleaned
                else:
                    print("⚠️ 普通对话响应为空，使用默认回复")
                    return "你好！有什么可以帮助你的吗？"
                    
        except Exception as e:
            print(f"⚠️ 最终清理失败: {e}")
            return "你好！有什么可以帮助你的吗？"
    
    def should_execute_search(self, state: PaperSearchState) -> str:
        """判断是否需要执行搜索"""
        is_academic = state.get("is_academic_query", False)
        need_search = state.get("need_search_strategy", False)
        
        if is_academic and need_search:
            print("🔍 判断为学术查询，执行搜索")
            return "search"
        else:
            print("💬 判断为普通对话，直接回复")
            return "direct_reply"
    
    async def search_execution_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """搜索执行节点 - 调用现有多源搜索引擎"""
        try:
            query = state.get("query", "")
            max_results = state.get("max_results", 10)
            analysis = state.get("analysis_result", {})
            
            print(f"🔍 开始执行搜索: query={query}, max_results={max_results}")
            
            # 构建搜索查询
            search_query = self._build_search_query(query, analysis)
            print(f"📋 构建的搜索查询: {search_query}")
            
            # 获取搜索引擎并执行搜索
            search_engine = await self._get_search_engine()
            
            # MultiSourceEngine使用不同的搜索接口
            if hasattr(search_engine, 'search_parallel'):
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
        """结果格式化节点 - 生成用户友好的回复"""
        try:
            search_results = state.get("search_results", [])
            analysis = state.get("analysis_result", {})
            keywords = state.get("search_keywords", [])
            
            print(f"📋 开始格式化 {len(search_results)} 个搜索结果")
            
            # 构建回复消息
            if search_results:
                response = self._build_search_response(search_results, analysis, keywords)
            else:
                response = "抱歉，未找到相关的学术论文。建议：\n- 尝试不同的关键词\n- 使用更通用的术语\n- 检查关键词拼写"
            
            return {
                "current_step": "completed",
                "is_completed": True,
                "messages": [AIMessage(content=response)]
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
    
    async def search_papers(self, query: str, max_results: int = 10, thread_id: str = None) -> Dict[str, Any]:
        """主要搜索接口"""
        if thread_id is None:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        
        initial_state = create_initial_state(
            query=query,
            user_message=query,
            max_results=max_results
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

async def chat_with_search_strategy(query: str, thread_id: str = None) -> Dict[str, Any]:
    """智能聊天与搜索策略分析的统一入口"""
    agent = get_intelligent_paper_search_agent()
    return await agent.search_papers(query, 10, thread_id)


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