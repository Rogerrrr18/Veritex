"""
Doubao (字节火山方舟 Ark) 模型适配器
集成官方火山引擎SDK，支持多轮对话和上下文记忆
支持文本与多模态消息格式
"""
import os
import sys
import httpx
from typing import List, Dict, Optional, Any
from langchain_core.messages import BaseMessage

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from llm_interface import BaseLLMAdapter
from model_config import ModelConfig

# 尝试导入火山引擎官方SDK
try:
    from volcenginesdkarkruntime import Ark
    VOLCANO_SDK_AVAILABLE = True
    print("✅ 火山引擎官方SDK已加载")
except ImportError:
    VOLCANO_SDK_AVAILABLE = False
    print("⚠️ 火山引擎官方SDK未安装，将使用HTTP客户端")


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
    """Doubao模型适配器 - 支持官方SDK和多轮对话"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.use_official_sdk = VOLCANO_SDK_AVAILABLE
        
        # 初始化官方SDK客户端（如果可用）
        if self.use_official_sdk:
            self.ark_client = Ark(api_key=config.api_key)
            print("🚀 使用火山引擎官方SDK")
        else:
            # 降级到HTTP客户端
            self.headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json"
            }
            # 优化HTTP客户端配置
            timeout_config = httpx.Timeout(
                connect=10.0, read=120.0, write=30.0, pool=10.0
            )
            limits_config = httpx.Limits(
                max_keepalive_connections=15,
                max_connections=25,
                keepalive_expiry=30.0
            )
            self.client = httpx.AsyncClient(
                timeout=timeout_config,
                limits=limits_config,
                http2=True
            )
            print("📡 使用HTTP客户端模式")
        
        # 对话历史缓存
        self._conversation_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_limit = 50  # 每个对话保留最多50轮历史
    
    def _add_to_conversation_cache(self, conversation_id: str, messages: List[Dict[str, Any]]):
        """将消息添加到对话缓存"""
        if conversation_id not in self._conversation_cache:
            self._conversation_cache[conversation_id] = []
        
        # 添加新消息并保持缓存限制
        self._conversation_cache[conversation_id].extend(messages)
        if len(self._conversation_cache[conversation_id]) > self._cache_limit:
            # 保留系统消息和最近的消息
            system_msgs = [msg for msg in self._conversation_cache[conversation_id] if msg.get("role") == "system"]
            recent_msgs = [msg for msg in self._conversation_cache[conversation_id] if msg.get("role") != "system"]
            recent_msgs = recent_msgs[-(self._cache_limit - len(system_msgs)):]
            self._conversation_cache[conversation_id] = system_msgs + recent_msgs
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self._conversation_cache.get(conversation_id, [])
    
    def clear_conversation_cache(self, conversation_id: str = None):
        """清空对话缓存"""
        if conversation_id:
            self._conversation_cache.pop(conversation_id, None)
        else:
            self._conversation_cache.clear()
    
    async def chat_with_history(
        self, 
        message: str, 
        conversation_id: str = "default",
        system_prompt: str = None,
        **kwargs
    ) -> Optional[str]:
        """支持历史的多轮对话"""
        # 构建完整的消息列表
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加历史消息
        history = self.get_conversation_history(conversation_id)
        messages.extend(history)
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": message})
        
        # 调用聊天完成
        response = await self.chat_completion(messages, **kwargs)
        
        if response:
            # 将用户消息和AI回复添加到缓存
            self._add_to_conversation_cache(conversation_id, [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response}
            ])
        
        return response
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, Any]], 
        **kwargs
    ) -> Optional[str]:
        """
        Doubao 聊天完成API调用
        支持官方SDK和HTTP客户端两种模式
        """
        if not self.config.api_key:
            raise ValueError("ARK_API_KEY 或 DOUBAO_API_KEY 未设置，请检查 .env 文件")
        
        # 使用官方SDK（优先）
        if self.use_official_sdk:
            return await self._chat_completion_sdk(messages, **kwargs)
        else:
            return await self._chat_completion_http(messages, **kwargs)
    
    async def _chat_completion_sdk(
        self, 
        messages: List[Dict[str, Any]], 
        **kwargs
    ) -> Optional[str]:
        """使用官方火山引擎SDK进行聊天完成"""
        try:
            # 转换消息格式为SDK期望的格式
            sdk_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # 豆包系统消息格式
                if role == "system":
                    sdk_messages.append({
                        "role": "system",
                        "content": content
                    })
                elif role == "user":
                    sdk_messages.append({
                        "role": "user", 
                        "content": content
                    })
                elif role == "assistant":
                    sdk_messages.append({
                        "role": "assistant",
                        "content": content
                    })
            
            # 调用官方SDK
            completion = self.ark_client.chat.completions.create(
                model=self.model_name,
                messages=sdk_messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stream=False
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            print(f"官方SDK调用失败: {e}")
            # 降级到HTTP客户端
            print("🔄 降级到HTTP客户端模式")
            return await self._chat_completion_http(messages, **kwargs)
    
    async def _chat_completion_http(
        self, 
        messages: List[Dict[str, Any]], 
        **kwargs
    ) -> Optional[str]:
        """使用HTTP客户端进行聊天完成"""
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
                return str(content) if content is not None else None
            elif isinstance(message, str):
                return message
            else:
                try:
                    return choice["message"]["content"][0]["text"]
                except Exception:
                    pass
            return None
            
        except httpx.HTTPError as e:
            print(f"HTTP客户端调用失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"响应内容: {e.response.text[:500]}")
                except Exception:
                    pass
            return None
        except Exception as e:
            print(f"HTTP客户端处理响应时出错: {e}")
            return None

    async def chat_completion_stream(
        self, 
        messages: List[Dict[str, Any]], 
        **kwargs
    ):
        """
        Doubao 流式聊天完成API调用
        返回一个异步生成器，逐步生成响应内容
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
            "stream": True  # 启用流式输出
        }
        
        try:
            url = f"{self.config.base_url}/api/v3/chat/completions"
            
            async with self.client.stream('POST', url, headers=self.headers, json=payload) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 处理SSE格式：data: {...}
                    if line.startswith('data: '):
                        data_str = line[6:]  # 移除 'data: ' 前缀
                        
                        # 检查是否为结束标志
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            import json
                            data = json.loads(data_str) if data_str.startswith('{') else None
                            if not data:
                                continue
                                
                            # 解析流式响应数据
                            choices = data.get('choices', [])
                            if not choices:
                                continue
                                
                            delta = choices[0].get('delta', {})
                            content = delta.get('content')
                            
                            if content:
                                # 处理content的不同格式
                                if isinstance(content, str):
                                    yield content
                                elif isinstance(content, list):
                                    # 处理多模态content数组格式
                                    for item in content:
                                        if isinstance(item, dict) and item.get('type') == 'text':
                                            text = item.get('text', '')
                                            if text:
                                                yield text
                                                
                        except Exception as e:
                            print(f"解析流式响应数据失败: {e}")
                            continue
                
        except httpx.HTTPError as e:
            print(f"Doubao 流式API调用失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"响应内容: {e.response.text[:500]}")
                except Exception:
                    pass
            raise
        except Exception as e:
            print(f"Doubao 流式处理出错: {e}")
            raise
    
    async def simple_chat(self, user_input: str, history: List[Dict[str, Any]] = None) -> str:
        """简单聊天接口 - 支持历史记录"""
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


