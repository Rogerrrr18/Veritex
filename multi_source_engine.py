"""
多源数据获取引擎 - Paper God核心搜索组件
实现 Semantic Scholar + arXiv + Paperscraper 多源并行搜索
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

# 获取API密钥
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
PUBMED_ENABLED = PUBMED_API_KEY and PUBMED_API_KEY.lower() != "disabled"

if not PUBMED_ENABLED:
    logger.info("PubMed API 已禁用或未配置API密钥")

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
    """Semantic Scholar API客户端"""
    
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.session = None
        
    async def _get_session(self):
        """获取异步HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索论文"""
        try:
            session = await self._get_session()
            
            # 构建搜索URL
            encoded_query = quote(query)
            url = f"{self.base_url}/paper/search"
            params = {
                'query': query,
                'limit': limit,
                'fields': 'title,authors,abstract,year,journal,url,citationCount,externalIds'
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_papers(data.get('data', []))
                else:
                    logger.warning(f"Semantic Scholar API错误: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Semantic Scholar搜索错误: {e}")
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

class PaperscraperClient:
    """Paperscraper客户端 - 替换scholarly的核心组件"""
    
    def __init__(self):
        self.session = None
        
    async def _get_session(self):
        """获取异步HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """使用paperscraper搜索（模拟实现，实际需要安装paperscraper）"""
        try:
            # 注意：这里是简化的模拟实现
            # 实际部署时需要安装和配置paperscraper
            logger.info(f"Paperscraper搜索: {query}")
            
            # 模拟延迟
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 这里返回空列表，实际实现时替换为真正的paperscraper调用
            return []
            
        except Exception as e:
            logger.error(f"Paperscraper搜索错误: {e}")
            return []
    
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
    """Google Scholar客户端 - 使用智能请求策略避免限制"""
    
    def __init__(self):
        self.base_url = "https://scholar.google.com/scholar"
        self.session = None
        self._last_request_time = datetime.now()
        self._min_delay = 3  # 最小请求间隔（秒）
        
    async def _get_session(self):
        """获取异步HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索Google Scholar文献（谨慎处理以避免被封禁）"""
        try:
            # 确保请求间隔
            now = datetime.now()
            time_since_last = (now - self._last_request_time).total_seconds()
            if time_since_last < self._min_delay:
                await asyncio.sleep(self._min_delay - time_since_last)
            
            session = await self._get_session()
            
            # 构建请求头，模拟浏览器行为
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://scholar.google.com/',
                'DNT': '1'
            }
            
            params = {
                'q': query,
                'hl': 'en',
                'num': min(limit, 20),  # Google Scholar通常限制每页结果
                'start': 0
            }
            
            papers = []
            remaining = limit
            
            while remaining > 0:
                async with session.get(self.base_url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Google Scholar请求失败: {response.status}")
                        break
                    
                    html_content = await response.text()
                    page_papers = self._parse_scholar_html(html_content)
                    
                    if not page_papers:
                        break
                    
                    papers.extend(page_papers[:remaining])
                    remaining -= len(page_papers)
                    
                    if remaining > 0:
                        params['start'] += 20
                        # 添加随机延迟避免被检测
                        await asyncio.sleep(random.uniform(2, 4))
                
                self._last_request_time = datetime.now()
            
            return papers
            
        except Exception as e:
            logger.error(f"Google Scholar搜索错误: {e}")
            return []
    
    def _parse_scholar_html(self, html_content: str) -> List[Paper]:
        """解析Google Scholar HTML响应（简化版本）"""
        # 注意：实际实现需要使用HTML解析库（如beautifulsoup4）
        # 这里提供一个简化的实现
        papers = []
        
        try:
            # 这里应该使用proper HTML解析
            # 为了示例，返回一个空列表
            logger.info("Google Scholar HTML解析待实现")
            return []
            
        except Exception as e:
            logger.error(f"解析Google Scholar HTML错误: {e}")
            return []
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()

# 更新MultiSourceEngine类以包含新的数据源
class MultiSourceEngine:
    """多源数据获取引擎 - 核心搜索组件"""
    
    def __init__(self):
        self.semantic_scholar = SemanticScholarAPI()
        self.arxiv = ArxivAPI()
        self.paperscraper = PaperscraperClient()
        
    async def search_parallel(self, query: str, max_results: int = 50) -> List[Paper]:
        """并行搜索多个数据源"""
        logger.info(f"开始多源并行搜索: {query}")
        
        # 计算每个源的搜索数量
        per_source_limit = max(10, max_results // 3)  # 现在有3个数据源
        
        try:
            # 并行调用所有搜索源
            tasks = [
                self.semantic_scholar.search(query, per_source_limit),
                self.arxiv.search(query, per_source_limit),
                self.paperscraper.search(query, per_source_limit)
            ]
            
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
            ranked_papers = self._rank_papers(deduplicated_papers, query)
            
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
                'paperscraper': 0.9
            }
            score *= source_weights.get(paper.source, 1.0)
            
            paper.relevance_score = score
        
        # 按相关性得分排序
        return sorted(papers, key=lambda p: p.relevance_score, reverse=True)
    
    async def close(self):
        """关闭所有连接"""
        await asyncio.gather(
            self.semantic_scholar.close(),
            self.arxiv.close(),
            self.paperscraper.close()
        )

# 使用示例
async def main():
    """测试多源搜索引擎"""
    engine = MultiSourceEngine()
    
    try:
        # 测试搜索
        results = await engine.search_parallel("machine learning", max_results=20)
        
        print(f"找到 {len(results)} 篇论文:")
        for i, paper in enumerate(results[:5], 1):
            print(f"\n{i}. {paper.title}")
            print(f"   作者: {', '.join(paper.authors[:3])}")
            print(f"   来源: {paper.source}")
            print(f"   年份: {paper.year}")
            print(f"   相关性得分: {paper.relevance_score:.2f}")
            
    finally:
        await engine.close()

if __name__ == "__main__":
    asyncio.run(main())