"""
学术论文API集成模块
集成Semantic Scholar和OpenAlex API，提供统一的论文搜索接口
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional, Union
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import time
from dataclasses import dataclass
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Paper:
    """标准化的论文数据结构"""
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    url: str
    venue: str
    citation_count: int
    doi: Optional[str]
    paper_id: str
    source: str  # 'semantic_scholar' 或 'openalex'
    fields_of_study: List[str]
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'authors': '; '.join(self.authors),
            'year': str(self.year) if self.year else '',
            'abstract': self.abstract[:300] + '...' if len(self.abstract) > 300 else self.abstract,
            'url': self.url,
            'venue': self.venue,
            'citation_count': self.citation_count,
            'doi': self.doi or '',
            'paper_id': self.paper_id,
            'source': self.source,
            'fields_of_study': ', '.join(self.fields_of_study)
        }

class SemanticScholarAPI:
    """Semantic Scholar API客户端"""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Paper-God-Academic-Search/1.0'
        }
        if self.api_key:
            headers['x-api-key'] = self.api_key
            
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_papers(
        self, 
        query: str, 
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        fields_of_study: Optional[List[str]] = None
    ) -> List[Paper]:
        """搜索论文"""
        
        url = f"{self.BASE_URL}/paper/search"
        params = {
            'query': query,
            'limit': min(limit, 100),  # API限制每次最多100个
            'fields': 'paperId,title,authors,year,abstract,url,venue,citationCount,externalIds,fieldsOfStudy'
        }
        
        # 添加年份过滤
        if year_min:
            params['year'] = f"{year_min}-"
        if year_max:
            if 'year' in params:
                params['year'] = f"{year_min}-{year_max}"
            else:
                params['year'] = f"-{year_max}"
                
        # 添加学科过滤
        if fields_of_study:
            params['fieldsOfStudy'] = ','.join(fields_of_study)
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    papers = []
                    
                    for item in data.get('data', []):
                        try:
                            paper = self._parse_semantic_scholar_paper(item)
                            if paper:
                                papers.append(paper)
                        except Exception as e:
                            logger.warning(f"解析论文数据失败: {e}")
                            continue
                    
                    logger.info(f"Semantic Scholar返回 {len(papers)} 篇论文")
                    return papers
                    
                elif response.status == 429:  # 速率限制
                    logger.warning("Semantic Scholar API速率限制，等待重试")
                    await asyncio.sleep(60)
                    raise aiohttp.ClientError("Rate limited")
                else:
                    logger.error(f"Semantic Scholar API错误: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Semantic Scholar搜索失败: {e}")
            return []
    
    def _parse_semantic_scholar_paper(self, item: Dict) -> Optional[Paper]:
        """解析Semantic Scholar返回的论文数据"""
        try:
            # 基本信息提取
            title = item.get('title', '').strip()
            if not title:
                return None
                
            # 作者信息
            authors = []
            for author in item.get('authors', []):
                if author.get('name'):
                    authors.append(author['name'])
            
            # 年份
            year = item.get('year')
            
            # 摘要
            abstract = item.get('abstract', '') or ''
            
            # URL - 优先使用DOI链接
            url = ""
            external_ids = item.get('externalIds', {})
            if external_ids.get('DOI'):
                url = f"https://doi.org/{external_ids['DOI']}"
            elif item.get('url'):
                url = item['url']
            
            # 场所
            venue = item.get('venue', '') or ''
            
            # 引用次数
            citation_count = item.get('citationCount', 0) or 0
            
            # DOI
            doi = external_ids.get('DOI')
            
            # 论文ID
            paper_id = item.get('paperId', '')
            
            # 学科领域
            fields_of_study = []
            for field in item.get('fieldsOfStudy', []):
                if isinstance(field, str):
                    fields_of_study.append(field)
                elif isinstance(field, dict) and field.get('category'):
                    fields_of_study.append(field['category'])
            
            return Paper(
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                url=url,
                venue=venue,
                citation_count=citation_count,
                doi=doi,
                paper_id=paper_id,
                source='semantic_scholar',
                fields_of_study=fields_of_study
            )
            
        except Exception as e:
            logger.warning(f"解析Semantic Scholar论文失败: {e}")
            return None

class OpenAlexAPI:
    """OpenAlex API客户端"""
    
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, email: str = "research@paper-god.com"):
        self.email = email
        self.session = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': f'Paper-God-Academic-Search/1.0 (mailto:{self.email})'
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_papers(
        self, 
        query: str, 
        limit: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        fields_of_study: Optional[List[str]] = None
    ) -> List[Paper]:
        """搜索论文"""
        
        url = f"{self.BASE_URL}/works"
        
        # 构建搜索参数
        search_query = f'title.search:{query} OR abstract.search:{query}'
        
        params = {
            'search': search_query,
            'per-page': min(limit, 200),  # OpenAlex支持更大的分页
            'mailto': self.email
        }
        
        # 年份过滤
        filters = []
        if year_min or year_max:
            if year_min and year_max:
                filters.append(f'publication_year:{year_min}-{year_max}')
            elif year_min:
                filters.append(f'publication_year:>{year_min-1}')
            elif year_max:
                filters.append(f'publication_year:<{year_max+1}')
        
        # 学科过滤
        if fields_of_study:
            # OpenAlex使用概念ID，这里简化处理
            concept_filters = []
            for field in fields_of_study:
                concept_filters.append(f'concepts.display_name.search:{field}')
            if concept_filters:
                filters.append('(' + ' OR '.join(concept_filters) + ')')
        
        if filters:
            params['filter'] = ','.join(filters)
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    papers = []
                    
                    for item in data.get('results', []):
                        try:
                            paper = self._parse_openalex_paper(item)
                            if paper:
                                papers.append(paper)
                        except Exception as e:
                            logger.warning(f"解析OpenAlex论文数据失败: {e}")
                            continue
                    
                    logger.info(f"OpenAlex返回 {len(papers)} 篇论文")
                    return papers
                    
                elif response.status == 429:  # 速率限制
                    logger.warning("OpenAlex API速率限制，等待重试")
                    await asyncio.sleep(10)
                    raise aiohttp.ClientError("Rate limited")
                else:
                    logger.error(f"OpenAlex API错误: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"OpenAlex搜索失败: {e}")
            return []
    
    def _parse_openalex_paper(self, item: Dict) -> Optional[Paper]:
        """解析OpenAlex返回的论文数据"""
        try:
            # 基本信息
            title = item.get('title', '').strip()
            if not title:
                return None
            
            # 作者信息
            authors = []
            for authorship in item.get('authorships', []):
                author = authorship.get('author', {})
                if author.get('display_name'):
                    authors.append(author['display_name'])
            
            # 年份
            year = item.get('publication_year')
            
            # 摘要 - OpenAlex可能没有完整摘要
            abstract = ''
            if item.get('abstract_inverted_index'):
                # 从倒排索引重建摘要（简化版）
                abstract = "摘要可通过DOI链接查看完整版本"
            
            # URL
            url = item.get('doi', '') or item.get('primary_location', {}).get('landing_page_url', '')
            
            # 期刊/会议
            venue = ''
            primary_location = item.get('primary_location', {})
            if primary_location.get('source'):
                venue = primary_location['source'].get('display_name', '')
            
            # 引用次数
            citation_count = item.get('cited_by_count', 0)
            
            # DOI
            doi = item.get('doi', '').replace('https://doi.org/', '') if item.get('doi') else None
            
            # 论文ID
            paper_id = item.get('id', '').split('/')[-1] if item.get('id') else ''
            
            # 学科领域
            fields_of_study = []
            for concept in item.get('concepts', []):
                if concept.get('display_name') and concept.get('level', 0) <= 2:  # 只取高级概念
                    fields_of_study.append(concept['display_name'])
            
            return Paper(
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                url=url,
                venue=venue,
                citation_count=citation_count,
                doi=doi,
                paper_id=paper_id,
                source='openalex',
                fields_of_study=fields_of_study
            )
            
        except Exception as e:
            logger.warning(f"解析OpenAlex论文失败: {e}")
            return None

class AcademicSearchEngine:
    """统一的学术搜索引擎"""
    
    def __init__(self, semantic_scholar_api_key: Optional[str] = None):
        self.semantic_scholar_api_key = semantic_scholar_api_key
        
    async def search_papers(
        self,
        query: str,
        max_results: int = 100,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        fields_of_study: Optional[List[str]] = None,
        use_both_apis: bool = True
    ) -> List[Paper]:
        """
        统一搜索接口，可选择使用单个或多个API源
        """
        all_papers = []
        seen_titles = set()  # 用于去重
        
        # 分配每个API的搜索数量
        papers_per_api = max_results // 2 if use_both_apis else max_results
        
        # 搜索任务列表
        tasks = []
        
        # Semantic Scholar搜索
        if use_both_apis or not hasattr(self, '_openalex_only'):
            async def search_semantic():
                async with SemanticScholarAPI(self.semantic_scholar_api_key) as ss_api:
                    return await ss_api.search_papers(
                        query=query,
                        limit=papers_per_api,
                        year_min=year_min,
                        year_max=year_max,
                        fields_of_study=fields_of_study
                    )
            tasks.append(search_semantic())
        
        # OpenAlex搜索
        if use_both_apis or hasattr(self, '_openalex_only'):
            async def search_openalex():
                async with OpenAlexAPI() as oa_api:
                    return await oa_api.search_papers(
                        query=query,
                        limit=papers_per_api,
                        year_min=year_min,
                        year_max=year_max,
                        fields_of_study=fields_of_study
                    )
            tasks.append(search_openalex())
        
        # 并发执行搜索
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"API搜索失败: {result}")
                    continue
                    
                for paper in result:
                    # 简单去重：基于标题
                    title_key = paper.title.lower().strip()
                    if title_key not in seen_titles and len(all_papers) < max_results:
                        seen_titles.add(title_key)
                        all_papers.append(paper)
        
        except Exception as e:
            logger.error(f"搜索过程出错: {e}")
        
        # 按引用次数排序
        all_papers.sort(key=lambda p: p.citation_count, reverse=True)
        
        logger.info(f"总共获取到 {len(all_papers)} 篇去重后的论文")
        return all_papers[:max_results]

# 使用示例
async def main():
    """测试用的主函数"""
    engine = AcademicSearchEngine()
    
    # 测试搜索
    papers = await engine.search_papers(
        query="machine learning",
        max_results=20,
        year_min=2020
    )
    
    print(f"找到 {len(papers)} 篇论文:")
    for i, paper in enumerate(papers[:5], 1):
        print(f"{i}. {paper.title}")
        print(f"   作者: {', '.join(paper.authors[:3])}")
        print(f"   年份: {paper.year}, 引用: {paper.citation_count}")
        print(f"   来源: {paper.source}")
        print()

if __name__ == "__main__":
    asyncio.run(main())