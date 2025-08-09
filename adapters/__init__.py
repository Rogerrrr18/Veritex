"""
LLM适配器模块
为不同的模型提供统一接口的适配器实现
"""

# 导入所有可用的适配器
from .qwen_adapter import QwenAdapter

__all__ = [
    "QwenAdapter",
]

# 动态导入其他适配器（避免导入错误）
try:
    from .openai_adapter import OpenAIAdapter
    __all__.append("OpenAIAdapter")
except ImportError:
    pass

try:
    from .claude_adapter import ClaudeAdapter  
    __all__.append("ClaudeAdapter")
except ImportError:
    pass

try:
    from .deepseek_adapter import DeepSeekAdapter
    __all__.append("DeepSeekAdapter")
except ImportError:
    pass