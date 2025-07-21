"""
查询意图识别模块
区分关键词搜索、问句查询、研究问题等不同查询类型
"""

import re
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from groq import Groq
import json
import logging

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """查询类型枚举"""
    KEYWORDS = "关键词搜索"
    QUESTION = "问句查询"
    RESEARCH_QUESTION = "研究问题"
    COMPARISON = "对比分析"
    REVIEW_REQUEST = "综述请求"
    DEFINITION = "定义查询"
    METHODOLOGY = "方法询问"
    TREND_ANALYSIS = "趋势分析"

class QueryComplexity(Enum):
    """查询复杂度"""
    SIMPLE = "简单"
    MODERATE = "中等"
    COMPLEX = "复杂"

@dataclass
class QueryIntent:
    """查询意图分析结果"""
    query_type: QueryType
    complexity: QueryComplexity
    entities: List[str]  # 识别出的实体
    concepts: List[str]  # 识别出的概念
    temporal_aspects: List[str]  # 时间相关的词汇
    comparison_targets: List[str]  # 对比目标
    research_focus: str  # 研究焦点
    suggested_search_strategy: str  # 建议的搜索策略
    confidence: float

@dataclass
class ProcessedQuery:
    """处理后的查询"""
    original_query: str
    processed_keywords: List[str]
    search_queries: List[str]  # 生成的搜索查询
    query_intent: QueryIntent
    optimization_notes: List[str]

class QueryIntentAnalyzer:
    """查询意图分析器"""
    
    def __init__(self, groq_api_key: str, model_name: str = "gemma2-9b-it"):
        self.client = Groq(api_key=groq_api_key)
        self.model_name = model_name
        
        # 查询类型识别模式
        self.query_patterns = {
            QueryType.QUESTION: [
                r'\?$',  # 以问号结尾
                r'^(what|how|why|when|where|who|which|is|are|does|do|can|could|would|will)',
                r'(什么|如何|为什么|什么时候|哪里|谁|哪个|是否|能否|会不会)'
            ],
            QueryType.RESEARCH_QUESTION: [
                r'(research question|研究问题)',
                r'(investigate|explore|examine|analyze|study|investigate)',
                r'(影响|关系|相关性|机制|效果|作用)'
            ],
            QueryType.COMPARISON: [
                r'(vs|versus|compared to|compare|difference|区别|对比|比较)',
                r'(better|worse|more|less|higher|lower|优于|劣于|更好|更差)'
            ],
            QueryType.REVIEW_REQUEST: [
                r'(review|survey|overview|综述|概述|总结)',
                r'(state of art|现状|发展|进展|趋势)'
            ],
            QueryType.DEFINITION: [
                r'^(define|definition|what is|什么是|定义)',
                r'(meaning|concept|概念|含义)'
            ],
            QueryType.METHODOLOGY: [
                r'(method|methodology|approach|technique|方法|技术|途径)',
                r'(how to|如何实现|怎样|怎么)'
            ],
            QueryType.TREND_ANALYSIS: [
                r'(trend|pattern|evolution|development|趋势|发展|演变)',
                r'(recent|latest|current|future|最新|当前|未来|近期)'
            ]
        }
        
        # 复杂度判断因素
        self.complexity_indicators = {
            'simple': ['单个概念', '一般词汇', '简单问句'],
            'moderate': ['多个概念', '特定领域', '对比关系'],
            'complex': ['多重关系', '交叉学科', '深层分析', '时间序列']
        }
    
    def _is_chinese(self, text: str) -> bool:
        """检测文本是否包含中文字符"""
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    
    def _detect_query_type_by_patterns(self, query: str) -> QueryType:
        """基于模式匹配检测查询类型"""
        query_lower = query.lower()
        
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type
        
        return QueryType.KEYWORDS  # 默认为关键词搜索
    
    def _extract_entities_simple(self, query: str) -> Tuple[List[str], List[str]]:
        """简单的实体和概念提取"""
        # 专业术语模式
        technical_patterns = [
            r'\b[A-Z]{2,}\b',  # 大写缩写
            r'\b\w+(?:\s+\w+)*(?:\s+algorithm|method|model|system|framework)\b',
            r'\b(?:deep|machine|artificial)\s+\w+\b'
        ]
        
        entities = []
        for pattern in technical_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities.extend(matches)
        
        # 概念提取（简化版）
        concepts = []
        concept_indicators = [
            'learning', 'intelligence', 'network', 'analysis', 'processing',
            '学习', '智能', '网络', '分析', '处理'
        ]
        
        for indicator in concept_indicators:
            if indicator in query.lower():
                concepts.append(indicator)
        
        return list(set(entities)), list(set(concepts))
    
    def _extract_temporal_aspects(self, query: str) -> List[str]:
        """提取时间相关的词汇"""
        temporal_patterns = [
            r'\b(recent|latest|current|new|old|past|future|年来|最近|当前|新的|旧的|未来)\b',
            r'\b(20\d{2}|19\d{2})\b',  # 年份
            r'\b(today|yesterday|tomorrow|今天|昨天|明天)\b'
        ]
        
        temporal_aspects = []
        for pattern in temporal_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            temporal_aspects.extend(matches)
        
        return list(set(temporal_aspects))
    
    def _extract_comparison_targets(self, query: str) -> List[str]:
        """提取对比目标"""
        # 寻找 "A vs B", "A compared to B" 等模式
        comparison_patterns = [
            r'(\w+(?:\s+\w+)*)\s+(?:vs|versus|compared\s+to)\s+(\w+(?:\s+\w+)*)',
            r'(\w+)\s+和\s+(\w+)\s*(?:的)?(?:区别|对比|比较)',
            r'(\w+)\s*(?:与|和)\s*(\w+)\s*(?:相比|对比)'
        ]
        
        targets = []
        for pattern in comparison_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                targets.extend([m.strip() for m in match if m.strip()])
        
        return targets
    
    def _assess_complexity(self, query: str, entities: List[str], concepts: List[str]) -> QueryComplexity:
        """评估查询复杂度"""
        complexity_score = 0
        
        # 基于长度
        if len(query) > 100:
            complexity_score += 2
        elif len(query) > 50:
            complexity_score += 1
        
        # 基于实体和概念数量
        complexity_score += len(entities) + len(concepts)
        
        # 基于查询结构
        if '?' in query:
            complexity_score += 1
        if any(word in query.lower() for word in ['and', 'or', 'but', '且', '或', '但是']):
            complexity_score += 1
        if any(word in query.lower() for word in ['compare', 'analyze', 'evaluate', '分析', '评估', '对比']):
            complexity_score += 2
        
        if complexity_score >= 6:
            return QueryComplexity.COMPLEX
        elif complexity_score >= 3:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE
    
    async def analyze_query_intent(self, query: str) -> QueryIntent:
        """分析查询意图"""
        
        # 1. 基本模式检测
        query_type = self._detect_query_type_by_patterns(query)
        
        # 2. 提取实体和概念
        entities, concepts = self._extract_entities_simple(query)
        
        # 3. 提取时间和对比信息
        temporal_aspects = self._extract_temporal_aspects(query)
        comparison_targets = self._extract_comparison_targets(query)
        
        # 4. 评估复杂度
        complexity = self._assess_complexity(query, entities, concepts)
        
        # 5. 使用LLM进行深度分析
        llm_analysis = await self._llm_intent_analysis(query, query_type)
        
        # 6. 生成研究焦点和搜索策略
        research_focus = self._determine_research_focus(query, entities, concepts)
        search_strategy = self._suggest_search_strategy(query_type, complexity, entities)
        
        return QueryIntent(
            query_type=query_type,
            complexity=complexity,
            entities=entities,
            concepts=concepts,
            temporal_aspects=temporal_aspects,
            comparison_targets=comparison_targets,
            research_focus=research_focus,
            suggested_search_strategy=search_strategy,
            confidence=llm_analysis.get('confidence', 0.7)
        )
    
    async def _llm_intent_analysis(self, query: str, detected_type: QueryType) -> Dict:
        """使用LLM进行深度意图分析"""
        
        prompt = f"""
分析以下学术查询的意图和特征：

查询: {query}
初步检测类型: {detected_type.value}

请分析：
1. 查询的真实意图和目的
2. 隐含的研究需求
3. 最佳的搜索方法建议
4. 分析的置信度(0-1)

返回JSON格式：
{{
    "true_intent": "实际查询意图",
    "research_needs": ["需求1", "需求2"],
    "search_suggestions": ["建议1", "建议2"],
    "confidence": 0.85,
    "reasoning": "分析理由"
}}

JSON结果："""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 提取JSON
            json_match = re.search(r'\\{.*\\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            logger.warning(f"LLM意图分析失败: {e}")
        
        return {'confidence': 0.5}
    
    def _determine_research_focus(self, query: str, entities: List[str], concepts: List[str]) -> str:
        """确定研究焦点"""
        if entities:
            return f"实体研究: {', '.join(entities[:3])}"
        elif concepts:
            return f"概念研究: {', '.join(concepts[:3])}"
        else:
            return f"主题研究: {query[:50]}"
    
    def _suggest_search_strategy(self, query_type: QueryType, complexity: QueryComplexity, entities: List[str]) -> str:
        """建议搜索策略"""
        strategies = {
            QueryType.KEYWORDS: "直接关键词匹配 + 语义扩展",
            QueryType.QUESTION: "问题分解 + 概念提取 + 多角度搜索",
            QueryType.RESEARCH_QUESTION: "系统性文献搜索 + 研究方法筛选",
            QueryType.COMPARISON: "对比实体分别搜索 + 比较研究筛选",
            QueryType.REVIEW_REQUEST: "综述类文献优先 + 最新研究补充",
            QueryType.DEFINITION: "定义性文献 + 概念发展历程",
            QueryType.METHODOLOGY: "方法论文献 + 技术实现细节",
            QueryType.TREND_ANALYSIS: "时间序列搜索 + 发展趋势分析"
        }
        
        base_strategy = strategies.get(query_type, "通用搜索策略")
        
        if complexity == QueryComplexity.COMPLEX:
            base_strategy += " + 分阶段深入搜索"
        
        if entities:
            base_strategy += " + 实体相关性增强"
        
        return base_strategy

class QueryProcessor:
    """查询处理器：将分析结果转换为可执行的搜索"""
    
    def __init__(self, intent_analyzer: QueryIntentAnalyzer):
        self.intent_analyzer = intent_analyzer
    
    async def process_query(self, original_query: str) -> ProcessedQuery:
        """处理查询并生成搜索策略"""
        
        # 1. 分析查询意图
        intent = await self.intent_analyzer.analyze_query_intent(original_query)
        
        # 2. 基于意图生成关键词
        keywords = await self._generate_keywords_from_intent(original_query, intent)
        
        # 3. 生成多个搜索查询
        search_queries = self._generate_search_queries(original_query, intent, keywords)
        
        # 4. 生成优化建议
        optimization_notes = self._generate_optimization_notes(intent)
        
        return ProcessedQuery(
            original_query=original_query,
            processed_keywords=keywords,
            search_queries=search_queries,
            query_intent=intent,
            optimization_notes=optimization_notes
        )
    
    async def _generate_keywords_from_intent(self, query: str, intent: QueryIntent) -> List[str]:
        """基于意图生成关键词"""
        keywords = []
        
        # 添加实体和概念
        keywords.extend(intent.entities)
        keywords.extend(intent.concepts)
        
        # 基于查询类型添加特定关键词
        if intent.query_type == QueryType.RESEARCH_QUESTION:
            keywords.extend(['research', 'study', 'investigation'])
        elif intent.query_type == QueryType.COMPARISON:
            keywords.extend(['comparison', 'versus', 'difference'])
        elif intent.query_type == QueryType.REVIEW_REQUEST:
            keywords.extend(['review', 'survey', 'overview'])
        
        # 从原始查询中提取额外关键词
        query_words = re.findall(r'\b\w{3,}\b', query.lower())
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        query_keywords = [word for word in query_words if word not in stop_words]
        
        keywords.extend(query_keywords)
        
        # 去重并过滤
        unique_keywords = []
        seen = set()
        for kw in keywords:
            if kw.lower() not in seen and len(kw) >= 3:
                unique_keywords.append(kw)
                seen.add(kw.lower())
        
        return unique_keywords[:10]  # 限制关键词数量
    
    def _generate_search_queries(self, original_query: str, intent: QueryIntent, keywords: List[str]) -> List[str]:
        """生成多个搜索查询"""
        queries = []
        
        # 基础关键词查询
        if keywords:
            queries.append(' '.join(keywords[:5]))
        
        # 基于查询类型的特化查询
        if intent.query_type == QueryType.QUESTION:
            # 对于问句，尝试提取核心概念
            core_concepts = [kw for kw in keywords if len(kw) > 5]
            if core_concepts:
                queries.append(' AND '.join(core_concepts[:3]))
        
        elif intent.query_type == QueryType.COMPARISON and intent.comparison_targets:
            # 对于对比查询，分别搜索对比目标
            for target in intent.comparison_targets[:2]:
                queries.append(f'{target} comparison study')
        
        elif intent.query_type == QueryType.REVIEW_REQUEST:
            # 综述查询
            topic_keywords = keywords[:3]
            queries.append(f'{" ".join(topic_keywords)} review')
            queries.append(f'{" ".join(topic_keywords)} survey')
        
        # 添加时间限制的查询
        if intent.temporal_aspects:
            recent_query = f'{" ".join(keywords[:3])} recent'
            queries.append(recent_query)
        
        # 确保至少有一个查询
        if not queries:
            queries.append(original_query)
        
        return queries[:4]  # 限制查询数量
    
    def _generate_optimization_notes(self, intent: QueryIntent) -> List[str]:
        """生成优化建议"""
        notes = []
        
        if intent.complexity == QueryComplexity.COMPLEX:
            notes.append("查询较为复杂，建议分阶段搜索")
        
        if intent.query_type == QueryType.QUESTION:
            notes.append("问句查询：已转换为关键词搜索，可能需要人工筛选结果")
        
        if intent.comparison_targets:
            notes.append(f"对比查询：建议分别搜索 {', '.join(intent.comparison_targets)}")
        
        if not intent.entities and not intent.concepts:
            notes.append("未检测到明确实体，建议细化查询内容")
        
        if intent.confidence < 0.6:
            notes.append("查询意图不够明确，建议重新表述")
        
        return notes

# 测试用例
async def main():
    """测试查询意图识别"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        print("请设置GROQ_API_KEY环境变量")
        return
    
    analyzer = QueryIntentAnalyzer(groq_api_key)
    processor = QueryProcessor(analyzer)
    
    # 测试查询
    test_queries = [
        "机器学习",
        "What is the difference between supervised and unsupervised learning?",
        "How does BERT transformer work?",
        "深度学习在医学影像中的应用研究进展",
        "Compare CNN vs RNN for image classification",
        "Recent advances in quantum computing",
        "神经网络优化算法综述"
    ]
    
    for query in test_queries:
        print(f"\\n=== 查询: {query} ===")
        
        # 处理查询
        result = await processor.process_query(query)
        
        print(f"查询类型: {result.query_intent.query_type.value}")
        print(f"复杂度: {result.query_intent.complexity.value}")
        print(f"研究焦点: {result.query_intent.research_focus}")
        print(f"提取关键词: {result.processed_keywords}")
        print(f"搜索查询: {result.search_queries}")
        print(f"搜索策略: {result.query_intent.suggested_search_strategy}")
        if result.optimization_notes:
            print(f"优化建议: {'; '.join(result.optimization_notes)}")

if __name__ == "__main__":
    asyncio.run(main())