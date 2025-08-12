"""
多源数据获取引擎 - Paper God核心搜索组件
实现 Semantic Scholar + arXiv + Google Scholar 多源并行搜索
提供稳定的学术文献检索服务
"""

import asyncio
import aiohttp
import time
import random
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from urllib.parse import quote
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取API密钥和配置
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
PUBMED_ENABLED = PUBMED_API_KEY and PUBMED_API_KEY.lower() != "disabled"

# Semantic Scholar API配置
SEMANTIC_SCHOLAR_ENABLED = os.getenv("SEMANTIC_SCHOLAR_ENABLED", "true").lower() == "true"
# Google Scholar配置（使用scholarly库）
GOOGLE_SCHOLAR_ENABLED = os.getenv("GOOGLE_SCHOLAR_ENABLED", "false").lower() == "true"

CROSSREF_ENABLED = os.getenv("CROSSREF_ENABLED", "true").lower() == "true" 
IEEE_API_KEY = os.getenv("IEEE_API_KEY")
IEEE_ENABLED = IEEE_API_KEY and IEEE_API_KEY.lower() != "disabled"
SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY") 
SPRINGER_ENABLED = SPRINGER_API_KEY and SPRINGER_API_KEY.lower() != "disabled"

# 日志输出API状态
logger.info(f"数据源状态:")
logger.info(f"  - Semantic Scholar: {'启用' if SEMANTIC_SCHOLAR_ENABLED else '禁用'}")
logger.info(f"  - arXiv: 启用")
logger.info(f"  - Google Scholar: {'启用' if GOOGLE_SCHOLAR_ENABLED else '禁用'}")  
logger.info(f"  - PubMed: {'启用' if PUBMED_ENABLED else '禁用'}")
logger.info(f"  - Crossref: {'启用' if CROSSREF_ENABLED else '禁用'}")
logger.info(f"  - IEEE Xplore: {'启用' if IEEE_ENABLED else '禁用'}")
logger.info(f"  - Springer: {'启用' if SPRINGER_ENABLED else '禁用'}")

@dataclass
class Paper:
    """论文数据结构"""
    title: str
    authors: List[str]
    abstract: str
    year: Optional[int]
    journal: str
    url: str
    doi: Optional[str]
    citations: Optional[int]
    source: str  # 数据来源标识
    relevance_score: float = 0.0
    pmid: Optional[str] = None  # PubMed ID
    keywords: Optional[List[str]] = None  # 关键词

class SemanticScholarAPI:
    """Semantic Scholar API客户端 - 优化的限频处理"""
    
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.session = None
        self._last_request_time = 0
        self._min_delay = 2.0  # 增加最小请求间隔到2秒
        self._max_retries = 5  # 增加最大重试次数到5次
        self._base_backoff_delay = 3.0  # 基础退避延时
        
    async def _get_session(self):
        """获取异步HTTP会话，带有合适的请求头"""
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': 'PaperGod/1.0 (Academic Research Tool; +https://github.com/paper-god)',
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate'
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索论文"""
        for attempt in range(self._max_retries):
            try:
                # 确保请求间隔（加入随机抖动避免同步请求）
                current_time = time.time()
                time_since_last = current_time - self._last_request_time
                required_delay = self._min_delay + random.uniform(0.1, 0.5)
                if time_since_last < required_delay:
                    await asyncio.sleep(required_delay - time_since_last)
                
                session = await self._get_session()
                
                # 构建搜索URL
                encoded_query = quote(query)
                url = f"{self.base_url}/paper/search"
                params = {
                    'query': query,
                    'limit': limit,
                    'fields': 'title,authors,abstract,year,journal,url,citationCount,externalIds'
                }
                
                self._last_request_time = time.time()
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_papers(data.get('data', []))
                    elif response.status == 429:
                        # 处理429错误 - 指数退避策略
                        wait_time = self._base_backoff_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(f"Semantic Scholar API限频 (429), 采用指数退避，等待 {wait_time:.1f} 秒后重试 (尝试 {attempt + 1}/{self._max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"Semantic Scholar API错误: {response.status}")
                        if attempt == self._max_retries - 1:
                            return []
                        
            except Exception as e:
                logger.error(f"Semantic Scholar搜索错误: {e}")
                if attempt == self._max_retries - 1:
                    return []
                # 异常时也采用退避策略
                wait_time = self._min_delay * (attempt + 1)
                await asyncio.sleep(wait_time)
        
        return []
    
    def _parse_papers(self, papers_data: List[Dict]) -> List[Paper]:
        """解析API返回的论文数据"""
        papers = []
        for paper_data in papers_data:
            try:
                # 提取作者信息
                authors = []
                if paper_data.get('authors'):
                    authors = [author.get('name', '未知作者') for author in paper_data['authors']]
                
                # 提取DOI
                doi = None
                external_ids = paper_data.get('externalIds', {})
                if external_ids and 'DOI' in external_ids:
                    doi = external_ids['DOI']
                
                paper = Paper(
                    title=paper_data.get('title', ''),
                    authors=authors,
                    abstract=paper_data.get('abstract', ''),
                    year=paper_data.get('year'),
                    journal=paper_data.get('journal', {}).get('name', ''),
                    url=paper_data.get('url', ''),
                    doi=doi,
                    citations=paper_data.get('citationCount', 0),
                    source='semantic_scholar'
                )
                papers.append(paper)
            except Exception as e:
                logger.warning(f"解析Semantic Scholar论文数据错误: {e}")
                continue
                
        return papers
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()

class ArxivAPI:
    """arXiv API客户端"""
    
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        self.session = None
        
    async def _get_session(self):
        """获取异步HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索arXiv预印本"""
        try:
            session = await self._get_session()
            
            # 构建搜索参数
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': limit,
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    xml_content = await response.text()
                    return self._parse_arxiv_xml(xml_content)
                else:
                    logger.warning(f"arXiv API错误: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"arXiv搜索错误: {e}")
            return []
    
    def _parse_arxiv_xml(self, xml_content: str) -> List[Paper]:
        """解析arXiv XML响应"""
        papers = []
        try:
            root = ET.fromstring(xml_content)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', namespace):
                try:
                    title = entry.find('atom:title', namespace)
                    title = title.text.strip() if title is not None else ''
                    
                    summary = entry.find('atom:summary', namespace)
                    abstract = summary.text.strip() if summary is not None else ''
                    
                    # 提取作者
                    authors = []
                    for author in entry.findall('atom:author', namespace):
                        name = author.find('atom:name', namespace)
                        if name is not None:
                            authors.append(name.text.strip())
                    
                    # 提取发布时间
                    published = entry.find('atom:published', namespace)
                    year = None
                    if published is not None:
                        try:
                            year = int(published.text[:4])
                        except:
                            pass
                    
                    # 提取URL
                    url = ''
                    for link in entry.findall('atom:link', namespace):
                        if link.get('type') == 'text/html':
                            url = link.get('href', '')
                            break
                    
                    paper = Paper(
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        year=year,
                        journal='arXiv',
                        url=url,
                        doi=None,
                        citations=0,  # arXiv没有引用数据
                        source='arxiv'
                    )
                    papers.append(paper)
                    
                except Exception as e:
                    logger.warning(f"解析arXiv条目错误: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析arXiv XML错误: {e}")
            
        return papers
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()


class PubMedAPI:
    """PubMed API客户端 - 用于生物医学文献检索"""
    
    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.session = None
        self.api_key = PUBMED_API_KEY
        
    async def _get_session(self):
        """获取异步HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索PubMed文献"""
        try:
            session = await self._get_session()
            
            # 步骤1: 使用esearch获取文献ID列表
            search_params = {
                'db': 'pubmed',
                'term': query,
                'retmax': limit,
                'sort': 'relevance',
                'retmode': 'json'
            }
            if self.api_key:
                search_params['api_key'] = self.api_key
                
            async with session.get(f"{self.base_url}/esearch.fcgi", params=search_params) as response:
                if response.status != 200:
                    logger.error(f"PubMed搜索错误: {response.status}")
                    return []
                    
                search_data = await response.json()
                pmids = search_data['esearchresult']['idlist']
                
                if not pmids:
                    return []
                
            # 步骤2: 使用efetch获取详细信息
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'xml'
            }
            if self.api_key:
                fetch_params['api_key'] = self.api_key
                
            async with session.get(f"{self.base_url}/efetch.fcgi", params=fetch_params) as response:
                if response.status != 200:
                    logger.error(f"PubMed获取详情错误: {response.status}")
                    return []
                    
                xml_content = await response.text()
                return self._parse_pubmed_xml(xml_content)
                
        except Exception as e:
            logger.error(f"PubMed API错误: {e}")
            return []
            
    def _parse_pubmed_xml(self, xml_content: str) -> List[Paper]:
        """解析PubMed XML响应"""
        papers = []
        try:
            root = ET.fromstring(xml_content)
            
            for article in root.findall(".//PubmedArticle"):
                try:
                    # 提取PMID
                    pmid = article.find(".//PMID").text
                    
                    # 提取标题
                    title_element = article.find(".//ArticleTitle")
                    title = title_element.text if title_element is not None else ""
                    
                    # 提取作者
                    authors = []
                    author_list = article.findall(".//Author")
                    for author in author_list:
                        last_name = author.find("LastName")
                        fore_name = author.find("ForeName")
                        if last_name is not None and fore_name is not None:
                            authors.append(f"{fore_name.text} {last_name.text}")
                        elif last_name is not None:
                            authors.append(last_name.text)
                    
                    # 提取摘要
                    abstract_element = article.find(".//Abstract/AbstractText")
                    abstract = abstract_element.text if abstract_element is not None else ""
                    
                    # 提取年份
                    year = None
                    pub_date = article.find(".//PubDate")
                    if pub_date is not None:
                        year_element = pub_date.find("Year")
                        if year_element is not None:
                            year = int(year_element.text)
                    
                    # 提取期刊信息
                    journal_element = article.find(".//Journal/Title")
                    journal = journal_element.text if journal_element is not None else ""
                    
                    # 提取DOI
                    doi = None
                    article_ids = article.findall(".//ArticleId")
                    for article_id in article_ids:
                        if article_id.get("IdType") == "doi":
                            doi = article_id.text
                            break
                    
                    # 构建URL
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    
                    # 提取关键词
                    keywords = []
                    keyword_elements = article.findall(".//Keyword")
                    for keyword in keyword_elements:
                        if keyword.text:
                            keywords.append(keyword.text)
                    
                    paper = Paper(
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        year=year,
                        journal=journal,
                        url=url,
                        doi=doi,
                        citations=None,  # PubMed不直接提供引用数
                        source='pubmed',
                        pmid=pmid,
                        keywords=keywords
                    )
                    papers.append(paper)
                    
                except Exception as e:
                    logger.warning(f"解析PubMed文章错误: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析PubMed XML错误: {e}")
            
        return papers
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()


class GoogleScholarAPI:
    """Google Scholar API客户端 - 使用scholarly库实现稳定的文献元数据爬取"""
    
    def __init__(self):
        self.session = None
        self._min_delay = (1, 3)  # 随机延迟范围（秒）
        self._max_retries = 3
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索Google Scholar文献"""
        try:
            # 导入scholarly库
            try:
                from scholarly import scholarly
            except ImportError:
                logger.error("scholarly库未安装，请运行: pip install scholarly")
                return []
            
            logger.info(f"开始Google Scholar搜索: {query}, 限制: {limit}")
            papers = []
            seen_urls = set()
            retrieved_count = 0
            import time as _time
            overall_budget_s = float(os.getenv("GOOGLE_SCHOLAR_TIME_BUDGET", "6.0"))
            start_ts = _time.time()
            
            # 使用scholarly库进行搜索，增加超时控制
            try:
                search_iterator = scholarly.search_pubs(query)
                
                # 获取论文结果，增加超时保护
                # 限制迭代次数，结合整体时间预算
                max_iters = max(5, min(limit, 10))
                for i in range(max_iters):
                    try:
                        # 为每次搜索设置超时
                        result = await asyncio.wait_for(
                            asyncio.to_thread(next, search_iterator),
                            timeout=5  # 单次抓取最多等待5秒
                        )
                        retrieved_count += 1
                        
                        if not result:
                            continue
                        
                        # 解析论文信息
                        bib = result.get('bib', {})
                        title = bib.get('title', '').strip()
                        
                        if not title or len(title) < 3:
                            continue
                        
                        # 获取URL
                        url = result.get('pub_url', '') or result.get('eprint_url', '')
                        if not url or url in seen_urls:
                            continue
                        
                        seen_urls.add(url)
                        
                        # 解析作者信息
                        authors_list = bib.get('author', [])
                        if isinstance(authors_list, list):
                            authors = [str(author) for author in authors_list]
                        else:
                            authors = [str(authors_list)] if authors_list else []
                        
                        # 解析年份
                        year = bib.get('pub_year')
                        if year:
                            try:
                                year = int(year)
                            except (ValueError, TypeError):
                                year = None
                        
                        # 获取摘要
                        abstract = bib.get('abstract', '')
                        if abstract and len(abstract) > 300:
                            abstract = abstract[:300] + "..."
                        
                        # 获取期刊信息
                        journal = bib.get('venue', '') or bib.get('journal', '')
                        
                        # 获取引用数
                        citations = result.get('num_citations', 0)
                        if citations:
                            try:
                                citations = int(citations)
                            except (ValueError, TypeError):
                                citations = 0
                        
                        # 创建Paper对象
                        paper = Paper(
                            title=title,
                            authors=authors,
                            abstract=abstract,
                            year=year,
                            journal=journal,
                            url=url,
                            doi=None,  # scholarly通常不提供DOI
                            citations=citations,
                            source="google_scholar",
                            relevance_score=1.0 - (len(papers) * 0.01)  # 简单的相关性评分
                        )
                        
                        papers.append(paper)
                        
                        logger.info(f"添加论文: {title[:50]}... (引用: {citations})")
                        
                        if len(papers) >= limit:
                            break
                        
                        # 随机延迟避免被限制
                        await asyncio.sleep(random.uniform(*self._min_delay))

                        # 触发整体时间预算检查
                        if (_time.time() - start_ts) >= overall_budget_s:
                            logger.info("Google Scholar达到时间预算上限，停止进一步抓取")
                            break
                        
                    except (StopIteration, asyncio.TimeoutError):
                        logger.info("Google Scholar搜索已无更多结果或超时")
                        break
                    except Exception as e:
                        logger.warning(f"处理单个结果时出错: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"初始化Google Scholar搜索失败: {e}")
                return []
            
            logger.info(f"Google Scholar搜索完成，获得 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"Google Scholar搜索错误: {e}")
            return []
    
    async def close(self):
        """关闭会话（scholarly库无需手动关闭）"""
        pass

# 学术数据源API集合
class CrossrefAPI:
    """Crossref API客户端 - 开放获取学术文献数据源"""
    
    def __init__(self):
        self.base_url = "https://api.crossref.org/works"
        self.session = None
        self._last_request_time = 0
        self._min_delay = float(os.getenv("CROSSREF_REQUEST_DELAY", "1.0"))
        
    async def _get_session(self):
        """获取异步HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索论文"""
        if not CROSSREF_ENABLED:
            logger.info("Crossref API 已禁用")
            return []
            
        try:
            # 确保请求间隔
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_delay:
                await asyncio.sleep(self._min_delay - time_since_last)
            
            session = await self._get_session()
            
            # 构建请求参数
            params = {
                'query': query,
                'rows': limit,
                'select': 'DOI,title,author,published,abstract,URL,is-referenced-by-count,publisher'
            }
            
            self._last_request_time = time.time()
            
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('message', {}).get('items', [])
                    return self._parse_papers(items)
                else:
                    logger.error(f"Crossref API请求失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Crossref搜索出错: {str(e)}")
            return []
            
    def _parse_papers(self, items: List[Dict]) -> List[Paper]:
        """解析Crossref响应数据"""
        papers = []
        for item in items:
            try:
                # 提取标题
                title_list = item.get('title', [])
                title = title_list[0] if title_list else "未知标题"
                
                # 提取作者
                authors = []
                for author in item.get('author', []):
                    if 'given' in author and 'family' in author:
                        authors.append(f"{author['given']} {author['family']}")
                    elif 'family' in author:
                        authors.append(author['family'])
                
                # 提取年份
                year = None
                published = item.get('published-print') or item.get('published-online')
                if published and 'date-parts' in published:
                    date_parts = published['date-parts'][0]
                    if date_parts:
                        year = date_parts[0]
                
                # 提取其他信息
                abstract = item.get('abstract', '')
                doi = item.get('DOI', '')
                url = item.get('URL', f"https://doi.org/{doi}" if doi else '')
                citations = item.get('is-referenced-by-count', 0)
                journal = item.get('publisher', '')
                
                paper = Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    journal=journal,
                    url=url,
                    doi=doi,
                    citations=citations,
                    source="crossref",
                    relevance_score=1.0
                )
                papers.append(paper)
                
            except Exception as e:
                logger.warning(f"解析Crossref论文数据失败: {str(e)}")
                continue
                
        return papers
        
    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()

class MultiSourceEngine:
    """多源数据获取引擎 - 核心搜索组件"""
    
    def __init__(self):
        # 初始化核心数据源
        self.arxiv = ArxivAPI()
        self.google_scholar = GoogleScholarAPI() if GOOGLE_SCHOLAR_ENABLED else None
        
        # 可选数据源
        self.semantic_scholar = SemanticScholarAPI() if SEMANTIC_SCHOLAR_ENABLED else None
        self.crossref = CrossrefAPI() if CROSSREF_ENABLED else None
        self.pubmed = PubMedAPI() if PUBMED_ENABLED else None
        
        logger.info(f"多源搜索引擎初始化完成，启用数据源数量: {self._count_enabled_sources()}")
        
    def _count_enabled_sources(self) -> int:
        """计算启用的数据源数量"""
        count = 1  # arXiv 总是启用
        if self.google_scholar:
            count += 1
        if self.semantic_scholar:
            count += 1
        if self.crossref:
            count += 1
        if self.pubmed:
            count += 1  
        return count
        
    async def search_parallel(self, query: str, max_results: int = 50) -> List[Paper]:
        """并行搜索多个数据源（兼容旧接口）"""
        return await self.search_parallel_with_filters(query, max_results)
    
    async def search_parallel_with_filters(
        self, 
        query: str, 
        max_results: int = 50, 
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        sources: Optional[List[str]] = None
    ) -> List[Paper]:
        """并行搜索多个数据源（带筛选参数）"""
        logger.info(f"开始多源并行搜索: {query}")
        if year_from or year_to:
            logger.info(f"年份筛选: {year_from} - {year_to}")
        
        # 计算每个源的搜索数量
        active_sources = self._count_enabled_sources()
        per_source_limit = max(10, max_results // active_sources)
        
        try:
            # 并行调用核心搜索源（arXiv和Google Scholar享受相同权重）
            tasks = []
            per_task_timeout = float(os.getenv("SEARCH_TASK_TIMEOUT", "8.0"))
            
            # 核心数据源 - arXiv和Google Scholar权重相同
            if self.arxiv:
                tasks.append(asyncio.wait_for(self.arxiv.search(query, per_source_limit), timeout=per_task_timeout))
            if self.google_scholar:
                tasks.append(asyncio.wait_for(self.google_scholar.search(query, per_source_limit), timeout=per_task_timeout))
            
            # 添加可选数据源
            if self.semantic_scholar:
                tasks.append(asyncio.wait_for(self.semantic_scholar.search(query, per_source_limit), timeout=per_task_timeout))
            if self.crossref:
                tasks.append(asyncio.wait_for(self.crossref.search(query, per_source_limit), timeout=per_task_timeout))
            if self.pubmed:
                tasks.append(asyncio.wait_for(self.pubmed.search(query, per_source_limit), timeout=per_task_timeout))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 合并结果
            all_papers = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"搜索源 {i} 出错: {result}")
                    continue
                elif isinstance(result, list):
                    all_papers.extend(result)
            
            # 去重和排序
            deduplicated_papers = self._deduplicate_papers(all_papers)
            
            # 应用年份筛选
            if year_from is not None or year_to is not None:
                filtered_papers = self._filter_papers_by_year(deduplicated_papers, year_from, year_to)
                logger.info(f"年份筛选后剩余 {len(filtered_papers)} 篇论文")
            else:
                filtered_papers = deduplicated_papers
            
            ranked_papers = self._rank_papers(filtered_papers, query)
            
            logger.info(f"多源搜索完成，获得 {len(ranked_papers)} 篇论文")
            return ranked_papers[:max_results]
            
        except Exception as e:
            logger.error(f"多源搜索错误: {e}")
            return []
    
    def _deduplicate_papers(self, papers: List[Paper]) -> List[Paper]:
        """去重论文列表"""
        seen_titles = set()
        unique_papers = []
        
        for paper in papers:
            # 简单的标题去重
            title_key = paper.title.lower().strip()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_papers.append(paper)
        
        return unique_papers
    
    def _filter_papers_by_year(self, papers: List[Paper], year_from: Optional[int], year_to: Optional[int]) -> List[Paper]:
        """按年份筛选论文"""
        if year_from is None and year_to is None:
            return papers
        
        filtered_papers = []
        for paper in papers:
            if paper.year is None:
                # 如果论文没有年份信息，根据筛选策略决定是否保留
                # 这里选择保留，避免丢失有价值的论文
                filtered_papers.append(paper)
                continue
            
            # 检查年份范围
            include_paper = True
            if year_from is not None and paper.year < year_from:
                include_paper = False
            if year_to is not None and paper.year > year_to:
                include_paper = False
            
            if include_paper:
                filtered_papers.append(paper)
        
        return filtered_papers
    
    def _rank_papers(self, papers: List[Paper], query: str) -> List[Paper]:
        """论文相关性排序"""
        query_terms = set(query.lower().split())
        
        for paper in papers:
            score = 0.0
            
            # 标题匹配度
            title_terms = set(paper.title.lower().split())
            title_overlap = len(query_terms.intersection(title_terms))
            score += title_overlap * 2.0
            
            # 摘要匹配度
            if paper.abstract:
                abstract_terms = set(paper.abstract.lower().split())
                abstract_overlap = len(query_terms.intersection(abstract_terms))
                score += abstract_overlap * 0.5
            
            # 引用数权重
            if paper.citations:
                score += min(paper.citations / 100.0, 2.0)
            
            # 年份权重（近期论文优先）
            if paper.year:
                current_year = 2024
                year_bonus = max(0, (paper.year - (current_year - 10)) / 10.0)
                score += year_bonus
            
            # 数据源权重
            source_weights = {
                'semantic_scholar': 1.3,
                'arxiv': 1.1,
                'pubmed': 1.2,
                'google_scholar': 1.2,
                'crossref': 1.0
            }
            score *= source_weights.get(paper.source, 1.0)
            
            paper.relevance_score = score
        
        # 按相关性得分排序
        return sorted(papers, key=lambda p: p.relevance_score, reverse=True)
    
    async def close(self):
        """关闭所有连接"""
        coros = [self.arxiv.close()]
        if self.google_scholar:
            coros.append(self.google_scholar.close())
        if self.semantic_scholar:
            coros.append(self.semantic_scholar.close())
        if self.crossref:
            coros.append(self.crossref.close())
        if self.pubmed:
            coros.append(self.pubmed.close())
        await asyncio.gather(*coros)
        

# 使用示例
async def main():
    """测试多源搜索引擎（MCP增强版）"""
    # 测试MCP增强版本
    engine_mcp = MultiSourceEngine(enable_mcp=True)
    
    try:
        print("=== MCP增强搜索测试 ===")
        # 使用MCP增强搜索
        results = await engine_mcp.search_with_mcp_fallback("machine learning", max_results=10)
        
        print(f"MCP增强搜索找到 {len(results)} 篇论文:")
        for i, paper in enumerate(results[:3], 1):
            print(f"\n{i}. {paper.title}")
            print(f"   作者: {', '.join(paper.authors[:3])}")
            print(f"   来源: {paper.source}")
            print(f"   年份: {paper.year}")
            print(f"   相关性得分: {paper.relevance_score:.2f}")
            
        print("\n=== 传统搜索对比测试 ===")
        # 测试传统版本对比
        engine_traditional = MultiSourceEngine(enable_mcp=False)
        results_traditional = await engine_traditional.search_parallel("machine learning", max_results=10)
        
        print(f"传统搜索找到 {len(results_traditional)} 篇论文")
        
        await engine_traditional.close()
            
    finally:
        await engine_mcp.close()

if __name__ == "__main__":
    asyncio.run(main())