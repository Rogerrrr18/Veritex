"""
千问大模型API调用封装
"""
import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Optional

load_dotenv()

class QwenAPI:
    def __init__(self):
        self.api_key = os.getenv("QWEN_API_KEY", "sk-7ec5107d41af4d809d702303013be7f7”)
        self.base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "qwen-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Optional[str]:
        """
        调用千问聊天完成API
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            model: 模型名称
            temperature: 生成温度
            max_tokens: 最大令牌数
            
        Returns:
            生成的回复文本，出错时返回None
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
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                print(f"API响应格式异常: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"API调用失败: {e}")
            return None
        except Exception as e:
            print(f"处理响应时出错: {e}")
            return None
    
    def simple_chat(self, user_input: str, history: List[Dict[str, str]] = None) -> str:
        """
        简单聊天接口
        
        Args:
            user_input: 用户输入
            history: 历史对话记录
            
        Returns:
            AI回复
        """
        if history is None:
            history = []
        
        messages = history + [{"role": "user", "content": user_input}]
        
        response = self.chat_completion(messages)
        if response:
            return response
        else:
            return "抱歉，我现在无法回复。请稍后再试。"