"""
OpenAI模型适配器
支持OpenAI GPT系列模型
"""
import httpx
from typing import List, Dict, Optional
from langchain_core.messages import BaseMessage

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from llm_interface import BaseLLMAdapter
from model_config import ModelConfig

class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI模型适配器"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }
        # 创建异步HTTP客户端
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> Optional[str]:
        """
        OpenAI聊天完成API调用
        """
        if not self.config.api_key:
            raise ValueError("OPENAI_API_KEY 未设置，请检查 .env 文件")
        
        # 合并默认参数和传入参数
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens)
        }
        
        try:
            response = await self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                print(f"OpenAI API响应格式异常: {result}")
                return None
                
        except httpx.HTTPError as e:
            print(f"OpenAI API调用失败: {e}")
            print(f"HTTP状态码: {getattr(e.response, 'status_code', 'N/A') if hasattr(e, 'response') and e.response else 'N/A'}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"响应内容: {e.response.text[:500]}")
                except:
                    pass
            return None
        except Exception as e:
            print(f"OpenAI处理响应时出错: {e}")
            return None
    
    async def simple_chat(self, user_input: str, history: List[Dict[str, str]] = None) -> str:
        """
        简单异步聊天接口
        """
        if history is None:
            history = []
        
        messages = history + [{"role": "user", "content": user_input}]
        
        response = await self.chat_completion(messages)
        if response:
            return response
        else:
            return "抱歉，我现在无法回复。请稍后再试。"
    
    async def process_langchain_messages(self, messages: List[BaseMessage]) -> str:
        """处理LangChain消息格式"""
        try:
            # 转换消息格式
            converted_messages = self._convert_langchain_messages_to_dict(messages)
            
            # 调用OpenAI API
            response = await self.chat_completion(converted_messages)
            
            if response:
                return response
            else:
                return "抱歉，我现在无法回复。请稍后再试。"
                
        except Exception as e:
            print(f"OpenAI LangChain消息处理错误: {e}")
            import traceback
            print(f"详细错误信息:")
            traceback.print_exc()
            return f"LLM调用失败: {str(e)}"
    
    async def close(self):
        """关闭HTTP客户端"""
        if hasattr(self, 'client'):
            await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# 测试功能
async def test_openai_adapter():
    """测试OpenAI适配器"""
    print("🔍 测试OpenAI适配器...")
    
    try:
        from model_config import get_model_config_manager
        
        # 获取OpenAI配置
        config_manager = get_model_config_manager()
        if not config_manager.is_model_available("openai"):
            print("❌ OpenAI模型配置不可用，跳过测试")
            return
            
        config = config_manager._configs["openai"]
        
        # 创建适配器
        async with OpenAIAdapter(config) as adapter:
            # 测试简单聊天
            response = await adapter.simple_chat("Hello, please introduce yourself briefly")
            print(f"✅ 简单聊天测试: {response[:100]}...")
            
            # 测试LangChain消息
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content="You are a professional AI assistant."),
                HumanMessage(content="Explain artificial intelligence briefly")
            ]
            response = await adapter.process_langchain_messages(messages)
            print(f"✅ LangChain消息测试: {response[:100]}...")
            
        print("✅ OpenAI适配器测试完成")
        
    except Exception as e:
        print(f"❌ OpenAI适配器测试失败: {e}")
        print("💡 请检查OPENAI_API_KEY配置和网络连接")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_openai_adapter())