"""
Doubao (字节火山方舟 Ark) 模型适配器
兼容 /api/v3/chat/completions 接口，支持文本与多模态消息格式
"""
import httpx
from typing import List, Dict, Optional, Any
from langchain_core.messages import BaseMessage

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from llm_interface import BaseLLMAdapter
from model_config import ModelConfig


def _to_ark_message_content(content: Any) -> Any:
    """将内部 content 标准化为 Ark 所需的数组格式。
    - 若为字符串，则包装为 [{"type": "text", "text": content}]
    - 若已是数组(多模态)，直接返回
    - 其他类型，转字符串后按文本处理
    """
    if isinstance(content, list):
        return content
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [{"type": "text", "text": str(content)}]


class DoubaoAdapter(BaseLLMAdapter):
    """Doubao模型适配器 (Ark Chat Completions v3)"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, Any]], 
        **kwargs
    ) -> Optional[str]:
        """
        Doubao 聊天完成API调用 (/api/v3/chat/completions)
        支持将纯文本消息自动转换为 Ark 多模态 content 数组格式
        """
        if not self.config.api_key:
            raise ValueError("ARK_API_KEY 或 DOUBAO_API_KEY 未设置，请检查 .env 文件")
        
        # 将消息转换为 Ark 期望的 content 数组格式
        ark_messages: List[Dict[str, Any]] = []
        for m in messages:
            ark_messages.append({
                "role": m.get("role", "user"),
                "content": _to_ark_message_content(m.get("content", ""))
            })
        
        payload = {
            "model": self.model_name,
            "messages": ark_messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": False
        }
        
        try:
            url = f"{self.config.base_url}/api/v3/chat/completions"
            response = await self.client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            # Ark 返回可能为多种结构：
            # 1) choices[0].message.content 为字符串
            # 2) choices[0].message.content 为数组([{type, text}])
            # 3) choices[0].message 为字符串(兼容模式，极少数场景)
            try:
                choice = (data.get("choices") or [])[0]
            except Exception:
                return None
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    return "\n".join([t for t in texts if t]) or None
                # 兜底
                return str(content) if content is not None else None
            elif isinstance(message, str):
                return message
            else:
                # 尝试 choices[0].message.content.text
                try:
                    return choice["message"]["content"][0]["text"]
                except Exception:
                    pass
            return None
        except httpx.HTTPError as e:
            print(f"Doubao API调用失败: {e}")
            print(f"HTTP状态码: {getattr(e.response, 'status_code', 'N/A') if hasattr(e, 'response') and e.response else 'N/A'}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"响应内容: {e.response.text[:500]}")
                except Exception:
                    pass
            return None
        except Exception as e:
            print(f"Doubao处理响应时出错: {e}")
            return None
    
    async def simple_chat(self, user_input: str, history: List[Dict[str, Any]] = None) -> str:
        if history is None:
            history = []
        messages = history + [{"role": "user", "content": user_input}]
        response = await self.chat_completion(messages)
        return response if response else "抱歉，我现在无法回复。请稍后再试。"
    
    async def process_langchain_messages(self, messages: List[BaseMessage]) -> str:
        try:
            converted = self._convert_langchain_messages_to_dict(messages)
            response = await self.chat_completion(converted)
            return response if response else "抱歉，我现在无法回复。请稍后再试。"
        except Exception as e:
            print(f"Doubao LangChain消息处理错误: {e}")
            import traceback
            traceback.print_exc()
            return f"LLM调用失败: {str(e)}"
    
    async def close(self):
        if hasattr(self, 'client'):
            await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    
async def test_doubao_adapter():
    """测试Doubao适配器"""
    print("🔍 测试Doubao适配器...")
    try:
        from model_config import get_model_config_manager
        config_manager = get_model_config_manager()
        if not config_manager.is_model_available("doubao"):
            print("❌ Doubao模型配置不可用，跳过测试")
            return
        config = config_manager._configs["doubao"]
        async with DoubaoAdapter(config) as adapter:
            response = await adapter.simple_chat("你好，请介绍一下你自己")
            print(f"✅ 简单聊天测试: {response[:100]}...")
            from langchain_core.messages import SystemMessage, HumanMessage
            msgs = [
                SystemMessage(content="你是一个专业的AI助手。"),
                HumanMessage(content="请简单解释什么是人工智能")
            ]
            response = await adapter.process_langchain_messages(msgs)
            print(f"✅ LangChain消息测试: {response[:100]}...")
        print("✅ Doubao适配器测试完成")
    except Exception as e:
        print(f"❌ Doubao适配器测试失败: {e}")
        print("💡 请检查 ARK_API_KEY/DOUBAO_API_KEY 与网络连接")
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_doubao_adapter())


