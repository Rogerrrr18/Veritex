"""
语义搜索配置管理器
提供统一的语义搜索相关配置管理
"""
import os
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class SemanticSearchConfig:
    """语义搜索配置管理器"""
    
    def __init__(self):
        # 核心开关
        self.enabled = os.getenv("ENABLE_SEMANTIC_SEARCH", "false").lower() == "true"
        self.enhancement_enabled = os.getenv("ENABLE_SEMANTIC_ENHANCEMENT", "false").lower() == "true"
        
        # 模型配置
        self.model_name = os.getenv("SEMANTIC_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        self.max_sequence_length = int(os.getenv("SEMANTIC_MAX_LENGTH", "512"))
        
        # 搜索参数
        self.top_k_candidates = int(os.getenv("SEMANTIC_TOP_K", "100"))
        self.similarity_threshold = float(os.getenv("SEMANTIC_THRESHOLD", "0.3"))
        self.enhancement_weight = float(os.getenv("SEMANTIC_ENHANCEMENT_WEIGHT", "0.3"))
        
        # 向量数据库配置
        self.vector_db_enabled = os.getenv("ENABLE_VECTOR_DATABASE", "false").lower() == "true"
        self.vector_store_type = os.getenv("VECTOR_STORE_TYPE", "memory").lower()
        self.vector_max_entries = int(os.getenv("VECTOR_STORE_MAX_ENTRIES", "10000"))
        self.vector_persistence = os.getenv("VECTOR_STORE_PERSISTENCE", "false").lower() == "true"
        self.vector_store_path = os.getenv("VECTOR_STORE_PATH", "./data/vector_store.pkl")
        
        # 性能配置
        self.batch_size = int(os.getenv("SEMANTIC_BATCH_SIZE", "32"))
        self.device = os.getenv("SEMANTIC_DEVICE", "cpu")  # cpu, cuda, mps
        self.num_threads = int(os.getenv("SEMANTIC_NUM_THREADS", "4"))
        
        # 缓存配置
        self.enable_model_cache = os.getenv("SEMANTIC_ENABLE_CACHE", "true").lower() == "true"
        self.cache_dir = os.getenv("SEMANTIC_CACHE_DIR", "./cache/semantic_models")
        
        logger.info(f"语义搜索配置初始化完成 - 启用: {self.enabled}")
        
    def get_model_config(self) -> Dict[str, Any]:
        """获取模型配置"""
        return {
            "model_name": self.model_name,
            "max_length": self.max_sequence_length,
            "device": self.device,
            "cache_dir": self.cache_dir if self.enable_model_cache else None,
            "num_threads": self.num_threads
        }
    
    def get_search_config(self) -> Dict[str, Any]:
        """获取搜索配置"""
        return {
            "top_k": self.top_k_candidates,
            "threshold": self.similarity_threshold,
            "enhancement_weight": self.enhancement_weight,
            "batch_size": self.batch_size
        }
    
    def get_vector_db_config(self) -> Dict[str, Any]:
        """获取向量数据库配置"""
        return {
            "enabled": self.vector_db_enabled,
            "store_type": self.vector_store_type,
            "max_entries": self.vector_max_entries,
            "persistence": self.vector_persistence,
            "store_path": self.vector_store_path
        }
    
    def validate_dependencies(self) -> Dict[str, bool]:
        """验证依赖是否满足"""
        dependencies = {
            "sentence_transformers": False,
            "scikit_learn": False,
            "numpy": False,
            "torch": False
        }
        
        try:
            import sentence_transformers
            dependencies["sentence_transformers"] = True
        except ImportError:
            pass
        
        try:
            import sklearn
            dependencies["scikit_learn"] = True
        except ImportError:
            pass
        
        try:
            import numpy
            dependencies["numpy"] = True
        except ImportError:
            pass
        
        try:
            import torch
            dependencies["torch"] = True
        except ImportError:
            pass
        
        return dependencies
    
    def get_missing_dependencies(self) -> List[str]:
        """获取缺失的依赖"""
        dependencies = self.validate_dependencies()
        missing = []
        
        required_deps = ["sentence_transformers", "scikit_learn", "numpy"]
        
        for dep in required_deps:
            if not dependencies.get(dep, False):
                missing.append(dep)
        
        return missing
    
    def is_ready(self) -> bool:
        """检查语义搜索是否准备就绪"""
        if not self.enabled:
            return True  # 如果未启用，认为是准备就绪的
        
        missing_deps = self.get_missing_dependencies()
        return len(missing_deps) == 0
    
    def get_installation_command(self) -> str:
        """获取安装缺失依赖的命令"""
        missing = self.get_missing_dependencies()
        if not missing:
            return ""
        
        package_mapping = {
            "sentence_transformers": "sentence-transformers",
            "scikit_learn": "scikit-learn",
            "numpy": "numpy"
        }
        
        packages = [package_mapping.get(dep, dep) for dep in missing]
        return f"pip install {' '.join(packages)}"
    
    def get_status_report(self) -> Dict[str, Any]:
        """获取完整状态报告"""
        dependencies = self.validate_dependencies()
        missing = self.get_missing_dependencies()
        
        return {
            "semantic_search_enabled": self.enabled,
            "enhancement_enabled": self.enhancement_enabled,
            "vector_database_enabled": self.vector_db_enabled,
            "model_name": self.model_name,
            "device": self.device,
            "dependencies": dependencies,
            "missing_dependencies": missing,
            "ready": self.is_ready(),
            "installation_command": self.get_installation_command()
        }
    
    def log_status(self):
        """记录配置状态到日志"""
        status = self.get_status_report()
        
        if status["ready"]:
            logger.info("✅ 语义搜索系统配置完整")
            if status["semantic_search_enabled"]:
                logger.info(f"🧠 模型: {status['model_name']}")
                logger.info(f"🖥️ 设备: {status['device']}")
        else:
            logger.warning("⚠️ 语义搜索系统配置不完整")
            if status["missing_dependencies"]:
                logger.warning(f"缺失依赖: {', '.join(status['missing_dependencies'])}")
                logger.info(f"安装命令: {status['installation_command']}")

# 全局配置实例
semantic_config = SemanticSearchConfig()

def get_semantic_config() -> SemanticSearchConfig:
    """获取语义搜索配置实例"""
    return semantic_config

def check_semantic_search_ready() -> bool:
    """快速检查语义搜索是否可用"""
    return semantic_config.is_ready()

def print_semantic_status():
    """打印语义搜索状态"""
    status = semantic_config.get_status_report()
    
    print("🔍 语义搜索系统状态:")
    print(f"  启用语义搜索: {'✅' if status['semantic_search_enabled'] else '❌'}")
    print(f"  启用查询增强: {'✅' if status['enhancement_enabled'] else '❌'}")
    print(f"  启用向量数据库: {'✅' if status['vector_database_enabled'] else '❌'}")
    print(f"  模型: {status['model_name']}")
    print(f"  设备: {status['device']}")
    
    print("\n📦 依赖状态:")
    for dep, available in status["dependencies"].items():
        status_icon = "✅" if available else "❌"
        print(f"  {dep}: {status_icon}")
    
    if status["missing_dependencies"]:
        print(f"\n⚠️ 缺失依赖: {', '.join(status['missing_dependencies'])}")
        print(f"💡 安装命令: {status['installation_command']}")
    
    print(f"\n🚀 系统就绪: {'✅' if status['ready'] else '❌'}")

if __name__ == "__main__":
    print_semantic_status()