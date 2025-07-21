"""
结构化数据提取模块
类似Elicit的论文信息矩阵，自动提取研究方法、样本量、主要发现等信息
"""

import asyncio
import json
import re
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from groq import Groq
import logging
from academic_apis import Paper

logger = logging.getLogger(__name__)

class ExtractionField(Enum):
    """可提取的数据字段"""
    RESEARCH_METHOD = "研究方法"
    SAMPLE_SIZE = "样本量"
    MAIN_FINDINGS = "主要发现"
    LIMITATIONS = "研究局限"
    STUDY_TYPE = "研究类型"
    INTERVENTION = "干预措施"
    OUTCOME_MEASURES = "结果指标"
    POPULATION = "研究人群"
    STATISTICAL_METHOD = "统计方法"
    EFFECT_SIZE = "效应量"
    P_VALUE = "P值"
    CONFIDENCE_INTERVAL = "置信区间"
    PUBLICATION_TYPE = "发表类型"
    FUNDING_SOURCE = "资助来源"
    ETHICAL_APPROVAL = "伦理批准"

@dataclass
class ExtractedData:
    """提取的数据结构"""
    field: ExtractionField
    value: str
    confidence: float
    source_text: str  # 提取依据的原文

@dataclass
class PaperAnalysis:
    """论文分析结果"""
    paper: Paper
    extracted_data: Dict[str, ExtractedData]
    summary: str
    quality_score: float
    relevance_score: float
    extraction_notes: List[str]

@dataclass
class CustomColumn:
    """用户自定义列"""
    name: str
    description: str
    extraction_prompt: str
    data_type: str  # "text", "number", "category", "boolean"

class StructuredDataExtractor:
    """结构化数据提取器"""
    
    def __init__(self, groq_api_key: str, model_name: str = "gemma2-9b-it"):
        self.client = Groq(api_key=groq_api_key)
        self.model_name = model_name
        
        # 预定义的提取模板
        self.extraction_templates = self._init_extraction_templates()
        
        # 学科特定的提取规则
        self.discipline_specific_fields = self._init_discipline_fields()
    
    def _init_extraction_templates(self) -> Dict[ExtractionField, Dict]:
        """初始化提取模板"""
        return {
            ExtractionField.RESEARCH_METHOD: {
                "prompt": "识别研究使用的主要方法（如：实验、调查、观察、案例研究、系统综述等）",
                "keywords": ["method", "approach", "design", "methodology", "study design"],
                "patterns": [r"(experimental|observational|case study|survey|review|meta-analysis)"]
            },
            ExtractionField.SAMPLE_SIZE: {
                "prompt": "提取研究的样本量或参与者数量",
                "keywords": ["sample", "participants", "subjects", "n =", "n="],
                "patterns": [r"[Nn]\s*=\s*(\d+)", r"(\d+)\s*(participants|subjects|patients|samples)"]
            },
            ExtractionField.MAIN_FINDINGS: {
                "prompt": "总结研究的主要发现和结论（1-2句话）",
                "keywords": ["results", "findings", "conclusion", "outcome"],
                "patterns": [r"(significant|p\s*<|effect|correlation|association)"]
            },
            ExtractionField.LIMITATIONS: {
                "prompt": "识别研究承认的局限性",
                "keywords": ["limitation", "weakness", "constraint", "restrict"],
                "patterns": [r"(limited|constraint|weakness|bias|limitation)"]
            },
            ExtractionField.STUDY_TYPE: {
                "prompt": "确定研究类型（如：随机对照试验、队列研究、横断面研究等）",
                "keywords": ["randomized", "controlled", "cohort", "cross-sectional", "longitudinal"],
                "patterns": [r"(RCT|randomized controlled trial|cohort study|cross-sectional)"]
            },
            ExtractionField.INTERVENTION: {
                "prompt": "识别研究中的干预措施或治疗方法",
                "keywords": ["intervention", "treatment", "therapy", "drug", "medication"],
                "patterns": [r"(treatment|intervention|therapy|drug|medication)"]
            },
            ExtractionField.POPULATION: {
                "prompt": "描述研究的目标人群或对象",
                "keywords": ["population", "participants", "patients", "subjects"],
                "patterns": [r"(adults|children|patients|healthy|disease)"]
            },
            ExtractionField.P_VALUE: {
                "prompt": "提取统计显著性P值",
                "keywords": ["p-value", "p =", "p<", "significance"],
                "patterns": [r"[Pp]\s*[<>=]\s*(0\.\d+)", r"[Pp]\s*value\s*[<>=]\s*(0\.\d+)"]
            }
        }
    
    def _init_discipline_fields(self) -> Dict[str, List[ExtractionField]]:
        """初始化学科特定字段"""
        return {
            "医学": [
                ExtractionField.SAMPLE_SIZE, ExtractionField.INTERVENTION,
                ExtractionField.OUTCOME_MEASURES, ExtractionField.P_VALUE,
                ExtractionField.STUDY_TYPE, ExtractionField.POPULATION
            ],
            "心理学": [
                ExtractionField.SAMPLE_SIZE, ExtractionField.RESEARCH_METHOD,
                ExtractionField.STATISTICAL_METHOD, ExtractionField.EFFECT_SIZE,
                ExtractionField.POPULATION
            ],
            "计算机科学": [
                ExtractionField.RESEARCH_METHOD, ExtractionField.MAIN_FINDINGS,
                ExtractionField.LIMITATIONS, ExtractionField.STUDY_TYPE
            ],
            "生物学": [
                ExtractionField.RESEARCH_METHOD, ExtractionField.SAMPLE_SIZE,
                ExtractionField.STATISTICAL_METHOD, ExtractionField.MAIN_FINDINGS
            ]
        }
    
    async def extract_from_paper(
        self,
        paper: Paper,
        fields: Optional[List[ExtractionField]] = None,
        custom_columns: Optional[List[CustomColumn]] = None,
        user_query: Optional[str] = None
    ) -> PaperAnalysis:
        """
        从单篇论文提取结构化数据
        
        Args:
            paper: 论文对象
            fields: 要提取的字段列表
            custom_columns: 用户自定义列
            user_query: 用户原始查询，用于相关性评估
        """
        
        # 使用默认字段如果未指定
        if fields is None:
            fields = [
                ExtractionField.RESEARCH_METHOD,
                ExtractionField.SAMPLE_SIZE,
                ExtractionField.MAIN_FINDINGS,
                ExtractionField.STUDY_TYPE,
                ExtractionField.LIMITATIONS
            ]
        
        extracted_data = {}
        extraction_notes = []
        
        # 构建分析文本（标题 + 摘要）
        analysis_text = f"Title: {paper.title}\\n\\nAbstract: {paper.abstract}"
        
        # 提取预定义字段
        for field in fields:
            try:
                extracted = await self._extract_single_field(analysis_text, field, paper)
                if extracted:
                    extracted_data[field.value] = extracted
            except Exception as e:
                extraction_notes.append(f"提取{field.value}失败: {str(e)}")
                logger.warning(f"字段提取失败 {field.value}: {e}")
        
        # 提取自定义字段
        if custom_columns:
            for column in custom_columns:
                try:
                    extracted = await self._extract_custom_field(analysis_text, column, paper)
                    if extracted:
                        extracted_data[column.name] = extracted
                except Exception as e:
                    extraction_notes.append(f"提取自定义字段{column.name}失败: {str(e)}")
        
        # 生成论文摘要
        summary = await self._generate_paper_summary(paper, user_query)
        
        # 计算质量和相关性分数
        quality_score = self._calculate_quality_score(paper, extracted_data)
        relevance_score = self._calculate_relevance_score(paper, user_query) if user_query else 0.5
        
        return PaperAnalysis(
            paper=paper,
            extracted_data=extracted_data,
            summary=summary,
            quality_score=quality_score,
            relevance_score=relevance_score,
            extraction_notes=extraction_notes
        )
    
    async def _extract_single_field(
        self,
        text: str,
        field: ExtractionField,
        paper: Paper
    ) -> Optional[ExtractedData]:
        """提取单个字段"""
        
        template = self.extraction_templates.get(field)
        if not template:
            return None
        
        # 首先尝试正则表达式提取
        regex_result = self._regex_extract(text, template["patterns"])
        if regex_result:
            return ExtractedData(
                field=field,
                value=regex_result["value"],
                confidence=0.8,
                source_text=regex_result["source"]
            )
        
        # 使用LLM提取
        llm_result = await self._llm_extract_field(text, field, template)
        return llm_result
    
    def _regex_extract(self, text: str, patterns: List[str]) -> Optional[Dict]:
        """使用正则表达式提取"""
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                return {
                    "value": match.group(1) if match.groups() else match.group(0),
                    "source": match.group(0)
                }
        return None
    
    async def _llm_extract_field(
        self,
        text: str,
        field: ExtractionField,
        template: Dict
    ) -> Optional[ExtractedData]:
        """使用LLM提取字段"""
        
        prompt = f"""
从以下学术论文文本中提取特定信息：

{text[:1500]}  # 限制文本长度

提取任务：{template['prompt']}
关键词提示：{', '.join(template['keywords'])}

请返回JSON格式：
{{
    "value": "提取的值（如果没有找到返回'未找到'）",
    "confidence": 0.85,
    "source_text": "提取依据的原文片段",
    "reasoning": "提取理由"
}}

要求：
1. 如果确实没有相关信息，value填写"未找到"
2. confidence为0-1之间的数值
3. source_text应该是支持你判断的具体文本
4. 简要说明提取理由

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
                result_data = json.loads(json_match.group())
                
                value = result_data.get('value', '未找到')
                if value == '未找到' or not value.strip():
                    return None
                
                return ExtractedData(
                    field=field,
                    value=value,
                    confidence=result_data.get('confidence', 0.5),
                    source_text=result_data.get('source_text', '')
                )
        
        except Exception as e:
            logger.warning(f"LLM字段提取失败 {field.value}: {e}")
        
        return None
    
    async def _extract_custom_field(
        self,
        text: str,
        column: CustomColumn,
        paper: Paper
    ) -> Optional[ExtractedData]:
        """提取用户自定义字段"""
        
        prompt = f"""
从以下学术论文文本中提取用户指定的信息：

{text[:1500]}

自定义提取任务：
字段名称：{column.name}
字段描述：{column.description}
提取指令：{column.extraction_prompt}
数据类型：{column.data_type}

请返回JSON格式：
{{
    "value": "提取的值",
    "confidence": 0.85,
    "source_text": "提取依据的原文",
    "reasoning": "提取理由"
}}

注意：
- 根据数据类型返回合适的值格式
- 如果是数字类型，返回数值
- 如果是分类类型，返回具体类别
- 如果是布尔类型，返回true/false
- 如果没有找到相关信息，value填写"未找到"

JSON结果："""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 提取JSON
            json_match = re.search(r'\\{.*\\}', result_text, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
                
                value = result_data.get('value', '未找到')
                if value == '未找到':
                    return None
                
                return ExtractedData(
                    field=None,  # 自定义字段没有预定义枚举
                    value=str(value),
                    confidence=result_data.get('confidence', 0.5),
                    source_text=result_data.get('source_text', '')
                )
        
        except Exception as e:
            logger.warning(f"自定义字段提取失败 {column.name}: {e}")
        
        return None
    
    async def _generate_paper_summary(self, paper: Paper, user_query: Optional[str] = None) -> str:
        """生成针对查询的论文摘要"""
        
        context = f"针对用户查询：{user_query}" if user_query else "通用摘要"
        
        prompt = f"""
为以下学术论文生成简洁摘要：

{context}

论文标题：{paper.title}
论文摘要：{paper.abstract[:800]}

请生成一个2-3句话的摘要，重点突出：
1. 研究的核心内容
2. 主要方法或发现
3. 与用户查询的相关性（如果提供了查询）

摘要："""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.warning(f"摘要生成失败: {e}")
            return paper.abstract[:200] + "..." if paper.abstract else "无法生成摘要"
    
    def _calculate_quality_score(self, paper: Paper, extracted_data: Dict) -> float:
        """计算论文质量分数"""
        score = 0.5  # 基础分数
        
        # 基于引用次数
        if paper.citation_count > 100:
            score += 0.2
        elif paper.citation_count > 10:
            score += 0.1
        
        # 基于信息完整性
        if paper.abstract and len(paper.abstract) > 100:
            score += 0.1
        
        if paper.venue:
            score += 0.1
        
        # 基于提取数据的丰富程度
        extraction_completeness = len([d for d in extracted_data.values() if d.confidence > 0.6])
        score += min(extraction_completeness * 0.05, 0.2)
        
        return min(score, 1.0)
    
    def _calculate_relevance_score(self, paper: Paper, user_query: str) -> float:
        """计算与用户查询的相关性分数"""
        if not user_query:
            return 0.5
        
        query_terms = set(user_query.lower().split())
        paper_text = f"{paper.title} {paper.abstract}".lower()
        
        # 简单的词汇重叠计算
        matches = sum(1 for term in query_terms if term in paper_text)
        relevance = matches / len(query_terms) if query_terms else 0
        
        # 标题匹配加权
        title_matches = sum(1 for term in query_terms if term in paper.title.lower())
        if title_matches > 0:
            relevance += title_matches * 0.1
        
        return min(relevance, 1.0)
    
    async def batch_extract(
        self,
        papers: List[Paper],
        fields: Optional[List[ExtractionField]] = None,
        custom_columns: Optional[List[CustomColumn]] = None,
        user_query: Optional[str] = None,
        max_concurrent: int = 5
    ) -> List[PaperAnalysis]:
        """
        批量提取多篇论文的结构化数据
        
        Args:
            papers: 论文列表
            fields: 要提取的字段
            custom_columns: 自定义列
            user_query: 用户查询
            max_concurrent: 最大并发数
        """
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_single(paper):
            async with semaphore:
                return await self.extract_from_paper(
                    paper, fields, custom_columns, user_query
                )
        
        # 并发提取
        tasks = [extract_single(paper) for paper in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"论文 {i} 提取失败: {result}")
            else:
                valid_results.append(result)
        
        logger.info(f"成功提取 {len(valid_results)}/{len(papers)} 篇论文的数据")
        return valid_results
    
    def export_to_matrix(self, analyses: List[PaperAnalysis]) -> Dict[str, Any]:
        """导出为研究矩阵格式"""
        
        if not analyses:
            return {"columns": [], "rows": []}
        
        # 收集所有字段
        all_fields = set()
        for analysis in analyses:
            all_fields.update(analysis.extracted_data.keys())
        
        all_fields = sorted(list(all_fields))
        
        # 构建列定义
        columns = [
            {"name": "title", "label": "标题", "type": "text"},
            {"name": "authors", "label": "作者", "type": "text"},
            {"name": "year", "label": "年份", "type": "number"},
            {"name": "venue", "label": "发表期刊", "type": "text"},
            {"name": "citation_count", "label": "引用次数", "type": "number"},
            {"name": "summary", "label": "摘要总结", "type": "text"},
            {"name": "quality_score", "label": "质量分数", "type": "number"},
            {"name": "relevance_score", "label": "相关性分数", "type": "number"}
        ]
        
        # 添加提取的字段列
        for field in all_fields:
            columns.append({
                "name": field.replace(" ", "_").lower(),
                "label": field,
                "type": "text"
            })
        
        # 构建数据行
        rows = []
        for analysis in analyses:
            row = {
                "title": analysis.paper.title,
                "authors": "; ".join(analysis.paper.authors[:3]),
                "year": analysis.paper.year,
                "venue": analysis.paper.venue,
                "citation_count": analysis.paper.citation_count,
                "summary": analysis.summary,
                "quality_score": round(analysis.quality_score, 2),
                "relevance_score": round(analysis.relevance_score, 2),
                "url": analysis.paper.url,
                "doi": analysis.paper.doi or ""
            }
            
            # 添加提取的数据
            for field in all_fields:
                field_key = field.replace(" ", "_").lower()
                if field in analysis.extracted_data:
                    extracted = analysis.extracted_data[field]
                    row[field_key] = extracted.value
                    row[f"{field_key}_confidence"] = round(extracted.confidence, 2)
                else:
                    row[field_key] = "未提取"
                    row[f"{field_key}_confidence"] = 0.0
            
            rows.append(row)
        
        return {
            "columns": columns,
            "rows": rows,
            "metadata": {
                "total_papers": len(analyses),
                "extraction_fields": len(all_fields),
                "average_quality": round(sum(a.quality_score for a in analyses) / len(analyses), 2)
            }
        }

# 使用示例和测试
async def main():
    """测试结构化数据提取"""
    import os
    from dotenv import load_dotenv
    from academic_apis import AcademicSearchEngine
    
    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        print("请设置GROQ_API_KEY环境变量")
        return
    
    # 获取一些测试论文
    academic_engine = AcademicSearchEngine()
    papers = await academic_engine.search_papers(
        query="machine learning healthcare",
        max_results=5
    )
    
    if not papers:
        print("未找到测试论文")
        return
    
    # 初始化提取器
    extractor = StructuredDataExtractor(groq_api_key)
    
    # 定义自定义列
    custom_columns = [
        CustomColumn(
            name="技术创新点",
            description="论文的主要技术创新或贡献",
            extraction_prompt="识别论文的主要技术创新点或贡献",
            data_type="text"
        )
    ]
    
    # 提取数据
    print("开始提取结构化数据...")
    analyses = await extractor.batch_extract(
        papers=papers[:3],  # 测试前3篇
        fields=[
            ExtractionField.RESEARCH_METHOD,
            ExtractionField.SAMPLE_SIZE,
            ExtractionField.MAIN_FINDINGS,
            ExtractionField.STUDY_TYPE
        ],
        custom_columns=custom_columns,
        user_query="machine learning in healthcare applications"
    )
    
    # 展示结果
    for analysis in analyses:
        print(f"\\n=== {analysis.paper.title[:50]}... ===")
        print(f"质量分数: {analysis.quality_score:.2f}")
        print(f"相关性分数: {analysis.relevance_score:.2f}")
        print(f"摘要: {analysis.summary}")
        
        print("\\n提取的数据:")
        for field_name, extracted in analysis.extracted_data.items():
            print(f"  {field_name}: {extracted.value} (置信度: {extracted.confidence:.2f})")
        
        if analysis.extraction_notes:
            print(f"\\n提取注意: {'; '.join(analysis.extraction_notes)}")
    
    # 导出研究矩阵
    matrix = extractor.export_to_matrix(analyses)
    print(f"\\n=== 研究矩阵 ===")
    print(f"列数: {len(matrix['columns'])}")
    print(f"行数: {len(matrix['rows'])}")
    print(f"平均质量分数: {matrix['metadata']['average_quality']}")

if __name__ == "__main__":
    asyncio.run(main())