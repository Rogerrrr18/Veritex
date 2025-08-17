"""
优化的LLM意图分类器
去除embedding步骤，直接使用LLM + 规则降级的两阶段方案
提升响应速度，简化系统架构
"""
import os
import json
import asyncio
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from functools import lru_cache

import llm_interface

@dataclass
class IntentResult:
    """意图识别结果"""
    intent: str  # "查文献", "闲聊", "学术探讨"
    confidence: float  # 置信度 0-1
    method: str  # "llm", "rule"
    response: Optional[str] = None  # LLM生成的回复（如适用）
    reasoning: Optional[str] = None  # 分类原因

class LLMIntentClassifier:
    """优化的LLM意图分类器 - 高效两阶段分类"""
    
    def __init__(self):
        # 配置参数
        self.cache_size = 1000
        
        # 缓存
        self.result_cache = {}
        
        # LLM接口
        self.llm = None
        
        print("✅ 使用优化的LLM意图分类器（已移除embedding步骤）")
        
    async def _llm_classify(self, query: str) -> IntentResult:
        """LLM智能分类"""
        try:
            if not self.llm:
                self.llm = await llm_interface.get_universal_llm()
            
            # 构建优化的分类prompt
            prompt = self._build_classification_prompt(query)
            
            # 调用LLM
            response = await self.llm.simple_chat(prompt)
            return self._parse_llm_response(response, query)
            
        except Exception as e:
            print(f"❌ LLM分类失败: {e}")
            # 降级到规则分类
            return self._rule_classify(query)
    
    def _build_classification_prompt(self, query: str) -> str:
        """构建优化的LLM分类prompt"""
        prompt = f"""你是一个专业的意图分类专家。请准确判断用户查询的意图类别。

三个意图类别定义：

1. **查文献**：用户明确要求搜索、查找、检索学术论文或文献
   - 特征：包含"找"、"搜索"、"检索"、"查找"、"文献"、"论文"、"paper"、"研究"等词
   - 示例：
     * "帮我找关于量子计算的最新论文"
     * "搜索机器学习算法文献" 
     * "我想查询关于智能体开发相关的研究"
     * "甲烷干重整催化剂研究"

2. **闲聊**：日常对话、问候、感谢、系统使用咨询等非学术内容
   - 特征：情感表达、礼貌用语、系统操作问题
   - 示例：
     * "你好，谢谢你的帮助"
     * "这个系统怎么使用？"
     * "今天天气真好啊"

3. **学术探讨**：对学术问题的讨论、提问、观点交流，但不要求搜索文献
   - 特征：以疑问句形式探讨学术概念、理论、现象，不包含搜索意图
   - 示例：
     * "量子纠缠能不能用来超光速通信？"
     * "人工智能会取代人类吗？"
     * "甲烷干重整的机理是什么？"

⚠️ 重要判断标准：
- 如果查询中包含明确的搜索意图词汇（找、搜索、检索、查询、研究等），优先归类为"查文献"
- 只有当查询是纯粹的学术讨论或疑问，且没有搜索意图时，才归类为"学术探讨"
- "研究"相关的查询通常是要搜索文献的需求

用户查询："{query}"

请按以下JSON格式回复：
```json
{{
  "intent": "查文献|闲聊|学术探讨",
  "confidence": 0.95,
  "reasoning": "详细的分类原因说明"
}}
```"""
        
        return prompt
    
    def _parse_llm_response(self, response: str, query: str) -> IntentResult:
        """解析LLM分类响应"""
        try:
            # 提取JSON
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group(1))
                
                return IntentResult(
                    intent=result_data.get("intent", "闲聊"),
                    confidence=result_data.get("confidence", 0.8),
                    method="llm",
                    reasoning=result_data.get("reasoning", "LLM智能分类"),
                    response=response if result_data.get("intent") == "闲聊" else None
                )
            else:
                print("⚠️ LLM响应格式解析失败，使用规则降级方案")
                return self._rule_classify(query)
                
        except Exception as e:
            print(f"❌ LLM响应解析失败: {e}")
            return self._rule_classify(query)
    
    def _rule_classify(self, query: str) -> IntentResult:
        """规则降级分类方案（优化版本）"""
        query_lower = query.lower()
        query_clean = query.strip()
        
        # 查文献关键词（扩展和优化）
        search_keywords = [
            # 直接搜索词汇
            "找", "搜索", "检索", "查找", "查询", "寻找", "搜", "查",
            # 英文搜索词汇
            "find", "search", "lookup", "retrieve",
            # 中文文献词汇
            "文献", "论文", "paper", "研究", "文章", "资料", "材料",
            # 搜索句式
            "帮我找", "请检索", "我需要", "我想找", "我要找", "需要一些",
            "查一下", "搜一下", "找一下", "看看", "了解", "获取",
            # 学术领域词汇（当与搜索意图结合时）
            "催化剂", "算法", "技术", "方法", "模型", "系统", "理论",
            "机器学习", "深度学习", "人工智能", "量子计算", "神经网络",
            "数据挖掘", "计算机视觉", "自然语言处理", "智能体"
        ]
        
        # 闲聊关键词
        chat_keywords = [
            "你好", "谢谢", "感谢", "再见", "拜拜", "hello", "hi", "thanks", "thank you",
            "怎么用", "怎么使用", "如何使用", "使用方法", "操作指南", "帮助",
            "功能", "界面", "系统", "你是谁", "你能做什么", "什么功能",
            "天气", "心情", "今天", "明天", "周末", "假期", "电影", "音乐"
        ]
        
        # 学术探讨特征词汇
        question_words = [
            "什么", "如何", "为什么", "能否", "是否", "怎样", "会不会", "能不能",
            "what", "how", "why", "can", "will", "could", "would",
            "是不是", "会", "能", "看待", "认为", "觉得", "评价"
        ]
        
        academic_concepts = [
            "机理", "原理", "理论", "概念", "现象", "问题", "挑战", "前景", "趋势",
            "发展", "影响", "应用", "突破", "创新", "未来", "可能性", "意义"
        ]
        
        # 计算匹配得分
        search_score = sum(1 for kw in search_keywords if kw in query_lower)
        chat_score = sum(1 for kw in chat_keywords if kw in query_lower)
        
        # 学术探讨检测
        has_question = any(qw in query_lower for qw in question_words)
        has_academic_concept = any(ac in query_lower for ac in academic_concepts)
        is_question_form = query_clean.endswith('？') or query_clean.endswith('?')
        
        # 特殊关键词检测
        has_academic_term = any(term in query_lower for term in [
            "机器学习", "深度学习", "人工智能", "量子", "神经网络", "算法",
            "催化", "重整", "材料", "化学", "物理", "生物", "医学", "智能体"
        ])
        
        # 明确的搜索意图检测
        explicit_search_intent = any(word in query_lower for word in [
            "找", "搜索", "检索", "查找", "查询", "我需要", "帮我", "寻找",
            "我想找", "我要", "给我", "提供", "获取"
        ])
        
        # 分类逻辑（优化后更精确）
        if search_score >= 2 or explicit_search_intent:
            # 强搜索意图
            return IntentResult(
                intent="查文献",
                confidence=min(0.85 + search_score * 0.05, 0.95),
                method="rule",
                reasoning=f"明确搜索意图，匹配{search_score}个搜索关键词"
            )
        elif has_academic_term and (explicit_search_intent or "研究" in query_lower):
            # 学术术语 + 搜索意图
            return IntentResult(
                intent="查文献",
                confidence=0.85,
                method="rule",
                reasoning="包含学术术语且有搜索意图"
            )
        elif chat_score > 0:
            return IntentResult(
                intent="闲聊", 
                confidence=min(0.8 + chat_score * 0.05, 0.9),
                method="rule",
                reasoning=f"日常对话，匹配{chat_score}个对话关键词"
            )
        elif (has_question or is_question_form) and has_academic_concept:
            # 学术探讨：有疑问词 + 学术概念，但无明确搜索意图
            return IntentResult(
                intent="学术探讨",
                confidence=0.8,
                method="rule", 
                reasoning="学术疑问形式，无明确搜索意图"
            )
        elif has_academic_term and not explicit_search_intent:
            # 仅提及学术概念，无搜索意图
            return IntentResult(
                intent="学术探讨",
                confidence=0.7,
                method="rule",
                reasoning="包含学术概念但无明确搜索意图"
            )
        else:
            # 默认归类为闲聊
            return IntentResult(
                intent="闲聊",
                confidence=0.6,
                method="rule",
                reasoning="未明确匹配，默认对话模式"
            )
    
    async def classify_intent(self, query: str) -> IntentResult:
        """主要分类接口：LLM智能分类 + 规则降级"""
        print(f"🔍 开始意图分析: {query}")
        
        # 检查结果缓存
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.result_cache:
            cached_result = self.result_cache[cache_key]
            print(f"✅ 命中缓存: {cached_result.intent} ({cached_result.confidence:.3f})")
            return cached_result
        
        # 直接使用LLM分类（无embedding步骤）
        print("🤖 使用LLM智能分类...")
        result = await self._llm_classify(query)
        
        # 缓存结果
        if len(self.result_cache) >= self.cache_size:
            # 简单LRU：删除最老的一半
            keys_to_remove = list(self.result_cache.keys())[:self.cache_size//2]
            for key in keys_to_remove:
                del self.result_cache[key]
        
        self.result_cache[cache_key] = result
        
        print(f"✅ 最终分类结果: {result.intent} (置信度: {result.confidence:.3f}, 方法: {result.method})")
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取分类器统计信息"""
        return {
            "classifier_type": "llm_optimized",
            "embedding_removed": True,
            "result_cache_size": len(self.result_cache),
            "cache_size_limit": self.cache_size,
            "classification_methods": ["llm", "rule"]
        }

# 全局实例
_intent_classifier = None

def get_intent_classifier() -> LLMIntentClassifier:
    """获取全局意图分类器实例"""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = LLMIntentClassifier()
    return _intent_classifier

# 测试功能
async def test_intent_classifier():
    """测试优化的意图分类器"""
    print("🔍 测试优化的LLM意图分类器...")
    
    classifier = get_intent_classifier()
    
    test_queries = [
        "我想查询关于智能体开发相关的研究",  # 应该是查文献
        "帮我找关于机器学习的最新论文",      # 应该是查文献
        "你好，今天天气怎么样？",           # 应该是闲聊
        "量子计算能解决什么问题？",         # 应该是学术探讨
        "甲烷干重整催化剂研究",             # 应该是查文献（研究意图）
        "谢谢你的帮助",                    # 应该是闲聊
        "人工智能会取代人类吗？",           # 应该是学术探讨
        "搜索深度学习算法",                # 应该是查文献
        "这个系统怎么使用？"               # 应该是闲聊
    ]
    
    for query in test_queries:
        result = await classifier.classify_intent(query)
        print(f"📝 查询: {query}")
        print(f"   分类: {result.intent} (置信度: {result.confidence:.3f})")
        print(f"   方法: {result.method}, 原因: {result.reasoning}")
        print()
    
    # 打印统计信息
    stats = classifier.get_stats()
    print("📊 分类器统计:", json.dumps(stats, indent=2, ensure_ascii=False))
    
    print("✅ 测试完成")

if __name__ == "__main__":
    asyncio.run(test_intent_classifier())