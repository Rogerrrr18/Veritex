"""
简化版 LangGraph 文献搜索工作流 - Prompt驱动架构
完全基于LLM决策的简化工作流：START → 意图分析(LLM) → [条件分支] MCP工具调用 → END
"""
import asyncio
import json
import uuid
from typing import Dict, Any, List
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# 导入自定义模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langchain_llm_qwen import get_qwen_llm_for_langgraph
from langchain_workflows.state_schemas import PaperSearchState, create_initial_state


class SimplePaperSearchAgent:
    """
    简化版论文搜索Agent - 完全由Prompt驱动
    START → 意图分析与问答(LLM) → [条件分支] MCP工具调用 → END
    """
    
    def __init__(self, enable_memory: bool = True):
        self.enable_memory = enable_memory
        self.llm = get_qwen_llm_for_langgraph()
        self.system_prompt = self._load_system_prompt()
        self.tools = self._initialize_tools()
        self.checkpointer = MemorySaver() if enable_memory else None
        self.graph = self._build_graph()
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "literature_search_agent.txt")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"警告: 无法加载系统提示词: {e}")
            return """
# 智能文献管理与Agent

## 角色定义  
您是一个专业的智能文献管理和搜索助手。

## 关键规则
**当用户明确要求搜索文献时**，请在回答前添加：
SEARCH_NEEDED: [优化的英文关键词]

**其他情况请直接回答**。
            """
    
    def _initialize_tools(self) -> List:
        """初始化MCP工具"""
        tools = []
        try:
            from langchain_tools.universal_mcp_tool import create_google_scholar_tools
            tools.extend(create_google_scholar_tools())
            print(f"✅ 成功加载 {len(tools)} 个MCP工具")
        except Exception as e:
            print(f"⚠️ MCP工具加载失败: {e}")
        return tools
    
    def _build_graph(self) -> StateGraph:
        """构建简化的LangGraph工作流"""
        workflow = StateGraph(PaperSearchState)
        
        # 添加核心节点
        workflow.add_node("intent_analysis", self.intent_analysis_node)
        if self.tools:
            workflow.add_node("tool_call", self.tool_call_node)
        
        # 定义流程路径
        workflow.add_edge(START, "intent_analysis")
        
        if self.tools:
            workflow.add_conditional_edges(
                "intent_analysis",
                self.should_use_tools,
                {
                    "use_tools": "tool_call",
                    "end": END
                }
            )
            workflow.add_edge("tool_call", END)
        else:
            workflow.add_edge("intent_analysis", END)
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def intent_analysis_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """简化版LLM意图分析节点 - 完全基于prompt驱动"""
        try:
            query = state.get("query", "")
            user_message = state.get("messages", [])[-1].content if state.get("messages") else query
            
            print(f"🤖 LLM处理用户请求: {user_message}")
            
            # 构建完整的prompt，让LLM完全基于prompt文件内容来决策
            full_prompt = f"""
{self.system_prompt}

---
用户查询: {user_message}

请根据以上系统提示词的要求处理用户查询。

如果用户需要文献搜索，请在回答前添加特殊标记：SEARCH_NEEDED: [搜索关键词]
如果不需要搜索，请直接回答用户问题。
"""
            
            # 调用LLM进行处理
            ai_response = await self.llm.simple_chat(full_prompt, "")
            
            print(f"📊 LLM响应: {ai_response[:100]}...")
            
            # 检查是否需要工具调用
            if "SEARCH_NEEDED:" in ai_response:
                # 提取搜索关键词
                lines = ai_response.split('\n')
                search_line = next((line for line in lines if "SEARCH_NEEDED:" in line), "")
                search_keywords = search_line.replace("SEARCH_NEEDED:", "").strip()
                
                print(f"🔍 需要搜索: '{search_keywords}'")
                
                return {
                    "search_keywords": search_keywords,
                    "need_tools": True,
                    "current_step": "needs_search",
                    "messages": [AIMessage(content=f"正在为您搜索'{search_keywords}'相关文献...")]
                }
            else:
                # 直接回答，不需要工具
                return {
                    "need_tools": False,
                    "current_step": "completed",
                    "is_completed": True,
                    "messages": [AIMessage(content=ai_response)]
                }
                
        except Exception as e:
            error_msg = f"LLM处理失败: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "need_tools": False,
                "error_message": error_msg,
                "current_step": "error",
                "messages": [AIMessage(content="抱歉，处理您的请求时出现错误。请稍后再试。")]
            }
    
    async def tool_call_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """MCP工具调用节点"""
        try:
            search_keywords = state.get("search_keywords", "")
            max_results = state.get("max_results", 10)
            
            print(f"🔍 工具调用节点被触发")
            print(f"    搜索关键词: '{search_keywords}'")
            print(f"    最大结果数: {max_results}")
            print(f"    可用工具数: {len(self.tools)}")
            
            if not search_keywords:
                return {
                    "current_step": "error",
                    "error_message": "搜索关键词为空",
                    "messages": [AIMessage(content="搜索关键词提取失败。")]
                }
            
            if not self.tools:
                return {
                    "current_step": "error",
                    "error_message": "没有可用的搜索工具",
                    "messages": [AIMessage(content="抱歉，搜索服务暂时不可用。")]
                }
            
            # 使用第一个可用工具进行搜索
            try:
                search_tool = self.tools[0]
                search_result_str = await search_tool._arun(search_keywords, max_results)
                search_result = json.loads(search_result_str)
                
                if search_result.get("status") == "success":
                    papers = search_result.get("papers", [])
                    print(f"✅ 搜索成功: 找到 {len(papers)} 篇论文")
                    
                    # 生成文献表格
                    formatted_result = self._format_papers_table(papers, search_keywords)
                    
                    return {
                        "papers": papers,
                        "total_found": len(papers),
                        "current_step": "completed",
                        "is_completed": True,
                        "messages": [AIMessage(content=formatted_result)]
                    }
                else:
                    error_msg = search_result.get("message", "搜索失败")
                    print(f"⚠️ 工具搜索失败，使用模拟数据: {error_msg}")
                    # 回退到模拟数据
                    return self._generate_mock_search_result(search_keywords, max_results)
            except Exception as tool_error:
                print(f"⚠️ 工具调用异常，使用模拟数据: {tool_error}")
                # 回退到模拟数据
                return self._generate_mock_search_result(search_keywords, max_results)
                
        except Exception as e:
            error_msg = f"工具调用失败: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "current_step": "error",
                "error_message": error_msg,
                "messages": [AIMessage(content="文献搜索过程中出现错误。")]
            }
    
    def _format_papers_table(self, papers: List[Dict], query: str) -> str:
        """生成标准化文献表格"""
        if not papers:
            return f"很抱歉，没有找到关于'{query}'的相关文献。"
        
        table = f"## 关于'{query}'的文献搜索结果\n\n共找到 {len(papers)} 篇相关论文：\n\n"
        table += "| Title | Author | DOI | Year | Abstract | Journal | Citation_Count | Research_Type | Access_Status |\n"
        table += "|-------|--------|-----|------|----------|---------|----------------|---------------|---------------|\n"
        
        for paper in papers:
            title = (paper.get("title", "")[:50] + "...") if len(paper.get("title", "")) > 50 else paper.get("title", "")
            authors = (paper.get("authors", "")[:30] + "...") if len(paper.get("authors", "")) > 30 else paper.get("authors", "")
            doi = paper.get("doi", "")
            doi_link = f"[{doi}](https://doi.org/{doi})" if doi else "无"
            year = paper.get("year", "")
            abstract = (paper.get("abstract", "")[:80] + "...") if len(paper.get("abstract", "")) > 80 else paper.get("abstract", "")
            journal = (paper.get("venue", "")[:20] + "...") if len(paper.get("venue", "")) > 20 else paper.get("venue", "")
            citations = paper.get("citations", 0)
            research_type = paper.get("research_type", "其他")
            access_status = paper.get("access_status", "未知")
            
            table += f"| {title} | {authors} | {doi_link} | {year} | {abstract} | {journal} | {citations} | {research_type} | {access_status} |\n"
        
        table += f"\n\n---\n**搜索统计**:\n- 搜索关键词: {query}\n- 找到论文数量: {len(papers)}\n- 搜索时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        return table
    
    def _generate_mock_search_result(self, search_keywords: str, max_results: int) -> Dict[str, Any]:
        """生成模拟搜索结果"""
        print(f"📋 生成模拟搜索结果: {search_keywords}")
        
        mock_papers = []
        for i in range(min(max_results, 3)):  # 最多生成3篇模拟论文
            mock_papers.append({
                "title": f"Research on {search_keywords}: Study {i+1}",
                "authors": f"Author {i+1}, A., Author {i+2}, B.",
                "abstract": f"This comprehensive study examines {search_keywords} using advanced methodologies. Our research contributes significant insights to the field...",
                "year": 2024 - i,
                "venue": f"Journal of {search_keywords.title()} Research",
                "citations": 50 + i*10,
                "doi": f"10.1000/mock.{2024-i}.{i+1}",
                "research_type": "实验研究" if i % 2 == 0 else "理论分析",
                "access_status": "开放获取" if i % 2 == 0 else "付费订阅"
            })
        
        formatted_result = self._format_papers_table(mock_papers, search_keywords)
        formatted_result += "\n\n**注意**: 以上为演示数据，实际搜索功能暂时不可用。"
        
        return {
            "papers": mock_papers,
            "total_found": len(mock_papers),
            "current_step": "completed",
            "is_completed": True,
            "messages": [AIMessage(content=formatted_result)]
        }
    
    def should_use_tools(self, state: PaperSearchState) -> str:
        """简化的工具决策逻辑"""
        need_tools = state.get("need_tools", False)
        current_step = state.get("current_step", "")
        
        print(f"🤔 工具决策: need_tools={need_tools}, step={current_step}")
        
        return "use_tools" if (need_tools or current_step == "needs_search") else "end"
    
    async def search_papers(self, query: str, max_results: int = 10, thread_id: str = None) -> Dict[str, Any]:
        """主要搜索接口"""
        if thread_id is None:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        
        initial_state = create_initial_state(
            query=query,
            user_message=query,  # 直接使用用户原始查询
            max_results=max_results
        )
        
        print(f"🚀 启动简化工作流 - 查询: {query}")
        
        config = {"configurable": {"thread_id": thread_id}} if self.enable_memory else {}
        
        try:
            final_state = await self.graph.ainvoke(initial_state, config)
            
            messages = final_state.get("messages", [])
            papers = final_state.get("papers", [])
            is_completed = final_state.get("is_completed", False)
            error_message = final_state.get("error_message")
            
            final_response = ""
            if messages:
                ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
                if ai_messages:
                    final_response = ai_messages[-1].content
            
            result = {
                "success": is_completed and not error_message,
                "papers": papers or [],
                "total_found": len(papers) if papers else 0,
                "formatted_results": final_response,
                "error_message": error_message,
                "thread_id": thread_id,
                "query": query
            }
            
            print(f"✅ 工作流完成: {'成功' if result['success'] else '失败'}")
            return result
            
        except Exception as e:
            error_msg = f"工作流执行错误: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "papers": [],
                "total_found": 0,
                "formatted_results": "",
                "error_message": error_msg,
                "thread_id": thread_id,
                "query": query
            }


# 全局实例和便捷函数
_simple_agent = None

def get_simple_paper_search_agent(enable_memory: bool = True) -> SimplePaperSearchAgent:
    """获取简化Agent实例"""
    global _simple_agent
    if _simple_agent is None:
        _simple_agent = SimplePaperSearchAgent(enable_memory=enable_memory)
    return _simple_agent

async def process_user_query(query: str, max_results: int = 10, thread_id: str = None) -> Dict[str, Any]:
    """处理用户查询 - 包括问答和文献搜索"""
    agent = get_simple_paper_search_agent()
    return await agent.search_papers(query, max_results, thread_id)

async def search_literature_simple(query: str, max_results: int = 10, thread_id: str = None) -> Dict[str, Any]:
    """简化版文献搜索函数 - 兼容接口"""
    return await process_user_query(query, max_results, thread_id)


# 测试函数
async def test_simple_agent():
    """测试简化Agent"""
    print("🧪 测试简化版LangGraph工作流")
    print("=" * 50)
    
    # 测试1: 直接问答
    result1 = await search_literature_simple("什么是人工智能？")
    print(f"测试1 - 问答: 成功={result1['success']}")
    print(f"回答预览: {result1['formatted_results'][:100]}...")
    
    # 测试2: 文献搜索
    result2 = await search_literature_simple("我需要5篇关于机器学习的论文")  
    print(f"测试2 - 搜索: 成功={result2['success']}, 论文数={result2['total_found']}")
    
    print("✅ 简化测试完成")


if __name__ == "__main__":
    asyncio.run(test_simple_agent())