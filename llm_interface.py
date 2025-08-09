"""
抽象LLM接口层
为不同模型提供统一的调用接口
"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from model_config import get_model_config_manager, ModelConfig

class BaseLLMAdapter(ABC):
    """LLM适配器基类"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.model_name = config.model_name
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
    
    @abstractmethod
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> Optional[str]:
        """聊天完成接口 - 使用原生消息格式"""
        pass
    
    @abstractmethod
    async def simple_chat(self, user_input: str, history: List[Dict[str, str]] = None) -> str:
        """简单聊天接口"""
        pass
    
    @abstractmethod
    async def process_langchain_messages(self, messages: List[BaseMessage]) -> str:
        """处理LangChain消息格式"""
        pass
    
    def _convert_langchain_messages_to_dict(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """将LangChain消息格式转换为字典格式"""
        converted_messages = []
        
        for message in messages:
            if isinstance(message, HumanMessage):
                converted_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                converted_messages.append({"role": "assistant", "content": message.content})
            elif isinstance(message, SystemMessage):
                converted_messages.append({"role": "system", "content": message.content})
            else:
                # 默认处理为用户消息
                converted_messages.append({"role": "user", "content": str(message.content)})
        
        return converted_messages
    
    async def analyze_query(self, query: str, system_prompt: str) -> str:
        """分析用户查询（为LangGraph工作流提供支持）"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户查询: {query}\n\n请分析这个查询，提供搜索建议和关键词优化。"}
        ]
        
        result = await self.chat_completion(messages)
        return result if result else "分析失败，请稍后再试。"
    
    async def close(self):
        """清理资源（子类可重写）"""
        pass

class UniversalLLM:
    """
    统一LLM接口 - 根据配置自动选择和初始化对应的适配器
    这是用户代码主要交互的类
    """
    
    def __init__(self):
        self.config_manager = get_model_config_manager()
        self.adapter = None
        self._initialize_adapter()
    
    def _initialize_adapter(self):
        """根据当前配置初始化对应的适配器"""
        active_model = self.config_manager.get_active_model_name()
        config = self.config_manager.get_active_config()
        
        # 导入对应的适配器 (动态导入避免循环依赖)
        if active_model == "qwen":
            from adapters.qwen_adapter import QwenAdapter
            self.adapter = QwenAdapter(config)
        elif active_model == "openai":
            from adapters.openai_adapter import OpenAIAdapter
            self.adapter = OpenAIAdapter(config)
        elif active_model == "claude":
            from adapters.claude_adapter import ClaudeAdapter
            self.adapter = ClaudeAdapter(config)
        elif active_model == "deepseek":
            from adapters.deepseek_adapter import DeepSeekAdapter
            self.adapter = DeepSeekAdapter(config)
        else:
            raise ValueError(f"不支持的模型类型: {active_model}")
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> Optional[str]:
        """统一聊天完成接口"""
        return await self.adapter.chat_completion(messages, **kwargs)
    
    async def simple_chat(self, user_input: str, history: List[Dict[str, str]] = None) -> str:
        """统一简单聊天接口"""
        return await self.adapter.simple_chat(user_input, history)
    
    async def process_langchain_messages(self, messages: List[BaseMessage]) -> str:
        """统一LangChain消息处理接口"""
        return await self.adapter.process_langchain_messages(messages)
    
    async def analyze_query(self, query: str, system_prompt: str) -> str:
        """统一查询分析接口（用于LangGraph）"""
        return await self.adapter.analyze_query(query, system_prompt)
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型信息"""
        return {
            "active_model": self.config_manager.get_active_model_name(),
            "model_name": self.adapter.model_name,
            "temperature": self.adapter.temperature,
            "max_tokens": self.adapter.max_tokens,
            "available_models": self.config_manager.list_available_models()
        }
    
    async def close(self):
        """清理资源"""
        if self.adapter:
            await self.adapter.close()

# 全局LLM实例
_universal_llm = None

async def get_universal_llm() -> UniversalLLM:
    """获取全局统一LLM实例"""
    global _universal_llm
    if _universal_llm is None:
        _universal_llm = UniversalLLM()
    return _universal_llm

# 便捷函数，保持向后兼容
async def get_llm_client():
    """获取LLM客户端（向后兼容）"""
    return await get_universal_llm()

class LangGraphLLMWrapper:
    """
    专为LangGraph优化的包装器
    保持与原有langchain_llm_qwen.py的接口兼容性
    """
    
    def __init__(self):
        self.universal_llm = None
    
    async def _ensure_initialized(self):
        """确保LLM已初始化"""
        if self.universal_llm is None:
            self.universal_llm = await get_universal_llm()
    
    async def process_messages(self, messages: List[BaseMessage]) -> str:
        """处理消息列表并返回回复（与原接口兼容）"""
        await self._ensure_initialized()
        return await self.universal_llm.process_langchain_messages(messages)
    
    async def analyze_query(self, query: str, system_prompt: str) -> str:
        """分析用户查询（与原接口兼容）"""
        await self._ensure_initialized()
        return await self.universal_llm.analyze_query(query, system_prompt)
    
    async def simple_chat(self, prompt: str, system_prompt: str = None) -> str:
        """简单聊天接口（与原接口兼容）"""
        await self._ensure_initialized()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        result = await self.universal_llm.chat_completion(messages)
        return result if result else "抱歉，我现在无法回复。请稍后再试。"

# 向后兼容的全局实例
_langgraph_llm_instance = None

def get_llm_for_langgraph() -> LangGraphLLMWrapper:
    """获取LangGraph专用的LLM实例（保持向后兼容）"""
    global _langgraph_llm_instance
    if _langgraph_llm_instance is None:
        _langgraph_llm_instance = LangGraphLLMWrapper()
    return _langgraph_llm_instance

# 测试功能
async def test_universal_llm():
    """测试统一LLM接口"""
    print("🔍 测试统一LLM接口...")
    
    try:
        # 测试UniversalLLM
        llm = await get_universal_llm()
        print(f"✅ 当前模型信息: {llm.get_model_info()}")
        
        # 测试简单聊天
        response = await llm.simple_chat("你好，请介绍一下自己")
        print(f"✅ 简单聊天测试: {response[:100]}...")
        
        # 测试LangChain消息处理
        messages = [
            SystemMessage(content="你是一个专业的AI助手。"),
            HumanMessage(content="请解释什么是人工智能")
        ]
        response = await llm.process_langchain_messages(messages)
        print(f"✅ LangChain消息处理测试: {response[:100]}...")
        
        # 测试LangGraph兼容包装器
        langgraph_llm = get_llm_for_langgraph()
        analysis = await langgraph_llm.analyze_query(
            "机器学习算法研究", 
            "你是专业的学术文献分析助手。"
        )
        print(f"✅ LangGraph兼容性测试: {analysis[:100]}...")
        
        await llm.close()
        print("✅ 统一LLM接口测试完成")
        
    except Exception as e:
        print(f"❌ 统一LLM接口测试失败: {e}")
        print("💡 请检查模型配置和网络连接")

if __name__ == "__main__":
    asyncio.run(test_universal_llm())