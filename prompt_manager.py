"""
智能Prompt管理器
实现模块化prompt系统、缓存机制和动态选择
"""
import os
import hashlib
from typing import Dict, Optional, Tuple
from enum import Enum
from functools import lru_cache

class PromptType(Enum):
    """Prompt类型枚举"""
    BASE = "base"                    # 基础判断prompt
    CONVERSATION = "conversation"     # 普通对话prompt  
    SIMPLE_ACADEMIC = "simple_academic"   # 简单学术分析
    ADVANCED_ACADEMIC = "advanced_academic"  # 高级学术分析

class QueryComplexity(Enum):
    """查询复杂度枚举"""
    SIMPLE = "simple"       # 简单查询：1-2个关键词
    MEDIUM = "medium"       # 中等查询：3-5个关键词或包含修饰词
    COMPLEX = "complex"     # 复杂查询：多概念组合或特殊需求

class PromptManager:
    """智能Prompt管理器"""
    
    def __init__(self):
        self.prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self._prompt_cache: Dict[str, str] = {}
        self._ensure_prompt_dir()
        
    def _ensure_prompt_dir(self):
        """确保prompt目录存在"""
        if not os.path.exists(self.prompt_dir):
            os.makedirs(self.prompt_dir)
    
    @lru_cache(maxsize=32)
    def _load_prompt_template(self, prompt_type: PromptType) -> str:
        """加载prompt模板（带缓存）"""
        filename = f"{prompt_type.value}_prompt.txt"
        file_path = os.path.join(self.prompt_dir, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"⚠️  Prompt文件未找到: {file_path}")
            return self._get_fallback_prompt(prompt_type)
        except Exception as e:
            print(f"❌ 加载prompt文件失败: {e}")
            return self._get_fallback_prompt(prompt_type)
    
    def _get_fallback_prompt(self, prompt_type: PromptType) -> str:
        """获取fallback prompt"""
        fallbacks = {
            PromptType.BASE: "你是学术检索分析专家。分析用户查询：{user_query}",
            PromptType.CONVERSATION: "请自然友好地回应用户：{user_query}",
            PromptType.SIMPLE_ACADEMIC: "分析学术查询并提供关键词：{user_query}",
            PromptType.ADVANCED_ACADEMIC: "深度分析学术查询：{user_query}"
        }
        return fallbacks.get(prompt_type, "请分析：{user_query}")
    
    def _cache_key(self, prompt_type: PromptType, user_query: str) -> str:
        """生成缓存键"""
        content = f"{prompt_type.value}:{user_query}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def analyze_query_complexity(self, query: str) -> QueryComplexity:
        """分析查询复杂度"""
        query_clean = query.strip().lower()
        
        # 计算关键指标
        word_count = len(query_clean.split())
        
        # 复杂度指示词
        complex_indicators = [
            "机理", "机制", "原理", "mechanism", "principle",
            "综述", "review", "survey", "比较", "对比", "comparison",
            "最新", "进展", "recent", "advances", "发展", "evolution",
            "挑战", "问题", "challenge", "limitation", "优化", "optimization"
        ]
        
        # 专业术语密度检测
        tech_terms = [
            "算法", "模型", "方法", "技术", "系统", "框架",
            "algorithm", "model", "method", "technique", "system", "framework",
            "分析", "研究", "analysis", "research", "study", "investigation"
        ]
        
        complex_count = sum(1 for indicator in complex_indicators if indicator in query_clean)
        tech_count = sum(1 for term in tech_terms if term in query_clean)
        
        # 复杂度判断逻辑
        if word_count <= 3 and complex_count == 0:
            return QueryComplexity.SIMPLE
        elif word_count <= 8 and complex_count <= 1 and tech_count <= 2:
            return QueryComplexity.MEDIUM
        else:
            return QueryComplexity.COMPLEX
    
    def detect_query_type(self, query: str) -> Tuple[bool, QueryComplexity]:
        """检测查询类型：(是否学术查询, 复杂度)"""
        query_clean = query.strip().lower()
        
        # 学术检索特征词
        academic_indicators = [
            # 中文学术词汇
            "研究", "分析", "探索", "文献", "论文", "期刊", "学术", "科研",
            "方法", "算法", "模型", "技术", "系统", "理论", "机理", "机制",
            "实验", "测试", "评估", "性能", "效果", "应用", "发展", "进展",
            "重整", "催化", "合成", "制备", "氧化", "还原", "反应", "工艺",  # 化学工程术语
            "甲烷", "氢气", "一氧化碳", "二氧化碳", "天然气", "裂解", "转化",  # 化学物质和过程
            # 英文学术词汇  
            "research", "study", "analysis", "investigation", "paper", "literature",
            "method", "algorithm", "model", "technique", "system", "theory",
            "mechanism", "experiment", "performance", "application", "development",
            "reforming", "catalysis", "synthesis", "methane", "hydrogen", "carbon"
        ]
        
        # 普通对话特征词
        conversation_indicators = [
            "你好", "谢谢", "感谢", "不好意思", "请问", "怎么样", "怎么办",
            "心情", "感觉", "困扰", "开心", "难过", "帮助", "功能", "使用",
            "hello", "thanks", "thank you", "sorry", "how", "feel", "mood"
        ]
        
        # 计算匹配度
        academic_score = sum(1 for word in academic_indicators if word in query_clean)
        conversation_score = sum(1 for word in conversation_indicators if word in query_clean)
        
        # 判断逻辑
        is_academic = academic_score > conversation_score and academic_score > 0
        complexity = self.analyze_query_complexity(query) if is_academic else QueryComplexity.SIMPLE
        
        return is_academic, complexity
    
    def select_optimal_prompt(self, query: str) -> PromptType:
        """基于查询智能选择最优prompt"""
        is_academic, complexity = self.detect_query_type(query)
        
        if not is_academic:
            return PromptType.CONVERSATION
        
        # 学术查询根据复杂度选择
        if complexity == QueryComplexity.SIMPLE:
            return PromptType.SIMPLE_ACADEMIC
        elif complexity == QueryComplexity.MEDIUM:
            return PromptType.SIMPLE_ACADEMIC  # 中等复杂度仍用简单模板
        else:
            return PromptType.ADVANCED_ACADEMIC  # 仅最复杂的查询使用高级模板
    
    def get_prompt(self, query: str, force_type: Optional[PromptType] = None) -> str:
        """获取处理后的prompt（带缓存）"""
        # 确定prompt类型
        prompt_type = force_type or self.select_optimal_prompt(query)
        
        # 检查缓存
        cache_key = self._cache_key(prompt_type, query)
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]
        
        # 加载模板并格式化
        template = self._load_prompt_template(prompt_type)
        formatted_prompt = template.format(user_query=query)
        
        # 缓存结果
        self._prompt_cache[cache_key] = formatted_prompt
        
        # 输出调试信息
        print(f"🎯 选择Prompt: {prompt_type.value} (查询长度: {len(query)}字符)")
        print(f"📏 Prompt长度: {len(formatted_prompt)}字符")
        
        return formatted_prompt
    
    def get_base_prompt(self, query: str) -> str:
        """获取基础判断prompt"""
        return self.get_prompt(query, PromptType.BASE)
    
    def clear_cache(self):
        """清空prompt缓存"""
        self._prompt_cache.clear()
        self._load_prompt_template.cache_clear()
        print("🧹 Prompt缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self._prompt_cache),
            "template_cache_info": self._load_prompt_template.cache_info()._asdict()
        }

# 全局实例
_prompt_manager = None

def get_prompt_manager() -> PromptManager:
    """获取全局prompt管理器实例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager

# 便捷函数
def get_optimal_prompt(query: str) -> str:
    """获取最优prompt（便捷函数）"""
    return get_prompt_manager().get_prompt(query)

def detect_query_intent(query: str) -> Tuple[bool, str]:
    """检测查询意图（便捷函数）"""
    manager = get_prompt_manager()
    is_academic, complexity = manager.detect_query_type(query)
    return is_academic, complexity.value

if __name__ == "__main__":
    # 测试prompt管理器
    print("🔍 测试智能Prompt管理器...")
    
    test_queries = [
        "你好，这个系统怎么使用？",
        "甲烷干重整",
        "我想查找关于机器学习在医疗诊断中应用的最新研究",
        "深度学习和传统机器学习方法在图像识别性能上的比较分析研究"
    ]
    
    manager = get_prompt_manager()
    
    for query in test_queries:
        print(f"\n📝 查询: {query}")
        is_academic, complexity = manager.detect_query_type(query)
        prompt_type = manager.select_optimal_prompt(query)
        prompt = manager.get_prompt(query)
        
        print(f"🎯 学术查询: {is_academic}, 复杂度: {complexity.value}")
        print(f"📋 选择Prompt: {prompt_type.value}")
        print(f"📏 Prompt长度: {len(prompt)}字符")
        
    print(f"\n📊 缓存统计: {manager.get_cache_stats()}")
    print("✅ 测试完成")