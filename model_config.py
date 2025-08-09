"""
统一模型配置管理器
实现一键切换不同LLM模型的配置管理
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

@dataclass
class ModelConfig:
    """模型配置数据类"""
    api_key: str
    base_url: str
    model_name: str
    temperature: float = 0.3
    max_tokens: int = 1500
    timeout: float = 10.0

class ModelConfigManager:
    """统一模型配置管理器"""
    
    def __init__(self):
        self.active_model = os.getenv("ACTIVE_MODEL", "qwen").lower()
        self._configs = self._load_model_configs()
    
    def _load_model_configs(self) -> Dict[str, ModelConfig]:
        """加载所有支持的模型配置"""
        configs = {}
        
        # Qwen配置
        qwen_key = os.getenv("QWEN_API_KEY")
        if qwen_key:
            configs["qwen"] = ModelConfig(
                api_key=qwen_key,
                base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                model_name=os.getenv("QWEN_MODEL_NAME", "qwen-turbo"),
                temperature=float(os.getenv("QWEN_TEMPERATURE", "0.3")),
                max_tokens=int(os.getenv("QWEN_MAX_TOKENS", "1500"))
            )
        
        # OpenAI配置
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            configs["openai"] = ModelConfig(
                api_key=openai_key,
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo"),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.3")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "1500"))
            )
        
        # Claude配置
        claude_key = os.getenv("CLAUDE_API_KEY")
        if claude_key:
            configs["claude"] = ModelConfig(
                api_key=claude_key,
                base_url=os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com"),
                model_name=os.getenv("CLAUDE_MODEL_NAME", "claude-3-sonnet-20240229"),
                temperature=float(os.getenv("CLAUDE_TEMPERATURE", "0.3")),
                max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "1500"))
            )
        
        # DeepSeek配置
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            configs["deepseek"] = ModelConfig(
                api_key=deepseek_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                model_name=os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat"),
                temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0.3")),
                max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", "1500"))
            )
        
        return configs
    
    def get_active_config(self) -> ModelConfig:
        """获取当前激活的模型配置"""
        if self.active_model not in self._configs:
            available_models = list(self._configs.keys())
            raise ValueError(
                f"模型 '{self.active_model}' 未配置或API密钥缺失。"
                f"可用模型: {available_models}"
            )
        
        return self._configs[self.active_model]
    
    def get_active_model_name(self) -> str:
        """获取当前激活的模型名称"""
        return self.active_model
    
    def list_available_models(self) -> list:
        """列出所有可用的模型"""
        return list(self._configs.keys())
    
    def is_model_available(self, model_name: str) -> bool:
        """检查指定模型是否可用"""
        return model_name.lower() in self._configs
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型的详细信息"""
        config = self.get_active_config()
        return {
            "active_model": self.active_model,
            "model_name": config.model_name,
            "base_url": config.base_url,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "available_models": self.list_available_models()
        }

# 全局配置管理器实例
_config_manager = None

def get_model_config_manager() -> ModelConfigManager:
    """获取全局模型配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ModelConfigManager()
    return _config_manager

def get_active_model_config() -> ModelConfig:
    """获取当前激活的模型配置（便捷方法）"""
    return get_model_config_manager().get_active_config()

def get_active_model_name() -> str:
    """获取当前激活的模型名称（便捷方法）"""
    return get_model_config_manager().get_active_model_name()

# 测试功能
if __name__ == "__main__":
    print("🔍 测试统一模型配置管理器...")
    
    try:
        manager = get_model_config_manager()
        
        print(f"✅ 当前激活模型: {manager.get_active_model_name()}")
        print(f"✅ 可用模型: {manager.list_available_models()}")
        print(f"✅ 模型详细信息: {manager.get_model_info()}")
        
        # 测试获取配置
        config = manager.get_active_config()
        print(f"✅ 当前配置: model_name={config.model_name}, temperature={config.temperature}")
        
    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        print("💡 请检查 .env 文件中的模型配置")