"""
简化版 LangGraph 智能问答工作流 - 专注于意图识别和搜索策略
工作流程：START → 意图分析(LLM) → 搜索策略输出/直接问答 → END
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

# 使用统一LLM接口
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from llm_interface import get_llm_for_langgraph
from langchain_workflows.state_schemas import PaperSearchState, create_initial_state


class SimplePaperSearchAgent:
    """
    简化版智能问答Agent - 专注于意图识别和搜索策略输出
    START → 意图分析(LLM) → 搜索策略分析/直接问答 → END
    """
    
    def __init__(self, enable_memory: bool = True):
        self.enable_memory = enable_memory
        # 使用统一LLM接口
        self.llm = get_llm_for_langgraph()
        self.system_prompt = self._load_system_prompt()
        self.tools = self._initialize_tools()
        self.checkpointer = MemorySaver() if enable_memory else None
        self.graph = self._build_graph()
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "3.txt")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                original_prompt = f.read().strip()
                print(f"📄 成功加载系统提示词文件，长度: {len(original_prompt)}")
                # 直接返回用户自定义的提示词内容
                return original_prompt
        except Exception as e:
            print(f"❌ 无法加载系统提示词文件: {e}")
            return """你是专业的智能学术助手。请提供准确、专业且有帮助的回答。对于学术和技术问题，请展现你的专业知识深度。始终用中文回答。"""
    
    def _initialize_tools(self) -> List:
        """初始化MCP工具 - 暂时注释掉"""
        tools = []
        # TODO: 暂时注释掉MCP工具，专注于问答和关键词分析
        # try:
        #     from langchain_tools.universal_mcp_tool import create_google_scholar_tools
        #     tools.extend(create_google_scholar_tools())
        #     print(f"✅ 成功加载 {len(tools)} 个MCP工具")
        # except Exception as e:
        #     print(f"⚠️ MCP工具加载失败: {e}")
        print(f"📝 简化模式：专注于问答和搜索策略分析")
        return tools
    
    def _build_graph(self) -> StateGraph:
        """构建简化的LangGraph工作流"""
        workflow = StateGraph(PaperSearchState)
        
        # 添加核心节点 - 简化版只需要意图分析
        workflow.add_node("intent_analysis", self.intent_analysis_node)
        # 注释掉工具调用节点，简化工作流
        # if self.tools:
        #     workflow.add_node("tool_call", self.tool_call_node)
        
        # 定义流程路径 - 简化为直接从分析到结束
        workflow.add_edge(START, "intent_analysis")
        workflow.add_edge("intent_analysis", END)
        
        # 注释掉条件分支，简化工作流
        # if self.tools:
        #     workflow.add_conditional_edges(
        #         "intent_analysis",
        #         self.should_use_tools,
        #         {
        #             "use_tools": "tool_call",
        #             "end": END
        #         }
        #     )
        #     workflow.add_edge("tool_call", END)
        # else:
        #     workflow.add_edge("intent_analysis", END)
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def intent_analysis_node(self, state: PaperSearchState) -> Dict[str, Any]:
        """简化版LLM意图分析节点 - 完全基于prompt驱动，无回退机制"""
        try:
            query = state.get("query", "")
            user_message = state.get("messages", [])[-1].content if state.get("messages") else query
            
            print(f"🤖 LLM处理用户请求: {user_message}")
            
            # 使用统一LLM接口 - 移除回退机制，完全依赖系统提示词
            ai_response = await self.llm.simple_chat(
                prompt=user_message,
                system_prompt=self.system_prompt
            )
            
            print(f"📋 使用了系统提示词，长度: {len(self.system_prompt)}")
            
            # 如果API返回为空，直接报告错误而不是回退
            if not ai_response:
                error_msg = "LLM API返回为空，请检查API配置"
                print(f"❌ {error_msg}")
                return {
                    "error_message": error_msg,
                    "current_step": "failed",
                    "is_completed": False,
                    "messages": [AIMessage(content=f"抱歉，API调用失败：{error_msg}")]
                }
            
            print(f"📝 LLM回复成功，响应长度: {len(ai_response)}")
            
            # 返回处理后的响应
            return {
                "current_step": "completed",
                "is_completed": True,
                "messages": [AIMessage(content=ai_response)]
            }
                
        except Exception as e:
            error_msg = f"LLM处理失败: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "error_message": error_msg,
                "current_step": "failed",
                "is_completed": False,
                "messages": [AIMessage(content=f"系统错误：{error_msg}")]
            }
    
    
    def _extract_chinese_response(self, response: str) -> str:
        """从混合响应中提取中文回复部分"""
        try:
            # 如果响应包含JSON，尝试提取JSON后的中文部分
            if "```" in response:
                # 查找最后一个```之后的内容
                parts = response.split("```")
                if len(parts) >= 3:  # JSON + 中文解释
                    chinese_part = parts[-1].strip()
                    if chinese_part and len(chinese_part) > 10:  # 确保有实质内容
                        return chinese_part
            
            # 尝试按段落分割，寻找中文解释段落
            lines = response.split('\n')
            chinese_lines = []
            json_ended = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 跳过明显的JSON标记
                if line.startswith('{') or line.startswith('}') or '":' in line:
                    json_ended = True
                    continue
                
                # 如果已经过了JSON部分，开始收集中文内容
                if json_ended and line:
                    # 检查是否包含中文字符
                    if any('\u4e00' <= char <= '\u9fff' for char in line):
                        chinese_lines.append(line)
                elif not json_ended and any('\u4e00' <= char <= '\u9fff' for char in line):
                    # 即使在JSON前也收集中文内容
                    chinese_lines.append(line)
            
            if chinese_lines:
                extracted = '\n'.join(chinese_lines)
                if len(extracted) > 20:  # 确保有足够的内容
                    return extracted
            
            # 如果上述方法都失败，返回原响应（可能全部都是中文）
            return response.strip()
            
        except Exception as e:
            print(f"⚠️ 响应提取出错: {e}")
            return response.strip()
    
    # 注释掉工具调用节点 - 简化版不使用外部工具
    # async def tool_call_node(self, state: PaperSearchState) -> Dict[str, Any]:
    #     """MCP工具调用节点 - 已注释，简化版不使用"""
    #     pass
    
    # 已删除 _generate_search_strategy 方法 - 完全基于prompt驱动
    
    # 移除模拟搜索结果生成，改为搜索策略输出
    # def _generate_mock_search_result(self, search_keywords: str, max_results: int) -> Dict[str, Any]:
    #     """已移除 - 简化版不生成模拟数据"""
    #     pass
    
    # 注释掉工具决策逻辑 - 简化版不使用工具
    # def should_use_tools(self, state: PaperSearchState) -> str:
    #     """工具决策逻辑 - 已注释，简化版不使用"""
    #     pass
    
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
            is_completed = final_state.get("is_completed", False)
            error_message = final_state.get("error_message")
            
            final_response = ""
            if messages:
                ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
                if ai_messages:
                    final_response = ai_messages[-1].content
            
            result = {
                "success": is_completed and not error_message,
                "response": final_response,
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
                "response": "处理您的请求时出现错误，请稍后再试。",
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

async def process_user_query(query: str, thread_id: str = None) -> Dict[str, Any]:
    """处理用户查询 - 智能问答和搜索策略分析"""
    agent = get_simple_paper_search_agent()
    return await agent.search_papers(query, 10, thread_id)

async def chat_with_search_strategy(query: str, thread_id: str = None) -> Dict[str, Any]:
    """简化版智能聊天函数 - 支持搜索策略分析"""
    return await process_user_query(query, thread_id)


# 测试函数
async def test_simple_agent():
    """测试简化Agent"""
    print("🧪 测试简化版LangGraph工作流")
    print("=" * 50)
    
    # 测试1: 直接问答
    result1 = await chat_with_search_strategy("什么是人工智能？")
    print(f"测试1 - 问答: 成功={result1['success']}")
    print(f"回答预览: {result1['response'][:100]}...")
    
    # 测试2: 检索参数分析
    result2 = await chat_with_search_strategy("我需要5篇关于机器学习的论文")  
    print(f"测试2 - 检索分析: 成功={result2['success']}")
    print(f"响应长度: {len(result2['response'])}")
    
    print("✅ 简化测试完成")


if __name__ == "__main__":
    asyncio.run(test_simple_agent())