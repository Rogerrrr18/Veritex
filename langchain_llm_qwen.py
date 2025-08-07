"""
LangChain兼容的Qwen LLM包装器
基于现有的qwen_api_async.py构建，专为LangGraph设计
"""
import asyncio
from typing import List, Optional, Dict, Any

try:
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.outputs import ChatResult, ChatGeneration
    from langchain_core.callbacks.manager import (
        AsyncCallbackManagerForLLMRun,
        CallbackManagerForLLMRun,
    )
    LANGCHAIN_AVAILABLE = True
except ImportError:
    # 如果LangChain不可用，创建简单的替代类
    LANGCHAIN_AVAILABLE = False
    
    class BaseMessage:
        def __init__(self, content: str):
            self.content = content
    
    class HumanMessage(BaseMessage):
        pass
    
    class AIMessage(BaseMessage):
        pass
        
    class SystemMessage(BaseMessage):
        pass

from qwen_api_async import get_qwen_client


class QwenLLMForLangGraph:
    """
    专为LangGraph优化的Qwen LLM包装器
    简化接口，专注于LangGraph节点使用
    """
    
    def __init__(self, model_name: str = "qwen-turbo", temperature: float = 0.3, max_tokens: int = 1500):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def _convert_messages_to_qwen_format(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """将LangChain消息格式转换为Qwen API格式"""
        qwen_messages = []
        
        for message in messages:
            if isinstance(message, HumanMessage):
                qwen_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                qwen_messages.append({"role": "assistant", "content": message.content})
            elif isinstance(message, SystemMessage):
                qwen_messages.append({"role": "system", "content": message.content})
            else:
                # 默认处理为用户消息
                qwen_messages.append({"role": "user", "content": str(message.content)})
        
        return qwen_messages
    
    async def process_messages(self, messages: List[BaseMessage]) -> str:
        """处理消息列表并返回回复"""
        try:
            # 获取Qwen客户端
            qwen_client = await get_qwen_client()
            
            # 转换消息格式
            qwen_messages = self._convert_messages_to_qwen_format(messages)
            
            # 调用Qwen API
            response = await qwen_client.chat_completion(
                messages=qwen_messages,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            if response:
                return response
            else:
                return "抱歉，我现在无法回复。请稍后再试。"
                
        except Exception as e:
            print(f"Qwen LLM调用错误: {e}")
            import traceback
            print(f"详细错误信息:")
            traceback.print_exc()
            return f"LLM调用失败: {str(e)}"
    
    async def analyze_query(self, query: str, system_prompt: str) -> str:
        """分析用户查询"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"用户查询: {query}\n\n请分析这个查询，提供搜索建议和关键词优化。")
        ]
        
        return await self.process_messages(messages)
    
    async def simple_chat(self, prompt: str, system_prompt: str = None) -> str:
        """简单聊天接口"""
        messages = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        messages.append(HumanMessage(content=prompt))
        
        return await self.process_messages(messages)

# 全局LLM实例
_qwen_llm_instance = None

def get_qwen_llm_for_langgraph(model_name: str = "qwen-turbo") -> QwenLLMForLangGraph:
    """获取LangGraph专用的Qwen LLM实例"""
    global _qwen_llm_instance
    if _qwen_llm_instance is None:
        _qwen_llm_instance = QwenLLMForLangGraph(model_name=model_name, temperature=0.3)
    return _qwen_llm_instance


# 测试函数
async def test_qwen_llm():
    """测试Qwen LLM包装器"""
    print("测试LangChain兼容的Qwen LLM...")
    
    # 测试标准LangChain接口
    llm = get_standard_qwen_llm()
    messages = [
        SystemMessage(content="你是一个专业的文献搜索助手。"),
        HumanMessage(content="我需要搜索关于机器学习的论文")
    ]
    
    try:
        result = await llm._agenerate(messages)
        print(f"LangChain接口测试: {result.generations[0].message.content[:100]}...")
    except Exception as e:
        print(f"LangChain接口测试失败: {e}")
    
    # 测试LangGraph专用接口
    langgraph_llm = get_qwen_llm_for_langgraph()
    try:
        analysis = await langgraph_llm.analyze_query(
            "机器学习在医疗中的应用", 
            "你是专业的学术文献分析助手。"
        )
        print(f"LangGraph接口测试: {analysis[:100]}...")
    except Exception as e:
        print(f"LangGraph接口测试失败: {e}")
    
    print("✅ Qwen LLM包装器测试完成")


if __name__ == "__main__":
    asyncio.run(test_qwen_llm())