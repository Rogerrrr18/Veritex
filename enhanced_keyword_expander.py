"""
增强的关键词扩展器 - Paper God核心组件
重构版：集成学科检测 + 优化Groq LLM扩展 + 为SPLADE预留接口
"""

import asyncio
import time
from groq import Groq
from typing import List, Dict, Any
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class KeywordExpansionResult:
    """关键词扩展结果"""
    original_query: str
    expanded_keywords: List[str]
    detected_discipline: str
    discipline_chinese: str
    confidence: float
    expansion_strategy: str
    quality_score: float
    processing_time: float

class EnhancedKeywordExpander:
    """增强的关键词扩展器 - 支持学科检测和专业术语扩展"""
    
    def __init__(self, api_key: str, model: str = "gemma2-9b-it"):
        """初始化关键词扩展器"""
        try:
            self.client = Groq(api_key=api_key)
            self.model = model
            self.max_retries = 3
            self.retry_delay = 1  # 秒
            logger.info("关键词扩展器初始化成功")
        except Exception as e:
            logger.error(f"关键词扩展器初始化失败: {e}")
            raise
    
    async def detect_and_expand(
        self,
        query: str,
        max_keywords: int = 5
    ) -> KeywordExpansionResult:
        """检测学科领域并扩展关键词"""
        start_time = time.time()
        
        try:
            # 规范化查询
            query = query.strip()
            if not query:
                raise ValueError("查询不能为空")
            
            # 构建提示词
            prompt = self._build_prompt(query, max_keywords)
            
            # 尝试获取响应
            response = await self._get_response_with_retry(prompt)
            
            # 解析响应
            try:
                result = self._parse_response(response, query)
            except Exception as e:
                logger.error(f"解析响应失败: {e}")
                # 返回基本结果
                return KeywordExpansionResult(
                    original_query=query,
                    expanded_keywords=[query],
                    detected_discipline="unknown",
                    discipline_chinese="未知",
                    confidence=0.0,
                    expansion_strategy="fallback",
                    quality_score=0.0,
                    processing_time=time.time() - start_time
                )
            
            # 添加处理时间
            result.processing_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            logger.error(f"关键词扩展失败: {e}")
            # 返回原始查询作为结果
            return KeywordExpansionResult(
                original_query=query,
                expanded_keywords=[query],
                detected_discipline="error",
                discipline_chinese="错误",
                confidence=0.0,
                expansion_strategy="error",
                quality_score=0.0,
                processing_time=time.time() - start_time
            )
    
    def _build_prompt(self, query: str, max_keywords: int) -> str:
        """构建提示词"""
        return f"""作为一个学术文献搜索助手，请帮我分析以下查询并提供相关信息：

查询: {query}

请提供以下信息（JSON格式）：
1. 检测到的学科领域（英文）
2. 学科中文名称
3. 置信度（0-1）
4. 扩展策略说明
5. 扩展后的关键词列表（最多{max_keywords}个，包含原始关键词）
6. 质量评分（0-1）

示例格式：
{{
    "detected_discipline": "computer_science",
    "discipline_chinese": "计算机科学",
    "confidence": 0.95,
    "expansion_strategy": "field_specific_terms",
    "expanded_keywords": ["machine learning", "deep learning", "neural networks"],
    "quality_score": 0.85
}}"""
    
    async def _get_response_with_retry(self, prompt: str, attempt: int = 1) -> str:
        """获取响应，支持重试"""
        try:
            # 使用asyncio.to_thread在线程池中运行同步调用
            completion = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3,
                max_tokens=500,
                top_p=0.9
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            if attempt < self.max_retries:
                logger.warning(f"API调用失败，尝试重试 ({attempt}/{self.max_retries}): {e}")
                await asyncio.sleep(self.retry_delay * attempt)
                return await self._get_response_with_retry(prompt, attempt + 1)
            else:
                logger.error(f"API调用失败，已达到最大重试次数: {e}")
                raise
    
    def _parse_response(self, response: str, original_query: str) -> KeywordExpansionResult:
        """解析API响应"""
        try:
            # 提取JSON部分
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("响应中未找到有效的JSON")
            
            json_str = response[start:end]
            data = json.loads(json_str)
            
            # 验证必要字段
            required_fields = [
                "detected_discipline",
                "discipline_chinese",
                "confidence",
                "expansion_strategy",
                "expanded_keywords",
                "quality_score"
            ]
            
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"缺少必要字段: {field}")
            
            # 确保扩展关键词包含原始查询
            expanded_keywords = data["expanded_keywords"]
            if original_query not in expanded_keywords:
                expanded_keywords.insert(0, original_query)
            
            # 规范化数值
            confidence = max(0.0, min(1.0, float(data["confidence"])))
            quality_score = max(0.0, min(1.0, float(data["quality_score"])))
            
            return KeywordExpansionResult(
                original_query=original_query,
                expanded_keywords=expanded_keywords,
                detected_discipline=data["detected_discipline"],
                discipline_chinese=data["discipline_chinese"],
                confidence=confidence,
                expansion_strategy=data["expansion_strategy"],
                quality_score=quality_score,
                processing_time=0.0  # 将在外部设置
            )
            
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            raise
    
    def _is_chinese(self, text: str) -> bool:
        """检测文本是否包含中文字符"""
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    
    async def _expand_keywords_with_groq(
        self, 
        query: str, 
        discipline: str, 
        discipline_chinese: str,
        max_keywords: int
    ) -> List[str]:
        """使用优化的Groq LLM进行关键词扩展"""
        
        is_chinese_input = self._is_chinese(query)
        
        if is_chinese_input:
            return await self._expand_chinese_query(query, discipline_chinese, max_keywords)
        else:
            return await self._expand_english_query(query, discipline, max_keywords)
    
    async def _expand_chinese_query(
        self, 
        query: str, 
        discipline_chinese: str, 
        max_keywords: int
    ) -> List[str]:
        """扩展中文查询为英文学术术语"""
        
        prompt = f"""
你是{discipline_chinese}领域的专业术语专家。请将以下中文查询转换为{max_keywords}个最相关的英文学术术语：

学科领域：{discipline_chinese}
中文查询：{query}

要求：
1. 转换为该学科的标准英文术语
2. 包括核心概念、技术方法、专业工具
3. 避免通用词汇，专注专业术语
4. 术语要精准且在学术文献中常用
5. 仅返回英文术语，用逗号分隔
6. 不要包含解释或其他文字

英文学术术语："""

        try:
            # 使用asyncio.to_thread在线程池中运行同步调用
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150
            )
            
            raw_terms = response.choices[0].message.content.strip()
            terms = self._parse_terms(raw_terms)
            
            return terms[:max_keywords]
            
        except Exception as e:
            logger.error(f"中文查询扩展失败: {e}")
            return [query]
    
    async def _expand_english_query(
        self, 
        query: str, 
        discipline: str, 
        max_keywords: int
    ) -> List[str]:
        """扩展英文查询为相关学术术语"""
        
        prompt = f"""
You are a {discipline} terminology expert. Generate {max_keywords} highly relevant academic terms for:

Field: {discipline}
Query: {query}

Requirements:
1. Focus on technical methods, theories, algorithms specific to this field
2. Include both abbreviations and full terms when applicable
3. Prioritize terms commonly used in academic literature
4. Avoid general synonyms, focus on professional terminology
5. Return only terms separated by commas
6. No explanations or additional text

Academic terms:"""

        try:
            # 使用asyncio.to_thread在线程池中运行同步调用
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150
            )
            
            raw_terms = response.choices[0].message.content.strip()
            terms = self._parse_terms(raw_terms)
            
            # 确保原查询包含在结果中
            if query not in terms:
                terms.insert(0, query)
            
            return terms[:max_keywords]
            
        except Exception as e:
            logger.error(f"英文查询扩展失败: {e}")
            return [query]
    
    def _parse_terms(self, raw_terms: str) -> List[str]:
        """解析和清理术语列表"""
        terms = []
        
        for term in raw_terms.split(','):
            clean_term = term.strip().strip('"').strip("'").strip()
            
            # 基本验证
            if (clean_term and 
                len(clean_term) >= 2 and 
                len(clean_term) <= 100 and
                not self._is_chinese(clean_term)):
                
                # 过滤无效模式
                invalid_patterns = [
                    'academic terms', 'professional terms', 'requirements',
                    'format', 'field:', 'query:', 'based on'
                ]
                
                if not any(pattern in clean_term.lower() for pattern in invalid_patterns):
                    terms.append(clean_term)
        
        return terms
    
    def _merge_expansions(self, groq_terms: List[str], splade_terms: List[str]) -> List[str]:
        """合并Groq和SPLADE扩展结果（预留功能）"""
        # 简单合并策略，SPLADE集成时完善
        all_terms = groq_terms.copy()
        
        for term in splade_terms:
            if term not in all_terms:
                all_terms.append(term)
        
        return all_terms
    
    def _calculate_expansion_quality(
        self, 
        expanded_keywords: List[str], 
        confidence: float
    ) -> float:
        """计算扩展质量分数"""
        base_score = 0.5
        
        # 基于学科检测置信度
        base_score += confidence * 0.3
        
        # 基于扩展术语数量
        if len(expanded_keywords) >= 3:
            base_score += 0.2
        
        # 专业术语指标
        professional_indicators = [
            'algorithm', 'method', 'analysis', 'technique', 'approach',
            'model', 'system', 'framework', 'protocol', 'mechanism'
        ]
        
        professional_count = sum(
            1 for term in expanded_keywords 
            if any(indicator in term.lower() for indicator in professional_indicators)
        )
        
        if professional_count > 0:
            base_score += min(professional_count * 0.05, 0.2)
        
        return min(base_score, 1.0)
    
    def _determine_strategy(
        self, 
        query: str, 
        discipline_info: Dict[str, Any]
    ) -> str:
        """确定扩展策略描述"""
        if self._is_chinese(query):
            return f"中文翻译扩展 - {discipline_info['discipline_chinese']}领域"
        else:
            if discipline_info['confidence'] > 0.7:
                return f"专业术语扩展 - {discipline_info['discipline_chinese']}领域"
            else:
                return "通用学术术语扩展"
    
    # 预留SPLADE集成接口
    def enable_splade(self, splade_model):
        """启用SPLADE语义扩展（预留接口）"""
        self.splade_model = splade_model
        self.use_splade = True
        logger.info("SPLADE语义扩展已启用")
    
    def disable_splade(self):
        """禁用SPLADE语义扩展"""
        self.use_splade = False
        logger.info("SPLADE语义扩展已禁用")
    
    # 保持向后兼容的方法
    async def expand_keywords(self, keywords: str, max_terms: int = 5) -> List[str]:
        """
        向后兼容方法 - 保持与原有代码的兼容性
        """
        result = await self.detect_and_expand(keywords, max_terms)
        return result.expanded_keywords

# 测试和示例
async def main():
    """测试增强的关键词扩展器"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        print("请设置GROQ_API_KEY环境变量")
        return
    
    expander = EnhancedKeywordExpander(groq_api_key)
    
    # 测试案例
    test_cases = [
        "甲烷干重整催化剂",
        "machine learning algorithms", 
        "CRISPR基因编辑技术",
        "quantum computing applications",
        "蛋白质折叠预测",
        "blockchain consensus mechanisms"
    ]
    
    for query in test_cases:
        print(f"\n=== 测试查询: {query} ===")
        
        # 检测和扩展
        result = await expander.detect_and_expand(query, max_keywords=5)
        
        print(f"检测学科: {result.discipline_chinese} ({result.detected_discipline})")
        print(f"置信度: {result.confidence:.2f}")
        print(f"扩展策略: {result.expansion_strategy}")
        print(f"处理时间: {result.processing_time:.2f}秒")
        print(f"质量分数: {result.quality_score:.2f}")
        print(f"扩展结果: {result.expanded_keywords}")

if __name__ == "__main__":
    asyncio.run(main())