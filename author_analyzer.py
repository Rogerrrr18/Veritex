"""
作者分析模块 - Paper God作者网络分析核心组件
集成Open Alex MCP实现作者搜索、档案分析和合作关系分析
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

from mcp_client import get_mcp_client, MCPResponse

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Author:
    """作者数据结构"""
    id: str
    name: str
    display_name: str
    orcid: Optional[str] = None
    institutions: List[str] = field(default_factory=list)
    research_areas: List[str] = field(default_factory=list)
    works_count: int = 0
    cited_by_count: int = 0
    h_index: Optional[int] = None
    i10_index: Optional[int] = None
    homepage_url: Optional[str] = None
    image_url: Optional[str] = None
    
@dataclass
class AuthorWork:
    """作者作品数据结构"""
    id: str
    title: str
    authors: List[str]
    publication_year: Optional[int]
    journal: str
    doi: Optional[str] = None
    citation_count: int = 0
    is_open_access: bool = False
    type: str = "article"
    abstract: Optional[str] = None
    url: Optional[str] = None
    
@dataclass
class CollaborationNetwork:
    """合作网络数据结构"""
    primary_author: Author
    collaborators: List[Tuple[Author, int]]  # (合作者, 合作次数)
    collaboration_strength: Dict[str, float]  # 合作强度评分
    common_institutions: List[str]
    research_overlap_areas: List[str]

class AuthorAnalyzer:
    """作者分析器 - 基于Open Alex MCP的核心分析引擎"""
    
    def __init__(self):
        self.mcp_client = None
        self._cache = {}  # 简单的内存缓存
        self._cache_expiry = timedelta(hours=1)
        
    async def _get_client(self):
        """获取MCP客户端"""
        if self.mcp_client is None:
            self.mcp_client = await get_mcp_client()
        return self.mcp_client
    
    def _cache_key(self, method: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [method] + [f"{k}:{v}" for k, v in sorted(kwargs.items())]
        return "|".join(key_parts)
    
    async def search_authors(self, query: str, institution: Optional[str] = None,
                           research_topic: Optional[str] = None, limit: int = 20) -> List[Author]:
        """搜索作者"""
        try:
            # 检查缓存
            cache_key = self._cache_key("search_authors", query=query, 
                                      institution=institution or "", 
                                      research_topic=research_topic or "", 
                                      limit=limit)
            
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if datetime.now() - timestamp < self._cache_expiry:
                    logger.info(f"从缓存返回作者搜索结果: {query}")
                    return cached_data
            
            client = await self._get_client()
            
            # 调用MCP搜索作者
            response = await client.search_authors(
                query=query,
                institution=institution,
                research_topic=research_topic,
                limit=limit
            )
            
            if not response.success:
                logger.error(f"作者搜索失败: {response.error}")
                return []
            
            # 解析作者数据
            authors = self._parse_authors_data(response.data)
            
            # 缓存结果
            self._cache[cache_key] = (authors, datetime.now())
            
            logger.info(f"搜索到 {len(authors)} 位作者: {query}")
            return authors
            
        except Exception as e:
            logger.error(f"作者搜索错误: {e}")
            return []
    
    def _parse_authors_data(self, raw_data: Any) -> List[Author]:
        """解析原始作者数据"""
        authors = []
        
        try:
            # 假设Open Alex MCP返回的数据格式
            if isinstance(raw_data, dict) and "results" in raw_data:
                results = raw_data["results"]
            elif isinstance(raw_data, list):
                results = raw_data
            else:
                results = [raw_data]
            
            for author_data in results:
                try:
                    # 提取机构信息
                    institutions = []
                    if "affiliations" in author_data:
                        for affiliation in author_data["affiliations"]:
                            if isinstance(affiliation, dict):
                                institutions.append(affiliation.get("display_name", ""))
                            else:
                                institutions.append(str(affiliation))
                    
                    # 提取研究领域
                    research_areas = []
                    if "x_concepts" in author_data:
                        for concept in author_data["x_concepts"][:5]:  # 取前5个主要领域
                            research_areas.append(concept.get("display_name", ""))
                    
                    author = Author(
                        id=author_data.get("id", ""),
                        name=author_data.get("name", ""),
                        display_name=author_data.get("display_name", ""),
                        orcid=author_data.get("orcid"),
                        institutions=institutions,
                        research_areas=research_areas,
                        works_count=author_data.get("works_count", 0),
                        cited_by_count=author_data.get("cited_by_count", 0),
                        h_index=author_data.get("summary_stats", {}).get("h_index"),
                        i10_index=author_data.get("summary_stats", {}).get("i10_index"),
                        homepage_url=author_data.get("homepage_url"),
                        image_url=author_data.get("image_url")
                    )
                    
                    authors.append(author)
                    
                except Exception as e:
                    logger.warning(f"解析单个作者数据失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析作者数据失败: {e}")
            
        return authors
    
    async def get_author_profile(self, author_id: str) -> Optional[Author]:
        """获取作者详细档案"""
        try:
            # 这里可以调用更详细的作者信息API
            # 由于Open Alex MCP可能没有专门的get_author接口，我们使用搜索
            authors = await self.search_authors(query=author_id, limit=1)
            return authors[0] if authors else None
            
        except Exception as e:
            logger.error(f"获取作者档案失败 {author_id}: {e}")
            return None
    
    async def get_author_works(self, author_id: str, publication_type: Optional[str] = None,
                             min_citations: Optional[int] = None, limit: int = 50) -> List[AuthorWork]:
        """获取作者的作品列表"""
        try:
            # 检查缓存
            cache_key = self._cache_key("get_author_works", author_id=author_id,
                                      publication_type=publication_type or "",
                                      min_citations=min_citations or 0,
                                      limit=limit)
            
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if datetime.now() - timestamp < self._cache_expiry:
                    logger.info(f"从缓存返回作者作品: {author_id}")
                    return cached_data
            
            client = await self._get_client()
            
            # 调用MCP获取作者作品
            response = await client.get_author_works(
                author_id=author_id,
                publication_type=publication_type,
                min_citations=min_citations,
                limit=limit
            )
            
            if not response.success:
                logger.error(f"获取作者作品失败 {author_id}: {response.error}")
                return []
            
            # 解析作品数据
            works = self._parse_works_data(response.data)
            
            # 缓存结果
            self._cache[cache_key] = (works, datetime.now())
            
            logger.info(f"获取到 {len(works)} 篇作品，作者: {author_id}")
            return works
            
        except Exception as e:
            logger.error(f"获取作者作品错误 {author_id}: {e}")
            return []
    
    def _parse_works_data(self, raw_data: Any) -> List[AuthorWork]:
        """解析作品数据"""
        works = []
        
        try:
            # 假设返回的数据格式
            if isinstance(raw_data, dict) and "results" in raw_data:
                results = raw_data["results"]
            elif isinstance(raw_data, list):
                results = raw_data
            else:
                results = [raw_data]
                
            for work_data in results:
                try:
                    # 提取作者列表
                    authors = []
                    if "authorships" in work_data:
                        for authorship in work_data["authorships"]:
                            author = authorship.get("author", {})
                            authors.append(author.get("display_name", ""))
                    
                    # 提取期刊信息
                    journal = ""
                    if "primary_location" in work_data:
                        location = work_data["primary_location"]
                        if location and "source" in location:
                            journal = location["source"].get("display_name", "")
                    
                    work = AuthorWork(
                        id=work_data.get("id", ""),
                        title=work_data.get("title", ""),
                        authors=authors,
                        publication_year=work_data.get("publication_year"),
                        journal=journal,
                        doi=work_data.get("doi"),
                        citation_count=work_data.get("cited_by_count", 0),
                        is_open_access=work_data.get("open_access", {}).get("is_oa", False),
                        type=work_data.get("type", "article"),
                        abstract=work_data.get("abstract"),
                        url=work_data.get("landing_page_url")
                    )
                    
                    works.append(work)
                    
                except Exception as e:
                    logger.warning(f"解析单个作品数据失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析作品数据失败: {e}")
            
        return works
    
    async def analyze_collaboration_network(self, author_id: str, depth: int = 2) -> Optional[CollaborationNetwork]:
        """分析作者的合作网络"""
        try:
            # 获取主作者信息
            primary_author = await self.get_author_profile(author_id)
            if not primary_author:
                return None
            
            # 获取作者的作品
            works = await self.get_author_works(author_id, limit=100)
            
            # 分析合作者
            collaborator_counts = {}
            collaborator_details = {}
            
            for work in works:
                for co_author_name in work.authors:
                    if co_author_name != primary_author.display_name:
                        collaborator_counts[co_author_name] = collaborator_counts.get(co_author_name, 0) + 1
            
            # 获取主要合作者的详细信息
            top_collaborators = sorted(collaborator_counts.items(), 
                                     key=lambda x: x[1], reverse=True)[:10]
            
            collaborators_with_details = []
            for collaborator_name, count in top_collaborators:
                # 搜索合作者详细信息
                collaborator_results = await self.search_authors(collaborator_name, limit=1)
                if collaborator_results:
                    collaborators_with_details.append((collaborator_results[0], count))
            
            # 计算合作强度
            total_works = len(works)
            collaboration_strength = {}
            for collaborator, count in collaborators_with_details:
                strength = count / total_works if total_works > 0 else 0
                collaboration_strength[collaborator.id] = strength
            
            # 找出共同机构和研究领域
            common_institutions = set(primary_author.institutions)
            research_overlap_areas = set(primary_author.research_areas)
            
            for collaborator, _ in collaborators_with_details:
                common_institutions.intersection_update(collaborator.institutions)
                research_overlap_areas.intersection_update(collaborator.research_areas)
            
            network = CollaborationNetwork(
                primary_author=primary_author,
                collaborators=collaborators_with_details,
                collaboration_strength=collaboration_strength,
                common_institutions=list(common_institutions),
                research_overlap_areas=list(research_overlap_areas)
            )
            
            logger.info(f"分析合作网络完成，找到 {len(collaborators_with_details)} 个主要合作者")
            return network
            
        except Exception as e:
            logger.error(f"分析合作网络失败 {author_id}: {e}")
            return None
    
    async def get_author_research_trajectory(self, author_id: str) -> Dict[str, Any]:
        """分析作者的研究轨迹"""
        try:
            works = await self.get_author_works(author_id, limit=200)
            
            if not works:
                return {}
            
            # 按年份分组
            yearly_stats = {}
            research_topics_by_year = {}
            
            for work in works:
                year = work.publication_year
                if not year:
                    continue
                    
                if year not in yearly_stats:
                    yearly_stats[year] = {
                        'publication_count': 0,
                        'total_citations': 0,
                        'journals': set(),
                        'collaboration_count': 0
                    }
                
                yearly_stats[year]['publication_count'] += 1
                yearly_stats[year]['total_citations'] += work.citation_count
                yearly_stats[year]['journals'].add(work.journal)
                yearly_stats[year]['collaboration_count'] += len(work.authors) - 1
                
                # 简单的主题提取（基于标题关键词）
                if year not in research_topics_by_year:
                    research_topics_by_year[year] = []
                research_topics_by_year[year].append(work.title)
            
            # 转换为序列化格式
            for year in yearly_stats:
                yearly_stats[year]['journals'] = list(yearly_stats[year]['journals'])
            
            trajectory = {
                'yearly_statistics': yearly_stats,
                'research_evolution': research_topics_by_year,
                'career_span': max(yearly_stats.keys()) - min(yearly_stats.keys()) if yearly_stats else 0,
                'total_publications': len(works),
                'total_citations': sum(work.citation_count for work in works),
                'average_citations_per_paper': sum(work.citation_count for work in works) / len(works) if works else 0
            }
            
            return trajectory
            
        except Exception as e:
            logger.error(f"分析研究轨迹失败 {author_id}: {e}")
            return {}
    
    async def close(self):
        """关闭分析器"""
        # 清理缓存
        self._cache.clear()
        logger.info("作者分析器已关闭")

# 使用示例
async def main():
    """测试作者分析器"""
    analyzer = AuthorAnalyzer()
    
    try:
        # 搜索作者
        authors = await analyzer.search_authors("machine learning", limit=3)
        print(f"找到 {len(authors)} 位作者")
        
        if authors:
            author = authors[0]
            print(f"\n分析作者: {author.display_name}")
            
            # 获取作者作品
            works = await analyzer.get_author_works(author.id, limit=10)
            print(f"找到 {len(works)} 篇作品")
            
            # 分析合作网络
            network = await analyzer.analyze_collaboration_network(author.id)
            if network:
                print(f"主要合作者: {len(network.collaborators)} 个")
            
            # 分析研究轨迹
            trajectory = await analyzer.get_author_research_trajectory(author.id)
            print(f"研究轨迹: {trajectory.get('career_span', 0)} 年")
            
    finally:
        await analyzer.close()

if __name__ == "__main__":
    asyncio.run(main())