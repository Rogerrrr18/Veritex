"""
增强的关键词扩展和学科检测模块
支持15+学科领域的自动检测和专业术语扩展
"""

import asyncio
from groq import Groq
from typing import List, Dict, Optional, Tuple
import re
import json
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AcademicDiscipline(Enum):
    """学科领域枚举"""
    COMPUTER_SCIENCE = "计算机科学"
    ARTIFICIAL_INTELLIGENCE = "人工智能"
    BIOLOGY = "生物学"
    MEDICINE = "医学"
    CHEMISTRY = "化学"
    PHYSICS = "物理学"
    MATHEMATICS = "数学"
    PSYCHOLOGY = "心理学"
    ECONOMICS = "经济学"
    ENGINEERING = "工程学"
    SOCIAL_SCIENCE = "社会科学"
    ENVIRONMENTAL_SCIENCE = "环境科学"
    MATERIALS_SCIENCE = "材料科学"
    NEUROSCIENCE = "神经科学"
    PHARMACOLOGY = "药理学"
    BIOTECHNOLOGY = "生物技术"
    DATA_SCIENCE = "数据科学"
    ROBOTICS = "机器人学"
    UNKNOWN = "未知领域"

@dataclass
class DisciplineDetectionResult:
    """学科检测结果"""
    primary_discipline: AcademicDiscipline
    secondary_disciplines: List[AcademicDiscipline]
    confidence: float
    keywords_by_discipline: Dict[str, List[str]]

@dataclass
class KeywordExpansionResult:
    """关键词扩展结果"""
    original_keywords: List[str]
    expanded_keywords: List[str]
    discipline_info: DisciplineDetectionResult
    expansion_strategy: str
    quality_score: float

class EnhancedKeywordExpander:
    """增强的关键词扩展器"""
    
    def __init__(self, groq_api_key: str, model_name: str = "gemma2-9b-it"):
        self.client = Groq(api_key=groq_api_key)
        self.model_name = model_name
        
        # 学科特征词典
        self.discipline_keywords = {
            AcademicDiscipline.COMPUTER_SCIENCE: [
                "algorithm", "software", "programming", "computing", "database", 
                "network", "system", "code", "compiler", "interface"
            ],
            AcademicDiscipline.ARTIFICIAL_INTELLIGENCE: [
                "machine learning", "neural network", "deep learning", "AI", 
                "artificial intelligence", "model", "training", "prediction", 
                "classification", "regression", "transformer", "attention"
            ],
            AcademicDiscipline.BIOLOGY: [
                "gene", "protein", "cell", "organism", "evolution", "species",
                "DNA", "RNA", "enzyme", "molecular", "genetics", "biotechnology"
            ],
            AcademicDiscipline.MEDICINE: [
                "patient", "treatment", "diagnosis", "therapy", "clinical",
                "disease", "symptom", "drug", "pharmaceutical", "healthcare"
            ],
            AcademicDiscipline.CHEMISTRY: [
                "molecule", "compound", "reaction", "catalyst", "synthesis",
                "organic", "inorganic", "chemical", "bond", "element"
            ],
            AcademicDiscipline.PHYSICS: [
                "quantum", "particle", "energy", "force", "wave", "field",
                "matter", "radiation", "electromagnetic", "mechanics"
            ],
            AcademicDiscipline.MATHEMATICS: [
                "theorem", "proof", "equation", "function", "matrix", "calculus",
                "algebra", "geometry", "statistics", "probability"
            ],
            AcademicDiscipline.PSYCHOLOGY: [
                "behavior", "cognitive", "mental", "brain", "mind", "emotion",
                "perception", "learning", "memory", "consciousness"
            ],
            AcademicDiscipline.ECONOMICS: [
                "market", "economy", "finance", "trade", "investment", "price",
                "economic", "monetary", "fiscal", "business", "growth"
            ],
            AcademicDiscipline.ENGINEERING: [
                "design", "construction", "mechanical", "electrical", "civil",
                "structural", "manufacturing", "technology", "innovation"
            ],
            AcademicDiscipline.SOCIAL_SCIENCE: [
                "social", "society", "culture", "community", "policy", "governance",
                "political", "sociology", "anthropology", "demographic"
            ],
            AcademicDiscipline.ENVIRONMENTAL_SCIENCE: [
                "environment", "climate", "ecosystem", "pollution", "sustainability",
                "conservation", "ecology", "biodiversity", "carbon", "renewable"
            ],
            AcademicDiscipline.MATERIALS_SCIENCE: [
                "material", "polymer", "composite", "ceramic", "metal", "crystal",
                "nanostructure", "mechanical properties", "thermal"
            ],
            AcademicDiscipline.NEUROSCIENCE: [
                "neuron", "brain", "nervous system", "synaptic", "neurological",
                "cognitive neuroscience", "neuroimaging", "neurotransmitter"
            ],
            AcademicDiscipline.PHARMACOLOGY: [
                "drug", "pharmaceutical", "pharmacokinetics", "toxicity",
                "medication", "therapeutic", "dosage", "clinical trial"
            ],
            AcademicDiscipline.BIOTECHNOLOGY: [
                "bioengineering", "genetic engineering", "bioinformatics",
                "bioprocessing", "fermentation", "recombinant", "cloning"
            ],
            AcademicDiscipline.DATA_SCIENCE: [
                "data mining", "big data", "analytics", "visualization",
                "statistical analysis", "machine learning", "predictive modeling"
            ],
            AcademicDiscipline.ROBOTICS: [
                "robot", "automation", "control system", "sensor", "actuator",
                "autonomous", "manipulation", "navigation", "humanoid"
            ]
        }
    
    def _is_chinese(self, text: str) -> bool:
        """检测文本是否包含中文字符"""
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    
    async def detect_discipline(self, keywords: str) -> DisciplineDetectionResult:
        """
        检测关键词所属的学科领域
        
        Args:
            keywords: 关键词字符串
            
        Returns:
            DisciplineDetectionResult: 学科检测结果
        """
        # 简单的关键词匹配检测
        keywords_lower = keywords.lower()
        discipline_scores = {}
        
        for discipline, discipline_keywords in self.discipline_keywords.items():
            score = 0
            matched_keywords = []
            
            for keyword in discipline_keywords:
                if keyword.lower() in keywords_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            if score > 0:
                discipline_scores[discipline] = {
                    'score': score,
                    'keywords': matched_keywords
                }
        
        # 如果基于关键词匹配没有结果，使用LLM判断
        if not discipline_scores:
            llm_result = await self._llm_discipline_detection(keywords)
            return llm_result
        
        # 排序并选择主要学科
        sorted_disciplines = sorted(
            discipline_scores.items(), 
            key=lambda x: x[1]['score'], 
            reverse=True
        )
        
        primary_discipline = sorted_disciplines[0][0]
        secondary_disciplines = [d[0] for d in sorted_disciplines[1:3]]
        
        # 计算置信度
        total_matches = sum(d['score'] for d in discipline_scores.values())
        primary_score = sorted_disciplines[0][1]['score']
        confidence = primary_score / total_matches if total_matches > 0 else 0.5
        
        # 构建关键词分布
        keywords_by_discipline = {}
        for discipline, data in discipline_scores.items():
            if data['keywords']:
                keywords_by_discipline[discipline.value] = data['keywords']
        
        return DisciplineDetectionResult(
            primary_discipline=primary_discipline,
            secondary_disciplines=secondary_disciplines,
            confidence=confidence,
            keywords_by_discipline=keywords_by_discipline
        )
    
    async def _llm_discipline_detection(self, keywords: str) -> DisciplineDetectionResult:
        """使用LLM进行学科检测"""
        
        disciplines_list = [d.value for d in AcademicDiscipline if d != AcademicDiscipline.UNKNOWN]
        
        prompt = f"""
你是学科领域专家。请分析以下关键词所属的学术领域：

关键词: {keywords}

可选学科领域：
{', '.join(disciplines_list)}

请返回JSON格式结果：
{{
    "primary_discipline": "主要学科（中文）",
    "secondary_disciplines": ["次要学科1", "次要学科2"],
    "confidence": 0.85,
    "reasoning": "判断理由"
}}

要求：
1. primary_discipline必须从可选学科中选择
2. secondary_disciplines最多2个
3. confidence为0-1之间的数值
4. 提供简短的判断理由

JSON结果："""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 尝试提取JSON
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
                
                # 转换为枚举类型
                primary_discipline = AcademicDiscipline.UNKNOWN
                for discipline in AcademicDiscipline:
                    if discipline.value == result_data.get('primary_discipline'):
                        primary_discipline = discipline
                        break
                
                secondary_disciplines = []
                for sec_disc in result_data.get('secondary_disciplines', []):
                    for discipline in AcademicDiscipline:
                        if discipline.value == sec_disc:
                            secondary_disciplines.append(discipline)
                            break
                
                return DisciplineDetectionResult(
                    primary_discipline=primary_discipline,
                    secondary_disciplines=secondary_disciplines,
                    confidence=result_data.get('confidence', 0.5),
                    keywords_by_discipline={}
                )
            
        except Exception as e:
            logger.warning(f"LLM学科检测失败: {e}")
        
        # 默认返回未知领域
        return DisciplineDetectionResult(
            primary_discipline=AcademicDiscipline.UNKNOWN,
            secondary_disciplines=[],
            confidence=0.3,
            keywords_by_discipline={}
        )
    
    async def expand_keywords_by_discipline(
        self,
        keywords: str,
        discipline_info: DisciplineDetectionResult,
        expansion_count: int = 3
    ) -> List[str]:
        """
        基于学科信息进行关键词扩展
        
        Args:
            keywords: 原始关键词
            discipline_info: 学科检测信息
            expansion_count: 扩展关键词数量
        """
        is_chinese_input = self._is_chinese(keywords)
        
        if is_chinese_input:
            return await self._expand_chinese_keywords(keywords, discipline_info, expansion_count)
        else:
            return await self._expand_english_keywords(keywords, discipline_info, expansion_count)
    
    async def _expand_chinese_keywords(
        self,
        keywords: str,
        discipline_info: DisciplineDetectionResult,
        expansion_count: int
    ) -> List[str]:
        """扩展中文关键词"""
        
        discipline_context = f"学科领域：{discipline_info.primary_discipline.value}"
        if discipline_info.secondary_disciplines:
            secondary_names = [d.value for d in discipline_info.secondary_disciplines]
            discipline_context += f"，相关领域：{', '.join(secondary_names)}"
        
        prompt = f"""
你是{discipline_info.primary_discipline.value}领域的专业术语专家。请将以下中文关键词转换为{expansion_count}个最相关的英文专业术语：

{discipline_context}
中文关键词: {keywords}

要求：
1. 优先转换为该学科领域的标准英文术语
2. 包括技术方法名、理论概念、专业工具等
3. 避免一般性词汇，专注于专业术语
4. 每个术语要精准且高质量
5. 返回格式：term1, term2, term3
6. 仅返回英文术语，用逗号分隔

专业英文术语："""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=100
            )
            
            raw_terms = response.choices[0].message.content.strip()
            terms = self._parse_and_validate_terms(raw_terms)
            
            return terms[:expansion_count]
            
        except Exception as e:
            logger.error(f"中文关键词扩展失败: {e}")
            return []
    
    async def _expand_english_keywords(
        self,
        keywords: str,
        discipline_info: DisciplineDetectionResult,
        expansion_count: int
    ) -> List[str]:
        """扩展英文关键词"""
        
        discipline_context = f"Academic field: {discipline_info.primary_discipline.value}"
        
        prompt = f"""
You are a {discipline_info.primary_discipline.value} terminology expert. Generate {expansion_count} highly relevant professional terms for the given keyword:

{discipline_context}
Keywords: {keywords}

Requirements:
1. Focus on technical methods, algorithms, theories specific to this field
2. Include both abbreviations and full terms when applicable
3. Prioritize terms commonly used in academic literature
4. Avoid general synonyms, focus on professional terminology
5. Each term should be precise and high-quality
6. Format: term1, term2, term3

Professional terms:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=100
            )
            
            raw_terms = response.choices[0].message.content.strip()
            terms = self._parse_and_validate_terms(raw_terms)
            
            # 确保原关键词包含在结果中
            if keywords not in terms:
                terms.insert(0, keywords)
            
            return terms[:expansion_count]
            
        except Exception as e:
            logger.error(f"英文关键词扩展失败: {e}")
            return [keywords]
    
    def _parse_and_validate_terms(self, raw_terms: str) -> List[str]:
        """解析和验证术语"""
        terms = []
        
        for term in raw_terms.split(','):
            clean_term = term.strip().strip('"').strip("'").strip()
            
            # 基本验证
            if (clean_term and 
                len(clean_term) >= 2 and 
                len(clean_term) <= 100 and
                not self._is_chinese(clean_term)):
                
                # 排除无效模式
                invalid_patterns = [
                    'based on', "i've generated", 'following', 'requirements',
                    'format', 'professional terms', 'academic field'
                ]
                
                if not any(pattern in clean_term.lower() for pattern in invalid_patterns):
                    terms.append(clean_term)
        
        return terms
    
    async def comprehensive_expansion(
        self, 
        keywords: str,
        max_keywords: int = 3
    ) -> KeywordExpansionResult:
        """
        综合关键词扩展：检测学科 + 扩展关键词
        
        Args:
            keywords: 原始关键词
            max_keywords: 最大扩展关键词数量
            
        Returns:
            KeywordExpansionResult: 完整的扩展结果
        """
        # 1. 检测学科领域
        discipline_info = await self.detect_discipline(keywords)
        
        # 2. 基于学科进行关键词扩展
        expanded_keywords = await self.expand_keywords_by_discipline(
            keywords, discipline_info, max_keywords
        )
        
        # 3. 计算扩展质量分数
        quality_score = self._calculate_quality_score(
            keywords, expanded_keywords, discipline_info
        )
        
        # 4. 确定扩展策略
        strategy = self._determine_expansion_strategy(keywords, discipline_info)
        
        return KeywordExpansionResult(
            original_keywords=[keywords],
            expanded_keywords=expanded_keywords,
            discipline_info=discipline_info,
            expansion_strategy=strategy,
            quality_score=quality_score
        )
    
    def _calculate_quality_score(
        self,
        original: str,
        expanded: List[str],
        discipline_info: DisciplineDetectionResult
    ) -> float:
        """计算扩展质量分数"""
        base_score = 0.5
        
        # 基于学科检测置信度
        base_score += discipline_info.confidence * 0.3
        
        # 基于扩展术语数量
        if len(expanded) >= 3:
            base_score += 0.2
        
        # 如果有专业术语特征，加分
        professional_indicators = [
            'algorithm', 'method', 'analysis', 'technique', 'approach',
            'model', 'system', 'framework', 'protocol', 'mechanism'
        ]
        
        professional_count = 0
        for term in expanded:
            if any(indicator in term.lower() for indicator in professional_indicators):
                professional_count += 1
        
        if professional_count > 0:
            base_score += min(professional_count * 0.05, 0.2)
        
        return min(base_score, 1.0)
    
    def _determine_expansion_strategy(
        self,
        keywords: str,
        discipline_info: DisciplineDetectionResult
    ) -> str:
        """确定扩展策略"""
        if self._is_chinese(keywords):
            return f"中文翻译策略 - {discipline_info.primary_discipline.value}领域"
        else:
            if discipline_info.confidence > 0.7:
                return f"专业术语扩展 - {discipline_info.primary_discipline.value}领域"
            else:
                return "通用扩展策略"

# 测试用例
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
        "机器学习",
        "neural networks", 
        "CRISPR基因编辑",
        "quantum computing",
        "蛋白质折叠",
        "blockchain technology"
    ]
    
    for keywords in test_cases:
        print(f"\n=== 测试关键词: {keywords} ===")
        
        # 学科检测
        discipline_info = await expander.detect_discipline(keywords)
        print(f"主要学科: {discipline_info.primary_discipline.value}")
        print(f"次要学科: {[d.value for d in discipline_info.secondary_disciplines]}")
        print(f"置信度: {discipline_info.confidence:.2f}")
        
        # 综合扩展
        result = await expander.comprehensive_expansion(keywords, max_keywords=6)
        print(f"扩展策略: {result.expansion_strategy}")
        print(f"质量分数: {result.quality_score:.2f}")
        print(f"扩展关键词: {result.expanded_keywords}")

if __name__ == "__main__":
    asyncio.run(main())