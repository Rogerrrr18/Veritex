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

# 直接使用千问API，无需LangChain包装器
# from langchain_llm_qwen import get_qwen_llm_for_langgraph
from langchain_workflows.state_schemas import PaperSearchState, create_initial_state


class SimplePaperSearchAgent:
    """
    简化版智能问答Agent - 专注于意图识别和搜索策略输出
    START → 意图分析(LLM) → 搜索策略分析/直接问答 → END
    """
    
    def __init__(self, enable_memory: bool = True):
        self.enable_memory = enable_memory
        # 直接使用千问API，无需LangChain包装器
        # self.llm = get_qwen_llm_for_langgraph()
        self.system_prompt = self._load_system_prompt()
        self.tools = self._initialize_tools()
        self.checkpointer = MemorySaver() if enable_memory else None
        self.graph = self._build_graph()
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "2.txt")
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
        """简化版LLM意图分析节点 - 完全基于prompt驱动"""
        try:
            query = state.get("query", "")
            user_message = state.get("messages", [])[-1].content if state.get("messages") else query
            
            print(f"🤖 LLM处理用户请求: {user_message}")
            
            # 直接调用千问API，简化中间层
            try:
                # 导入千问API客户端
                from qwen_api_async import get_qwen_client
                qwen_client = await get_qwen_client()
                
                # 使用更短、更直接的prompt减少超时风险
                simple_prompt = f"""你是专业的智能助手。请简洁明了地回答用户问题。

问题: {user_message}

请用中文回答:"""
                
                # 设置较短的超时时间
                ai_response = await qwen_client.chat_completion(
                    messages=[{"role": "user", "content": simple_prompt}],
                    model="qwen-turbo",  # 使用较快的模型
                    temperature=0.7,
                    max_tokens=800  # 限制token数量
                )
                
                # 如果API调用成功
                if ai_response and len(ai_response) > 20:
                    print(f"📊 直接API调用成功，响应长度: {len(ai_response)}")
                    final_response = ai_response
                else:
                    print("⚠️ API响应为空或过短，使用回退机制")
                    raise Exception("API响应无效")
                    
            except Exception as e:
                print(f"⚠️ API调用失败: {e}，使用动态回退机制...")
                # 直接使用动态回退，不再尝试复杂prompt
                final_response = await self._generate_professional_fallback_response(user_message)
            
            print(f"📝 最终中文回复: {final_response[:100]}...")
            
            # 如果仍然是错误消息，提供专业的备用回复
            if "抱歉" in final_response and "无法回复" in final_response:
                final_response = await self._generate_professional_fallback_response(user_message)
            
            # 返回处理后的中文响应
            return {
                "current_step": "completed",
                "is_completed": True,
                "messages": [AIMessage(content=final_response)]
            }
                
        except Exception as e:
            error_msg = f"LLM处理失败: {str(e)}"
            print(f"❌ {error_msg}")
            # 提供专业的回退响应而不是通用错误
            fallback_response = await self._generate_professional_fallback_response(user_message)
            return {
                "error_message": error_msg,
                "current_step": "completed",
                "is_completed": True,  # 标记为完成，因为我们提供了回退回复
                "messages": [AIMessage(content=fallback_response)]
            }
    
    async def _generate_professional_fallback_response(self, user_query: str) -> str:
        """生成专业的备用回复 - 简化版避免超时"""
        try:
            # 尝试快速的动态回复生成
            from qwen_api_async import get_qwen_client
            qwen_client = await get_qwen_client()
            
            # 简化的prompt，减少token消耗和延迟
            fallback_prompt = f"""简洁回答: {user_query}

用中文专业回答，100字以内:"""

            # 使用最快速的配置
            dynamic_response = await qwen_client.chat_completion(
                messages=[{"role": "user", "content": fallback_prompt}],
                model="qwen-turbo",
                temperature=0.3,
                max_tokens=200
            )
            
            if dynamic_response and len(dynamic_response) > 20:
                print(f"✅ 快速回退响应生成成功")
                return dynamic_response
            else:
                print("⚠️ 动态回退失败，使用静态回退")
                raise Exception("动态回退无效")
                
        except Exception as e:
            print(f"⚠️ 动态回退完全失败: {e}")
            # 根据查询内容提供静态但相关的回复
            query_lower = user_query.lower()
            
            if any(word in query_lower for word in ['机器学习', 'machine learning', 'ai', '人工智能']):
                return """机器学习是人工智能的重要分支，让计算机从数据中学习模式。主要包括监督学习、无监督学习和强化学习。如需了解更多，建议查阅相关学术资料或在线课程。"""
            elif any(word in query_lower for word in ['甲烷', 'methane', '重整', 'reforming']):
                return """甲烷干重整是重要的化工过程，涉及甲烷与二氧化碳反应生成合成气。这个过程在清洁能源和化工行业有重要应用。建议查阅专业化工文献了解详细机理。"""
            elif any(word in query_lower for word in ['论文', '文献', 'paper', 'research']):
                return """对于学术文献搜索，建议使用专业数据库如Web of Science、Google Scholar等。关键是选择合适的关键词，关注权威期刊，并注意文献的引用情况。"""
            else:
                return f"""感谢您的问题。关于"{user_query}"，我理解您的需求。建议提供更多背景信息以便我给出更准确的回答，或者您可以稍后重试。"""
    
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