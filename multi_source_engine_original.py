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
GOOGLE_SCHOLAR_ENABLED = os.getenv("GOOGLE_SCHOLAR_ENABLED", "true").lower() == "true"

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
    """Semantic Scholar API客户端 - 高度优化的限频处理"""
    
    # 类级别的全局限频控制
    _global_last_request = 0
    _global_consecutive_429s = 0
    _circuit_breaker_until = 0  # 熔断器：暂时禁用API直到此时间
    
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.session = None
        self._last_request_time = 0
        self._min_delay = 6.0  # 增加到6秒最小间隔
        self._max_retries = 2  # 减少重试次数到2次
        self._base_backoff_delay = 8.0  # 增加基础退避延时到8秒
        self._consecutive_429s = 0  # 连续429错误计数
        self._total_requests = 0  # 总请求计数
        self._successful_requests = 0  # 成功请求计数
        
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
        """搜索论文 - 带熔断器和全局限频"""
        current_time = time.time()
        
        # 熔断器检查：如果API被临时禁用，直接返回
        if current_time < self._circuit_breaker_until:
            remaining_time = self._circuit_breaker_until - current_time
            logger.warning(f"Semantic Scholar API熔断中，剩余 {remaining_time:.1f} 秒")
            return []
        
        self._total_requests += 1
        logger.info(f"开始Semantic Scholar搜索: {query}, 限制: {limit} (总请求数: {self._total_requests})")
        
        for attempt in range(self._max_retries):
            try:
                # 全局限频控制（防止并发请求）
                current_time = time.time()
                global_time_since_last = current_time - SemanticScholarAPI._global_last_request
                instance_time_since_last = current_time - self._last_request_time
                
                # 使用更严格的延迟（全局和实例级别的最大值）
                required_delay = max(
                    self._min_delay + random.uniform(0.5, 1.5),  # 增加随机抖动
                    8.0 if SemanticScholarAPI._global_consecutive_429s > 0 else self._min_delay  # 全局429时延迟更长
                )
                
                actual_delay = max(
                    required_delay - global_time_since_last,
                    required_delay - instance_time_since_last
                )
                
                if actual_delay > 0:
                    logger.info(f"Semantic Scholar限频等待: {actual_delay:.1f} 秒")
                    await asyncio.sleep(actual_delay)
                
                session = await self._get_session()
                
                # 构建搜索URL
                url = f"{self.base_url}/paper/search"
                params = {
                    'query': query,
                    'limit': limit,
                    'fields': 'title,authors,abstract,year,journal,url,citationCount,externalIds'
                }
                
                # 更新全局和实例时间戳
                SemanticScholarAPI._global_last_request = time.time()
                self._last_request_time = time.time()
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 成功时重置所有429计数器
                        self._consecutive_429s = 0
                        SemanticScholarAPI._global_consecutive_429s = 0
                        self._successful_requests += 1
                        papers = self._parse_papers(data.get('data', []))
                        logger.info(f"Semantic Scholar搜索成功，获得 {len(papers)} 篇论文")
                        return papers
                        
                    elif response.status == 429:
                        self._consecutive_429s += 1
                        SemanticScholarAPI._global_consecutive_429s += 1
                        
                        # 更激进的限制：第一次429就考虑提早放弃
                        if self._consecutive_429s >= 1 or SemanticScholarAPI._global_consecutive_429s >= 2:
                            # 启动熔断器：暂时禁用API 30秒
                            SemanticScholarAPI._circuit_breaker_until = time.time() + 30.0
                            logger.warning(f"Semantic Scholar API连续限频，启动30秒熔断器")
                            return []
                        
                        # 更长的退避时间
                        wait_time = min(self._base_backoff_delay * (2 ** attempt), 20.0) + random.uniform(1.0, 3.0)
                        logger.warning(f"Semantic Scholar API限频 (429), 等待 {wait_time:.1f} 秒后重试 (尝试 {attempt + 1}/{self._max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    else:
                        logger.warning(f"Semantic Scholar API错误: {response.status}")
                        if attempt == self._max_retries - 1:
                            return []
                        
            except Exception as e:
                logger.error(f"Semantic Scholar搜索错误: {e}")
                if attempt == self._max_retries - 1:
                    logger.warning(f"Semantic Scholar搜索最终失败，成功率: {self._successful_requests}/{self._total_requests}")
                    return []
                # 异常时采用更长的退避策略
                wait_time = self._min_delay * (attempt + 2)
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
                    authors = [author.get('name', '未知作者') for author in paper_data['authors'] if author.get('name')]
                if not authors:
                    authors = ['未知作者']
                
                # 提取DOI
                doi = None
                external_ids = paper_data.get('externalIds', {})
                if external_ids and 'DOI' in external_ids:
                    doi = external_ids['DOI']
                
                # 提取期刊信息，确保不为空
                journal_info = paper_data.get('journal', {})
                journal = journal_info.get('name', '') if journal_info else ''
                if not journal:
                    journal = 'Semantic Scholar'
                
                # 确保标题不为空
                title = paper_data.get('title', '').strip()
                if not title:
                    title = '无标题'
                
                # 确保摘要
                abstract = paper_data.get('abstract', '').strip()
                if not abstract:
                    abstract = '暂无摘要'
                
                # 确保URL
                url = paper_data.get('url', '').strip()
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                
                paper = Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=paper_data.get('year'),
                    journal=journal,
                    url=url,
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
        self._min_delay = (0.5, 1.5)  # 减少延迟范围以提高效率
        self._max_retries = 3
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索Google Scholar文献 - 使用简化的scholarly方法"""
        try:
            # 导入scholarly库
            try:
                from scholarly import scholarly
            except ImportError:
                logger.error("scholarly库未安装，请运行: pip install scholarly")
                return []
            
            logger.info(f"开始Google Scholar搜索: {query}, 限制: {limit}")
            papers = []
            
            # 🔥 简化方法：直接使用scholarly，不用复杂的异步包装
            try:
                search_generator = scholarly.search_pubs(query)
                count = 0
                
                # 简单遍历，避免复杂的异步处理
                for pub in search_generator:
                    try:
                        if count >= limit:
                            break
                            
                        # 解析论文信息
                        bib = pub.get('bib', {})
                        title = bib.get('title', '').strip()
                        
                        if not title or len(title) < 5:
                            continue
                        
                        # 获取作者
                        authors_raw = bib.get('author', [])
                        if isinstance(authors_raw, list):
                            authors = [str(author).strip() for author in authors_raw if str(author).strip()]
                        else:
                            authors = [str(authors_raw).strip()] if authors_raw else []
                        
                        if not authors:
                            authors = ['未知作者']
                        
                        # 获取年份
                        year = bib.get('pub_year')
                        if year:
                            try:
                                year = int(year)
                            except:
                                year = None
                        
                        # 获取摘要
                        abstract = bib.get('abstract', '').strip()
                        if not abstract:
                            abstract = '暂无摘要'
                        elif len(abstract) > 500:
                            abstract = abstract[:500] + "..."
                        
                        # 获取期刊
                        journal = bib.get('venue', '') or bib.get('journal', '') or 'Google Scholar'
                        
                        # 获取URL
                        url = pub.get('pub_url', '') or pub.get('eprint_url', '') or ''
                        
                        # 获取引用数
                        citations = pub.get('num_citations', 0)
                        try:
                            citations = int(citations) if citations else 0
                        except:
                            citations = 0
                        
                        # 创建Paper对象
                        paper = Paper(
                            title=title,
                            authors=authors,
                            abstract=abstract,
                            year=year,
                            journal=journal,
                            url=url,
                            doi=None,
                            citations=citations,
                            source="google_scholar",
                            relevance_score=1.0 - (count * 0.01)
                        )
                        
                        papers.append(paper)
                        count += 1
                        
                        logger.info(f"Google Scholar找到论文: {title[:50]}... (引用: {citations})")
                        
                        # 简单延迟避免被限制
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.warning(f"解析Google Scholar论文出错: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Google Scholar搜索失败: {e}")
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
                # 提取标题，确保不为空
                title_list = item.get('title', [])
                title = (title_list[0] if title_list else "").strip()
                if not title:
                    title = "无标题"
                
                # 提取作者，确保不为空
                authors = []
                for author in item.get('author', []):
                    if 'given' in author and 'family' in author:
                        full_name = f"{author['given']} {author['family']}".strip()
                        if full_name:
                            authors.append(full_name)
                    elif 'family' in author:
                        family_name = author['family'].strip()
                        if family_name:
                            authors.append(family_name)
                
                if not authors:
                    authors = ['未知作者']
                
                # 提取年份
                year = None
                published = item.get('published-print') or item.get('published-online')
                if published and 'date-parts' in published:
                    date_parts = published['date-parts'][0]
                    if date_parts:
                        try:
                            year = int(date_parts[0])
                        except (ValueError, TypeError, IndexError):
                            year = None
                
                # 提取其他信息，确保不为空
                abstract = item.get('abstract', '').strip()
                if not abstract:
                    abstract = '暂无摘要'
                
                doi = item.get('DOI', '').strip()
                url = item.get('URL', '').strip()
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                
                citations = item.get('is-referenced-by-count', 0)
                if not isinstance(citations, int):
                    try:
                        citations = int(citations)
                    except (ValueError, TypeError):
                        citations = 0
                
                journal = item.get('publisher', '').strip()
                if not journal:
                    journal = 'Crossref'
                
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
    """多源数据获取引擎 - 智能优化的搜索组件"""
    
    def __init__(self):
        # 初始化核心数据源
        self.arxiv = ArxivAPI()
        # 启用Google Scholar（使用scholarly库）
        self.google_scholar = GoogleScholarAPI() if GOOGLE_SCHOLAR_ENABLED else None
        
        # 可选数据源
        self.semantic_scholar = SemanticScholarAPI() if SEMANTIC_SCHOLAR_ENABLED else None
        self.crossref = CrossrefAPI() if CROSSREF_ENABLED else None
        self.pubmed = PubMedAPI() if PUBMED_ENABLED else None
        
        # 数据源性能跟踪
        self.source_performance = {
            'arxiv': {'attempts': 0, 'successes': 0, 'avg_results': 0, 'avg_time': 0, 'last_success': 0},
            'google_scholar': {'attempts': 0, 'successes': 0, 'avg_results': 0, 'avg_time': 0, 'last_success': 0},
            'semantic_scholar': {'attempts': 0, 'successes': 0, 'avg_results': 0, 'avg_time': 0, 'last_success': 0},
            'crossref': {'attempts': 0, 'successes': 0, 'avg_results': 0, 'avg_time': 0, 'last_success': 0},
            'pubmed': {'attempts': 0, 'successes': 0, 'avg_results': 0, 'avg_time': 0, 'last_success': 0}
        }
        
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
    
    def _update_source_performance(self, source_name: str, success: bool, result_count: int, response_time: float):
        """更新数据源性能统计"""
        if source_name in self.source_performance:
            stats = self.source_performance[source_name]
            stats['attempts'] += 1
            
            if success:
                stats['successes'] += 1
                stats['last_success'] = time.time()
                
                # 更新平均结果数（移动平均）
                if stats['avg_results'] == 0:
                    stats['avg_results'] = result_count
                else:
                    stats['avg_results'] = (stats['avg_results'] * 0.7) + (result_count * 0.3)
                
                # 更新平均响应时间（移动平均）
                if stats['avg_time'] == 0:
                    stats['avg_time'] = response_time
                else:
                    stats['avg_time'] = (stats['avg_time'] * 0.7) + (response_time * 0.3)
    
    def _calculate_source_priority(self, source_name: str) -> float:
        """计算数据源优先级得分（0-1，越高越好）"""
        if source_name not in self.source_performance:
            return 0.5  # 默认中等优先级
        
        stats = self.source_performance[source_name]
        if stats['attempts'] == 0:
            return 0.5  # 未使用过，中等优先级
        
        # 计算成功率
        success_rate = stats['successes'] / stats['attempts']
        
        # 计算结果质量（平均结果数，标准化到0-1）
        result_quality = min(stats['avg_results'] / 10.0, 1.0)  # 10篇为满分
        
        # 计算响应速度（响应时间越短越好，标准化到0-1）
        if stats['avg_time'] > 0:
            speed_score = max(0, 1.0 - (stats['avg_time'] / 30.0))  # 30秒为底线
        else:
            speed_score = 0.5
        
        # 计算最近成功度（最近成功的源优先）
        current_time = time.time()
        if stats['last_success'] > 0:
            time_since_success = current_time - stats['last_success']
            recency_score = max(0, 1.0 - (time_since_success / 3600.0))  # 1小时内为满分
        else:
            recency_score = 0
        
        # 综合计算优先级（权重分配）
        priority = (
            success_rate * 0.4 +          # 成功率权重40%
            result_quality * 0.3 +        # 结果质量权重30%
            speed_score * 0.2 +           # 响应速度权重20%
            recency_score * 0.1           # 最近成功权重10%
        )
        
        return min(priority, 1.0)
    
    def _get_prioritized_sources(self) -> List[tuple]:
        """获取按优先级排序的数据源列表"""
        sources = []
        
        if self.crossref:
            priority = self._calculate_source_priority('crossref')
            sources.append(('crossref', self.crossref, priority))
        
        if self.semantic_scholar:
            priority = self._calculate_source_priority('semantic_scholar')
            sources.append(('semantic_scholar', self.semantic_scholar, priority))
        
        if self.google_scholar:
            priority = self._calculate_source_priority('google_scholar')
            sources.append(('google_scholar', self.google_scholar, priority))
        
        if self.arxiv:
            priority = self._calculate_source_priority('arxiv')
            sources.append(('arxiv', self.arxiv, priority))
        
        if self.pubmed:
            priority = self._calculate_source_priority('pubmed')
            sources.append(('pubmed', self.pubmed, priority))
        
        # 按优先级排序（高到低）
        sources.sort(key=lambda x: x[2], reverse=True)
        
        logger.info(f"数据源优先级排序: {[(name, f'{priority:.2f}') for name, _, priority in sources]}")
        return sources
    
    async def _search_with_tracking(self, source_name: str, source_api, query: str, limit: int, start_time: float, timeout: float) -> List[Paper]:
        """带性能跟踪的搜索方法"""
        try:
            result = await asyncio.wait_for(source_api.search(query, limit), timeout=timeout)
            end_time = time.time()
            response_time = end_time - start_time
            
            # 更新性能统计（成功）
            self._update_source_performance(source_name, True, len(result), response_time)
            
            return result
            
        except asyncio.TimeoutError:
            end_time = time.time()
            response_time = end_time - start_time
            logger.warning(f"搜索源 {source_name} 超时 ({response_time:.1f}s)")
            
            # 更新性能统计（超时失败）
            self._update_source_performance(source_name, False, 0, response_time)
            return []
            
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            logger.error(f"搜索源 {source_name} 异常: {e}")
            
            # 更新性能统计（异常失败）
            self._update_source_performance(source_name, False, 0, response_time)
            return []
        
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
        
        # 计算每个源的搜索数量 - 为大量请求调整分配策略
        active_sources = self._count_enabled_sources()
        if max_results > 20:
            # 大量请求时，给主要源(Google Scholar)更多配额
            per_source_limit = max(15, int(max_results * 0.6 // max(1, active_sources - 1)))  # 主要源获得60%
            google_scholar_limit = max(20, int(max_results * 0.8))  # Google Scholar获得80%
            logger.info(f"大量请求模式：Google Scholar限制={google_scholar_limit}, 其他源限制={per_source_limit}")
        else:
            per_source_limit = max(10, max_results // active_sources)
            google_scholar_limit = per_source_limit
        
        try:
            # 智能源选择：基于优先级进行搜索
            prioritized_sources = self._get_prioritized_sources()
            tasks = []
            source_names = []
            per_task_timeout = float(os.getenv("SEARCH_TASK_TIMEOUT", "30.0"))  # 减少到30秒超时
            
            # 优化策略：优先使用高性能源，如果结果不足再并行所有源
            high_priority_sources = [s for s in prioritized_sources if s[2] > 0.6]
            
            if high_priority_sources:
                logger.info(f"优先使用高性能数据源: {[s[0] for s in high_priority_sources]}")
                
                # 先尝试高优先级源
                for source_name, source_api, priority in high_priority_sources:
                    source_names.append(source_name)
                    search_limit = per_source_limit
                    
                    # Google Scholar仍然给予特殊待遇
                    if source_name == 'google_scholar' and max_results > 20:
                        search_limit = google_scholar_limit
                    
                    start_time = time.time()
                    task = asyncio.create_task(self._search_with_tracking(
                        source_name, source_api, query, search_limit, start_time, per_task_timeout
                    ))
                    tasks.append(task)
            else:
                logger.info("所有数据源优先级较低，并行搜索所有可用源")
                
                # 如果没有高优先级源，使用所有可用源
                for source_name, source_api, priority in prioritized_sources:
                    source_names.append(source_name)
                    search_limit = per_source_limit
                    
                    if source_name == 'google_scholar' and max_results > 20:
                        search_limit = google_scholar_limit
                    
                    start_time = time.time()
                    task = asyncio.create_task(self._search_with_tracking(
                        source_name, source_api, query, search_limit, start_time, per_task_timeout
                    ))
                    tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 合并结果，记录各源的贡献
            all_papers = []
            source_stats = {}
            
            for i, result in enumerate(results):
                source_name = source_names[i] if i < len(source_names) else f"source_{i}"
                
                if isinstance(result, Exception):
                    logger.error(f"搜索源 {source_name} 出错: {type(result).__name__}: {result}")
                    # 更新性能统计（失败）
                    self._update_source_performance(source_name, False, 0, 0)
                    continue
                elif isinstance(result, list):
                    all_papers.extend(result)
                    # 记录各源获得的论文数
                    actual_source_name = result[0].source if result else source_name
                    source_stats[actual_source_name] = len(result)
                    logger.info(f"✅ {source_name} 成功返回 {len(result)} 篇论文")
                else:
                    logger.warning(f"⚠️ {source_name} 返回了意外的结果类型: {type(result)}")
            
            # 输出各源统计信息
            for source, count in source_stats.items():
                logger.info(f"数据源 {source} 贡献了 {count} 篇论文")
            
            # 去重和排序
            deduplicated_papers = self._deduplicate_papers(all_papers)
            
            # 应用年份筛选
            if year_from is not None or year_to is not None:
                filtered_papers = self._filter_papers_by_year(deduplicated_papers, year_from, year_to)
                
                # 如果筛选后结果太少，考虑适当放宽搜索
                if len(filtered_papers) < max_results // 2 and len(deduplicated_papers) > len(filtered_papers):
                    logger.warning(f"年份筛选后仅剩 {len(filtered_papers)} 篇论文，低于期望数量的一半")
                    # 可以在这里添加扩展搜索逻辑，但暂时保持严格筛选
            else:
                filtered_papers = deduplicated_papers
            
            # 排序并限制数量
            ranked_papers = self._rank_papers(filtered_papers, query)
            
            # 最终结果
            final_results = ranked_papers[:max_results]
            
            # 详细统计信息
            logger.info(f"多源搜索统计: 原始 {len(all_papers)} 篇 → 去重后 {len(deduplicated_papers)} 篇 → 筛选后 {len(filtered_papers)} 篇 → 最终 {len(final_results)} 篇")
            
            # 如果最终结果明显少于预期，记录警告
            if len(final_results) < max_results * 0.5 and max_results > 5:
                logger.warning(f"最终结果数量 ({len(final_results)}) 明显少于请求数量 ({max_results})，可能需要调整搜索参数")
            
            return final_results
            
        except Exception as e:
            logger.error(f"多源搜索错误: {e}")
            return []
    
    def _deduplicate_papers(self, papers: List[Paper]) -> List[Paper]:
        """智能去重论文列表 - 优先保留高质量论文，智能识别标题相似性"""
        seen_titles = set()
        seen_dois = set()
        unique_papers = []
        duplicate_count = 0
        
        # 按照质量排序：引用数高的优先，然后是有DOI的，最后是来源权重
        papers_sorted = sorted(papers, key=lambda p: (
            -(p.citations or 0),  # 引用数越多越好
            p.doi is not None,   # 有DOI的优先
            p.source == 'google_scholar'  # Google Scholar优先
        ), reverse=True)
        
        for paper in papers_sorted:
            # DOI去重优先级最高
            if paper.doi and paper.doi.strip() and paper.doi not in seen_dois:
                seen_dois.add(paper.doi)
                unique_papers.append(paper)
                continue
            elif paper.doi and paper.doi.strip() and paper.doi in seen_dois:
                duplicate_count += 1
                continue
                
            # 智能标题去重
            if self._is_duplicate_title(paper.title, seen_titles):
                duplicate_count += 1
                continue
            else:
                # 标准化标题作为键值
                normalized_title = self._normalize_title(paper.title)
                if normalized_title:
                    seen_titles.add(normalized_title)
                    unique_papers.append(paper)
                else:
                    # 标题为空或无效，仍然保留但用特殊标记
                    unique_papers.append(paper)
        
        logger.info(f"智能去重完成：保留 {len(unique_papers)} 篇，去除重复 {duplicate_count} 篇")
        return unique_papers
    
    def _normalize_title(self, title: str) -> str:
        """标准化论文标题，用于去重比较"""
        if not title:
            return ""
        
        import re
        
        # 转换为小写
        normalized = title.lower().strip()
        
        # 移除多余的空白字符
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 移除常见的标点符号差异
        normalized = re.sub(r'[:\-–—\.;,!?()[\]{}""''`]', ' ', normalized)
        
        # 移除多余空格并返回
        return re.sub(r'\s+', ' ', normalized).strip()
    
    def _is_duplicate_title(self, new_title: str, seen_titles: set) -> bool:
        """检查新标题是否与已见过的标题重复（考虑相似性）"""
        if not new_title or not new_title.strip():
            return False
            
        normalized_new = self._normalize_title(new_title)
        if not normalized_new:
            return False
            
        # 精确匹配
        if normalized_new in seen_titles:
            return True
            
        # 相似度匹配（用于处理轻微差异）
        new_words = set(normalized_new.split())
        if len(new_words) < 3:  # 标题太短，不进行相似度匹配
            return False
            
        for seen_title in seen_titles:
            seen_words = set(seen_title.split())
            if len(seen_words) < 3:
                continue
                
            # 计算词汇重叠度
            intersection = new_words.intersection(seen_words)
            union = new_words.union(seen_words)
            
            if len(union) == 0:
                continue
                
            jaccard_similarity = len(intersection) / len(union)
            
            # 如果相似度超过85%，认为是重复
            if jaccard_similarity > 0.85:
                return True
                
        return False
    
    def _filter_papers_by_year(self, papers: List[Paper], year_from: Optional[int], year_to: Optional[int]) -> List[Paper]:
        """按年份筛选论文 - 严格按照用户参数过滤"""
        if year_from is None and year_to is None:
            return papers
        
        filtered_papers = []
        excluded_count = 0
        no_year_count = 0
        
        for paper in papers:
            if paper.year is None:
                # 严格模式：如果用户指定了年份范围，则排除没有年份信息的论文
                if year_from is not None or year_to is not None:
                    no_year_count += 1
                    excluded_count += 1
                    continue
                else:
                    # 用户没有指定年份范围，保留无年份论文
                    filtered_papers.append(paper)
                    continue
            
            # 检查年份范围
            include_paper = True
            if year_from is not None and paper.year < year_from:
                include_paper = False
                excluded_count += 1
            if year_to is not None and paper.year > year_to:
                include_paper = False
                excluded_count += 1
            
            if include_paper:
                filtered_papers.append(paper)
        
        # 详细日志记录
        if year_from is not None or year_to is not None:
            year_range = f"{year_from or '∞'} - {year_to or '∞'}"
            logger.info(f"年份筛选 ({year_range}): 保留 {len(filtered_papers)} 篇, 排除 {excluded_count} 篇")
            if no_year_count > 0:
                logger.info(f"排除无年份信息论文: {no_year_count} 篇")
        
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