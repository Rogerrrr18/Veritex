"""
Elicit风格的学术研究引擎
集成语义搜索、结构化数据提取、查询意图识别等功能
"""

import asyncio
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging

# 导入所有模块
from academic_apis import AcademicSearchEngine, Paper
from semantic_search import HybridSearchEngine, SearchResult
from enhanced_keyword_expander import EnhancedKeywordExpander, KeywordExpansionResult
from query_intent_analyzer import QueryIntentAnalyzer, QueryProcessor, ProcessedQuery
from structured_data_extractor import (
    StructuredDataExtractor, PaperAnalysis, ExtractionField, CustomColumn
)

logger = logging.getLogger(__name__)

@dataclass
class ResearchSession:
    """研究会话信息"""
    session_id: str
    original_query: str
    processed_query: ProcessedQuery
    expansion_result: KeywordExpansionResult
    search_results: List[SearchResult]
    paper_analyses: List[PaperAnalysis]
    research_matrix: Dict[str, Any]
    processing_time: float
    reasoning_trace: List[str]  # 推理过程记录

class ElicitStyleResearchEngine:
    """Elicit风格的研究引擎"""
    
    def __init__(self, groq_api_key: str, semantic_scholar_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key
        
        # 初始化各个组件
        self.academic_search = AcademicSearchEngine(semantic_scholar_api_key)
        self.semantic_search = HybridSearchEngine()
        self.keyword_expander = EnhancedKeywordExpander(groq_api_key)
        self.query_analyzer = QueryIntentAnalyzer(groq_api_key)
        self.query_processor = QueryProcessor(self.query_analyzer)
        self.data_extractor = StructuredDataExtractor(groq_api_key)
        
        # 推理过程跟踪
        self.reasoning_trace = []
    
    def _add_reasoning_step(self, step: str):
        """添加推理步骤"""
        self.reasoning_trace.append(f"[{time.strftime('%H:%M:%S')}] {step}")
        logger.info(step)
    
    async def research(
        self,
        query: str,
        max_papers: int = 50,
        extraction_fields: Optional[List[ExtractionField]] = None,
        custom_columns: Optional[List[CustomColumn]] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> ResearchSession:
        """
        执行完整的学术研究流程
        
        Args:
            query: 用户查询
            max_papers: 最大论文数量
            extraction_fields: 要提取的字段
            custom_columns: 自定义列
            year_min: 最早年份
            year_max: 最晚年份
            session_id: 会话ID
        """
        start_time = time.time()
        self.reasoning_trace = []
        session_id = session_id or f"session_{int(time.time())}"
        
        self._add_reasoning_step(f"开始研究会话: {session_id}")
        self._add_reasoning_step(f"用户查询: {query}")
        
        try:
            # 第1步：查询意图分析
            self._add_reasoning_step("步骤1: 分析查询意图...")
            processed_query = await self.query_processor.process_query(query)
            
            self._add_reasoning_step(
                f"检测到查询类型: {processed_query.query_intent.query_type.value}"
            )
            self._add_reasoning_step(
                f"查询复杂度: {processed_query.query_intent.complexity.value}"
            )
            
            # 第2步：关键词扩展和学科检测
            self._add_reasoning_step("步骤2: 关键词扩展和学科检测...")
            expansion_result = await self.keyword_expander.comprehensive_expansion(
                query, max_keywords=8
            )
            
            self._add_reasoning_step(
                f"检测学科: {expansion_result.discipline_info.primary_discipline.value}"
            )
            self._add_reasoning_step(
                f"扩展关键词: {expansion_result.expanded_keywords}"
            )
            
            # 第3步：学术论文搜索
            self._add_reasoning_step("步骤3: 执行学术论文搜索...")
            
            # 使用处理后的查询进行搜索
            search_queries = processed_query.search_queries
            all_papers = []
            
            for i, search_query in enumerate(search_queries[:2]):  # 限制搜索查询数量
                self._add_reasoning_step(f"搜索策略 {i+1}: {search_query}")
                
                papers = await self.academic_search.search_papers(
                    query=search_query,
                    max_results=max_papers // len(search_queries),
                    year_min=year_min,
                    year_max=year_max,
                    fields_of_study=[expansion_result.discipline_info.primary_discipline.value] if expansion_result.discipline_info.primary_discipline.value != "未知领域" else None
                )
                
                all_papers.extend(papers)
                self._add_reasoning_step(f"获得 {len(papers)} 篇论文")
            
            # 去重
            unique_papers = self._deduplicate_papers(all_papers)
            self._add_reasoning_step(f"去重后共 {len(unique_papers)} 篇论文")
            
            # 第4步：语义搜索和重排序
            self._add_reasoning_step("步骤4: 语义搜索和相关性排序...")
            
            if unique_papers:
                semantic_results = self.semantic_search.hybrid_search(
                    query=query,
                    papers=unique_papers,
                    top_k=min(max_papers, len(unique_papers)),
                    semantic_weight=0.7,
                    keyword_weight=0.3
                )
                
                self._add_reasoning_step(f"语义搜索完成，保留 {len(semantic_results)} 篇高相关性论文")
            else:
                semantic_results = []
                self._add_reasoning_step("未找到相关论文")
            
            # 第5步：结构化数据提取
            self._add_reasoning_step("步骤5: 结构化数据提取...")
            
            if semantic_results:
                # 提取前N篇论文的详细信息
                top_papers = [result.paper for result in semantic_results[:20]]
                
                # 根据查询类型选择提取字段
                if extraction_fields is None:
                    extraction_fields = self._select_extraction_fields(
                        processed_query.query_intent.query_type,
                        expansion_result.discipline_info.primary_discipline
                    )
                
                paper_analyses = await self.data_extractor.batch_extract(
                    papers=top_papers,
                    fields=extraction_fields,
                    custom_columns=custom_columns,
                    user_query=query,
                    max_concurrent=3
                )
                
                self._add_reasoning_step(f"完成 {len(paper_analyses)} 篇论文的数据提取")
            else:
                paper_analyses = []
            
            # 第6步：生成研究矩阵
            self._add_reasoning_step("步骤6: 生成研究矩阵...")
            research_matrix = self.data_extractor.export_to_matrix(paper_analyses)
            
            # 计算处理时间
            processing_time = time.time() - start_time
            self._add_reasoning_step(f"研究完成，总耗时 {processing_time:.2f} 秒")
            
            # 创建研究会话结果
            session = ResearchSession(
                session_id=session_id,
                original_query=query,
                processed_query=processed_query,
                expansion_result=expansion_result,
                search_results=semantic_results,
                paper_analyses=paper_analyses,
                research_matrix=research_matrix,
                processing_time=processing_time,
                reasoning_trace=self.reasoning_trace.copy()
            )
            
            return session
            
        except Exception as e:
            self._add_reasoning_step(f"研究过程出错: {str(e)}")
            logger.error(f"研究引擎错误: {e}")
            raise
    
    def _deduplicate_papers(self, papers: List[Paper]) -> List[Paper]:
        """论文去重"""
        seen_titles = set()
        unique_papers = []
        
        for paper in papers:
            title_key = paper.title.lower().strip()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_papers.append(paper)
        
        return unique_papers
    
    def _select_extraction_fields(
        self,
        query_type,
        discipline
    ) -> List[ExtractionField]:
        """根据查询类型和学科选择提取字段"""
        
        # 基础字段
        fields = [
            ExtractionField.RESEARCH_METHOD,
            ExtractionField.MAIN_FINDINGS,
            ExtractionField.STUDY_TYPE
        ]
        
        # 根据学科添加特定字段
        if discipline.value in ["医学", "心理学", "生物学"]:
            fields.extend([
                ExtractionField.SAMPLE_SIZE,
                ExtractionField.POPULATION,
                ExtractionField.P_VALUE
            ])
        
        if discipline.value == "医学":
            fields.extend([
                ExtractionField.INTERVENTION,
                ExtractionField.OUTCOME_MEASURES
            ])
        
        # 根据查询类型调整
        from query_intent_analyzer import QueryType
        
        if query_type == QueryType.COMPARISON:
            fields.append(ExtractionField.LIMITATIONS)
        elif query_type == QueryType.REVIEW_REQUEST:
            fields.extend([
                ExtractionField.PUBLICATION_TYPE,
                ExtractionField.LIMITATIONS
            ])
        
        return list(set(fields))  # 去重
    
    async def quick_search(
        self,
        query: str,
        max_papers: int = 20
    ) -> Dict[str, Any]:
        """
        快速搜索模式：只进行搜索和基本排序，不做深度提取
        """
        start_time = time.time()
        
        # 简化的搜索流程
        expansion_result = await self.keyword_expander.comprehensive_expansion(query)
        
        papers = await self.academic_search.search_papers(
            query=query,
            max_results=max_papers,
            use_both_apis=False  # 只用一个API源加快速度
        )
        
        if papers:
            # 简单的语义排序
            semantic_results = self.semantic_search.hybrid_search(
                query=query,
                papers=papers,
                top_k=max_papers,
                semantic_weight=0.6,
                keyword_weight=0.4
            )
        else:
            semantic_results = []
        
        processing_time = time.time() - start_time
        
        return {
            "query": query,
            "expanded_keywords": expansion_result.expanded_keywords,
            "discipline": expansion_result.discipline_info.primary_discipline.value,
            "papers": [
                {
                    "title": result.paper.title,
                    "authors": result.paper.authors,
                    "year": result.paper.year,
                    "venue": result.paper.venue,
                    "citation_count": result.paper.citation_count,
                    "url": result.paper.url,
                    "similarity_score": result.similarity_score,
                    "abstract": result.paper.abstract[:300] + "..." if result.paper.abstract else ""
                }
                for result in semantic_results
            ],
            "total_papers": len(semantic_results),
            "processing_time": processing_time
        }
    
    def get_reasoning_trace(self) -> List[str]:
        """获取推理过程"""
        return self.reasoning_trace.copy()
    
    def export_session_summary(self, session: ResearchSession) -> Dict[str, Any]:
        """导出会话摘要"""
        return {
            "session_id": session.session_id,
            "query": session.original_query,
            "query_analysis": {
                "type": session.processed_query.query_intent.query_type.value,
                "complexity": session.processed_query.query_intent.complexity.value,
                "entities": session.processed_query.query_intent.entities,
                "research_focus": session.processed_query.query_intent.research_focus
            },
            "keyword_expansion": {
                "original": session.expansion_result.original_keywords,
                "expanded": session.expansion_result.expanded_keywords,
                "discipline": session.expansion_result.discipline_info.primary_discipline.value,
                "strategy": session.expansion_result.expansion_strategy
            },
            "search_results": {
                "total_papers": len(session.search_results),
                "avg_similarity": sum(r.similarity_score for r in session.search_results) / len(session.search_results) if session.search_results else 0,
                "top_papers": [
                    {
                        "title": r.paper.title,
                        "similarity": r.similarity_score,
                        "citations": r.paper.citation_count
                    }
                    for r in session.search_results[:5]
                ]
            },
            "data_extraction": {
                "analyzed_papers": len(session.paper_analyses),
                "avg_quality_score": sum(a.quality_score for a in session.paper_analyses) / len(session.paper_analyses) if session.paper_analyses else 0,
                "extraction_fields": len(session.research_matrix.get("columns", [])),
                "metadata": session.research_matrix.get("metadata", {})
            },
            "performance": {
                "processing_time": session.processing_time,
                "steps_completed": len(session.reasoning_trace)
            },
            "reasoning_trace": session.reasoning_trace
        }

# 测试和使用示例
async def main():
    """测试Elicit风格研究引擎"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        print("请设置GROQ_API_KEY环境变量")
        return
    
    # 创建研究引擎
    engine = ElicitStyleResearchEngine(groq_api_key)
    
    # 测试查询
    test_queries = [
        "机器学习在医学诊断中的应用",
        "What are the effects of mindfulness meditation on anxiety?",
        "Compare transformer vs CNN for image classification"
    ]
    
    for query in test_queries:
        print(f"\\n{'='*80}")
        print(f"研究查询: {query}")
        print('='*80)
        
        try:
            # 执行完整研究
            session = await engine.research(
                query=query,
                max_papers=15,
                year_min=2020
            )
            
            # 展示结果摘要
            summary = engine.export_session_summary(session)
            
            print(f"\\n查询分析:")
            print(f"  类型: {summary['query_analysis']['type']}")
            print(f"  复杂度: {summary['query_analysis']['complexity']}")
            print(f"  研究焦点: {summary['query_analysis']['research_focus']}")
            
            print(f"\\n关键词扩展:")
            print(f"  学科: {summary['keyword_expansion']['discipline']}")
            print(f"  扩展策略: {summary['keyword_expansion']['strategy']}")
            print(f"  扩展关键词: {summary['keyword_expansion']['expanded']}")
            
            print(f"\\n搜索结果:")
            print(f"  找到论文: {summary['search_results']['total_papers']} 篇")
            print(f"  平均相似度: {summary['search_results']['avg_similarity']:.3f}")
            
            print(f"\\n数据提取:")
            print(f"  分析论文: {summary['data_extraction']['analyzed_papers']} 篇")
            print(f"  平均质量分数: {summary['data_extraction']['avg_quality_score']:.3f}")
            print(f"  提取字段: {summary['data_extraction']['extraction_fields']} 个")
            
            print(f"\\n性能统计:")
            print(f"  总耗时: {summary['performance']['processing_time']:.2f} 秒")
            print(f"  处理步骤: {summary['performance']['steps_completed']} 步")
            
            # 展示top 3论文
            if session.paper_analyses:
                print(f"\\n前3篇论文:")
                for i, analysis in enumerate(session.paper_analyses[:3], 1):
                    print(f"  {i}. {analysis.paper.title[:60]}...")
                    print(f"     质量: {analysis.quality_score:.2f}, 相关性: {analysis.relevance_score:.2f}")
                    print(f"     摘要: {analysis.summary}")
            
            # 展示推理过程（最后5步）
            print(f"\\n推理过程 (最后5步):")
            for step in session.reasoning_trace[-5:]:
                print(f"  {step}")
            
        except Exception as e:
            print(f"研究失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())