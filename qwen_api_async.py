"""
千问大模型异步API调用封装 (性能优化版)
"""
import os
import httpx
import asyncio
from dotenv import load_dotenv
from typing import List, Dict, Optional

load_dotenv()

class QwenAPIAsync:
    def __init__(self):
        self.api_key = os.getenv("QWEN_API_KEY")
        self.base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # 创建异步HTTP客户端，使用连接池
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),  # 减少超时时间
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "qwen-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Optional[str]:
        """
        异步调用千问聊天完成API
        """
        if not self.api_key:
            raise ValueError("QWEN_API_KEY 未设置，请检查 .env 文件")
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                print(f"API响应格式异常: {result}")
                return None
                
        except httpx.HTTPError as e:
            print(f"API调用失败: {e}")
            print(f"HTTP状态码: {getattr(e, 'response', {}).get('status_code', 'N/A')}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"响应内容: {e.response.text[:500]}")
                except:
                    pass
            return None
        except Exception as e:
            print(f"处理响应时出错: {e}")
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
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# 全局异步客户端实例
_qwen_client = None

async def get_qwen_client() -> QwenAPIAsync:
    """获取全局异步客户端实例"""
    global _qwen_client
    if _qwen_client is None:
        _qwen_client = QwenAPIAsync()
    return _qwen_client