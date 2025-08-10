"""
增强语义搜索模块 - Paper God集成Semantic Scholar MCP的核心搜索组件
提供基于MCP协议的语义搜索和论文分析功能
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

from mcp_client import get_mcp_client, MCPResponse
from multi_source_engine import Paper

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SemanticPaper(Paper):
    """扩展的语义论文数据结构"""
    semantic_scholar_id: Optional[str] = None
    authors_details: List[Dict[str, Any]] = field(default_factory=list)
    references_count: int = 0
    influential_citation_count: int = 0
    fields_of_study: List[str] = field(default_factory=list)
    publication_types: List[str] = field(default_factory=list)
    venue_details: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None

@dataclass
class SearchFilter:
    """搜索过滤条件"""
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_citations: Optional[int] = None
    authors: List[str] = field(default_factory=list)
    venues: List[str] = field(default_factory=list)
    fields_of_study: List[str] = field(default_factory=list)
    publication_types: List[str] = field(default_factory=list)
    open_access_only: bool = False

class EnhancedSemanticSearch:
    """增强语义搜索引擎 - 基于Semantic Scholar MCP"""
    
    def __init__(self):
        self.mcp_client = None
        self._cache = {}
        self._cache_expiry = timedelta(minutes=30)
        
    async def _get_client(self):
        """获取MCP客户端"""
        if self.mcp_client is None:
            self.mcp_client = await get_mcp_client()
        return self.mcp_client
    
    def _cache_key(self, method: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [method] + [f"{k}:{v}" for k, v in sorted(kwargs.items())]
        return "|".join(key_parts)
    
    async def search_papers(self, query: str, limit: int = 20, 
                          search_filter: Optional[SearchFilter] = None) -> List[SemanticPaper]:
        """增强的论文搜索"""
        try:
            # 检查缓存
            filter_key = self._serialize_filter(search_filter) if search_filter else ""
            cache_key = self._cache_key("search_papers", query=query, limit=limit, filter=filter_key)
            
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if datetime.now() - timestamp < self._cache_expiry:
                    logger.info(f"从缓存返回语义搜索结果: {query}")
                    return cached_data
            
            client = await self._get_client()
            
            # 构建搜索字段
            fields = [
                "title", "authors", "abstract", "year", "journal", "url", 
                "citationCount", "externalIds", "influentialCitationCount",
                "fieldsOfStudy", "publicationTypes", "venue", "references"
            ]
            
            # 调用MCP搜索
            response = await client.search_papers_semantic(
                query=query,
                limit=limit,
                fields=fields
            )
            
            if not response.success:
                logger.error(f"语义搜索失败: {response.error}")
                return []
            
            # 解析论文数据
            papers = self._parse_semantic_papers(response.data)
            
            # 应用过滤条件
            if search_filter:
                papers = self._apply_filters(papers, search_filter)
            
            # 缓存结果
            self._cache[cache_key] = (papers, datetime.now())
            
            logger.info(f"语义搜索完成，获得 {len(papers)} 篇论文: {query}")
            return papers
            
        except Exception as e:
            logger.error(f"语义搜索错误: {e}")
            return []
    
    def _serialize_filter(self, search_filter: SearchFilter) -> str:
        """序列化搜索过滤条件"""
        return json.dumps({
            'min_year': search_filter.min_year,
            'max_year': search_filter.max_year,
            'min_citations': search_filter.min_citations,
            'authors': search_filter.authors,
            'venues': search_filter.venues,
            'fields_of_study': search_filter.fields_of_study,
            'publication_types': search_filter.publication_types,
            'open_access_only': search_filter.open_access_only
        }, sort_keys=True)
    
    def _parse_semantic_papers(self, raw_data: Any) -> List[SemanticPaper]:
        """解析Semantic Scholar返回的论文数据"""
        papers = []
        
        try:
            # 处理不同的数据格式
            if isinstance(raw_data, dict):
                if "data" in raw_data:
                    results = raw_data["data"]
                elif "results" in raw_data:
                    results = raw_data["results"]
                else:
                    results = [raw_data]
            elif isinstance(raw_data, list):
                results = raw_data
            else:
                results = [raw_data]
                
            for paper_data in results:
                try:
                    # 提取基础论文信息
                    authors = []
                    authors_details = []
                    
                    if "authors" in paper_data and paper_data["authors"]:
                        for author in paper_data["authors"]:
                            if isinstance(author, dict):
                                author_name = author.get("name", "")
                                authors.append(author_name)
                                authors_details.append({
                                    "name": author_name,
                                    "authorId": author.get("authorId"),
                                    "url": author.get("url")
                                })
                            else:
                                authors.append(str(author))
                    
                    # 提取DOI和其他外部ID
                    doi = None
                    external_ids = paper_data.get("externalIds", {})
                    if external_ids and isinstance(external_ids, dict):
                        doi = external_ids.get("DOI")
                    
                    # 提取期刊信息
                    journal = ""
                    venue_details = None
                    if "journal" in paper_data and paper_data["journal"]:
                        if isinstance(paper_data["journal"], dict):
                            journal = paper_data["journal"].get("name", "")
                        else:
                            journal = str(paper_data["journal"])
                    
                    if "venue" in paper_data and paper_data["venue"]:
                        venue_details = paper_data["venue"]
                        if isinstance(venue_details, str):
                            journal = venue_details
                            venue_details = {"name": venue_details}
                    
                    # 提取研究领域
                    fields_of_study = []
                    if "fieldsOfStudy" in paper_data and paper_data["fieldsOfStudy"]:
                        fields_of_study = paper_data["fieldsOfStudy"]
                    
                    # 提取发表类型
                    publication_types = []
                    if "publicationTypes" in paper_data and paper_data["publicationTypes"]:
                        publication_types = paper_data["publicationTypes"]
                    
                    # 创建SemanticPaper对象
                    paper = SemanticPaper(
                        title=paper_data.get("title", ""),
                        authors=authors,
                        abstract=paper_data.get("abstract", ""),
                        year=paper_data.get("year"),
                        journal=journal,
                        url=paper_data.get("url", ""),
                        doi=doi,
                        citations=paper_data.get("citationCount", 0),
                        source="semantic_scholar_mcp",
                        semantic_scholar_id=paper_data.get("paperId"),
                        authors_details=authors_details,
                        references_count=len(paper_data.get("references", [])),
                        influential_citation_count=paper_data.get("influentialCitationCount", 0),
                        fields_of_study=fields_of_study,
                        publication_types=publication_types,
                        venue_details=venue_details
                    )
                    
                    papers.append(paper)
                    
                except Exception as e:
                    logger.warning(f"解析单篇论文数据失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析语义论文数据失败: {e}")
            
        return papers
    
    def _apply_filters(self, papers: List[SemanticPaper], search_filter: SearchFilter) -> List[SemanticPaper]:
        """应用搜索过滤条件"""
        filtered_papers = []
        
        for paper in papers:
            # 年份过滤
            if search_filter.min_year and paper.year and paper.year < search_filter.min_year:
                continue
            if search_filter.max_year and paper.year and paper.year > search_filter.max_year:
                continue
            
            # 引用数过滤
            if search_filter.min_citations and paper.citations < search_filter.min_citations:
                continue
            
            # 作者过滤
            if search_filter.authors:
                author_match = False
                for filter_author in search_filter.authors:
                    for paper_author in paper.authors:
                        if filter_author.lower() in paper_author.lower():
                            author_match = True
                            break
                    if author_match:
                        break
                if not author_match:
                    continue
            
            # 期刊/会议过滤
            if search_filter.venues:
                venue_match = False
                for filter_venue in search_filter.venues:
                    if filter_venue.lower() in paper.journal.lower():
                        venue_match = True
                        break
                if not venue_match:
                    continue
            
            # 研究领域过滤
            if search_filter.fields_of_study:
                field_match = False
                for filter_field in search_filter.fields_of_study:
                    for paper_field in paper.fields_of_study:
                        if filter_field.lower() in paper_field.lower():
                            field_match = True
                            break
                    if field_match:
                        break
                if not field_match:
                    continue
            
            # 发表类型过滤
            if search_filter.publication_types:
                type_match = False
                for filter_type in search_filter.publication_types:
                    if filter_type in paper.publication_types:
                        type_match = True
                        break
                if not type_match:
                    continue
            
            filtered_papers.append(paper)
        
        return filtered_papers
    
    async def get_paper_details(self, paper_id: str) -> Optional[SemanticPaper]:
        """获取论文详细信息"""
        try:
            # 检查缓存
            cache_key = self._cache_key("get_paper_details", paper_id=paper_id)
            
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if datetime.now() - timestamp < self._cache_expiry:
                    logger.info(f"从缓存返回论文详情: {paper_id}")
                    return cached_data
            
            client = await self._get_client()
            
            # 调用MCP获取论文详情
            response = await client.get_paper_details(paper_id)
            
            if not response.success:
                logger.error(f"获取论文详情失败 {paper_id}: {response.error}")
                return None
            
            # 解析论文数据
            papers = self._parse_semantic_papers([response.data])
            paper = papers[0] if papers else None
            
            # 缓存结果
            if paper:
                self._cache[cache_key] = (paper, datetime.now())
            
            return paper
            
        except Exception as e:
            logger.error(f"获取论文详情错误 {paper_id}: {e}")
            return None
    
    async def get_related_papers(self, paper_id: str, limit: int = 10) -> List[SemanticPaper]:
        """获取相关论文"""
        try:
            # 这里可以通过获取论文的引用和被引用来找相关论文
            # 或者使用semantic similarity搜索
            
            # 首先获取论文详情
            paper = await self.get_paper_details(paper_id)
            if not paper:
                return []
            
            # 使用论文标题的关键词进行相似搜索
            # 这是一个简化的实现，实际可以使用更复杂的算法
            title_keywords = paper.title.split()[:5]  # 取前5个词
            query = " ".join(title_keywords)
            
            related_papers = await self.search_papers(query, limit=limit*2)
            
            # 过滤掉原论文本身
            related_papers = [p for p in related_papers if p.semantic_scholar_id != paper_id]
            
            return related_papers[:limit]
            
        except Exception as e:
            logger.error(f"获取相关论文错误 {paper_id}: {e}")
            return []
    
    async def search_by_author(self, author_name: str, limit: int = 20) -> List[SemanticPaper]:
        """按作者搜索论文"""
        search_filter = SearchFilter(authors=[author_name])
        return await self.search_papers(f"author:{author_name}", limit=limit, search_filter=search_filter)
    
    async def search_by_venue(self, venue_name: str, limit: int = 20) -> List[SemanticPaper]:
        """按期刊/会议搜索论文"""
        search_filter = SearchFilter(venues=[venue_name])
        return await self.search_papers(f"venue:{venue_name}", limit=limit, search_filter=search_filter)
    
    async def advanced_search(self, query: str, author: Optional[str] = None,
                            venue: Optional[str] = None, year_range: Optional[tuple] = None,
                            min_citations: Optional[int] = None, limit: int = 20) -> List[SemanticPaper]:
        """高级搜索"""
        search_filter = SearchFilter()
        
        if author:
            search_filter.authors = [author]
        if venue:
            search_filter.venues = [venue]
        if year_range:
            search_filter.min_year = year_range[0]
            search_filter.max_year = year_range[1]
        if min_citations:
            search_filter.min_citations = min_citations
        
        return await self.search_papers(query, limit=limit, search_filter=search_filter)
    
    def get_search_statistics(self, papers: List[SemanticPaper]) -> Dict[str, Any]:
        """获取搜索结果统计信息"""
        if not papers:
            return {}
        
        # 年份分布
        year_distribution = {}
        for paper in papers:
            if paper.year:
                year_distribution[paper.year] = year_distribution.get(paper.year, 0) + 1
        
        # 期刊分布
        venue_distribution = {}
        for paper in papers:
            if paper.journal:
                venue_distribution[paper.journal] = venue_distribution.get(paper.journal, 0) + 1
        
        # 研究领域分布
        field_distribution = {}
        for paper in papers:
            for field in paper.fields_of_study:
                field_distribution[field] = field_distribution.get(field, 0) + 1
        
        # 引用统计
        citations = [paper.citations for paper in papers if paper.citations]
        avg_citations = sum(citations) / len(citations) if citations else 0
        max_citations = max(citations) if citations else 0
        
        return {
            "total_papers": len(papers),
            "year_distribution": dict(sorted(year_distribution.items())),
            "top_venues": dict(sorted(venue_distribution.items(), key=lambda x: x[1], reverse=True)[:10]),
            "top_fields": dict(sorted(field_distribution.items(), key=lambda x: x[1], reverse=True)[:10]),
            "citation_stats": {
                "average": round(avg_citations, 2),
                "maximum": max_citations,
                "total": sum(citations)
            }
        }
    
    async def close(self):
        """关闭搜索引擎"""
        self._cache.clear()
        logger.info("增强语义搜索引擎已关闭")

# 使用示例
async def main():
    """测试增强语义搜索"""
    search_engine = EnhancedSemanticSearch()
    
    try:
        # 基础搜索
        papers = await search_engine.search_papers("machine learning", limit=5)
        print(f"找到 {len(papers)} 篇论文")
        
        # 高级搜索
        advanced_papers = await search_engine.advanced_search(
            query="deep learning",
            year_range=(2020, 2024),
            min_citations=10,
            limit=5
        )
        print(f"高级搜索找到 {len(advanced_papers)} 篇论文")
        
        # 获取统计信息
        if papers:
            stats = search_engine.get_search_statistics(papers)
            print(f"搜索统计: {stats}")
            
    finally:
        await search_engine.close()

if __name__ == "__main__":
    asyncio.run(main())