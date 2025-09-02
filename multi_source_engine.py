"""
多源数据获取引擎 - Paper God核心搜索组件（简化版）
实现 Semantic Scholar + arXiv + Google Scholar 多源并行搜索
"""

import asyncio
import aiohttp
import time
import random
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
import os
from dotenv import load_dotenv
from scholar_mirror_api import ScholarMirrorAPI
from scholar_dock_spider import ScholarDockSpider, ScholarDockPaper

# 加载环境变量
load_dotenv()


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取配置 - 只启用指定的三个数据源
SEMANTIC_SCHOLAR_ENABLED = os.getenv("SEMANTIC_SCHOLAR_ENABLED", "false").lower() == "true"  # 暂时禁用
# 启用ScholarPy（自定义的Google Scholar访问实现）
SCHOLAR_PY_ENABLED = os.getenv("SCHOLAR_PY_ENABLED", "false").lower() == "true"  
# ScholarDock高效爬虫（推荐使用，默认启用）
SCHOLAR_DOCK_ENABLED = os.getenv("SCHOLAR_DOCK_ENABLED", "true").lower() == "true"
# 新增：控制是否启用Google Scholar（默认启用作为主力搜索源）
GOOGLE_SCHOLAR_ENABLED = os.getenv("GOOGLE_SCHOLAR_ENABLED", "true").lower() == "true"
# 启用arXiv作为辅助数据源
ARXIV_ENABLED = os.getenv("ARXIV_ENABLED", "true").lower() == "true"
# 暂时禁用其他数据源
CROSSREF_ENABLED = os.getenv("CROSSREF_ENABLED", "false").lower() == "true"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
PUBMED_ENABLED = False  # 暂时禁用


# 兼容性支持：SCHOLARLY_ENABLED 映射到 SCHOLAR_PY_ENABLED
if os.getenv("SCHOLARLY_ENABLED"):
    SCHOLAR_PY_ENABLED = os.getenv("SCHOLARLY_ENABLED", "true").lower() == "true"

@dataclass
class Paper:
    """论文数据结构 - 集成ScholarDock增强字段"""
    title: str
    authors: List[str]
    abstract: str
    year: Optional[int]
    journal: str
    url: str
    doi: Optional[str]
    citations: Optional[int]
    source: str
    relevance_score: float = 0.0
    pmid: Optional[str] = None
    keywords: Optional[List[str]] = None
    
    # ScholarDock增强字段
    citations_per_year: float = 0.0
    venue: str = ""
    publisher: str = ""
    description: str = ""

def convert_scholar_dock_paper(scholar_paper: ScholarDockPaper) -> Paper:
    """将ScholarDockPaper转换为标准Paper对象"""
    return Paper(
        title=scholar_paper.title,
        authors=scholar_paper.authors,
        abstract=scholar_paper.abstract or scholar_paper.description,
        year=scholar_paper.year,
        journal=scholar_paper.journal or scholar_paper.venue,
        url=scholar_paper.url,
        doi=scholar_paper.doi,
        citations=scholar_paper.citations,
        source=scholar_paper.source,
        relevance_score=0.0,
        pmid=None,
        keywords=None,
        # ScholarDock增强字段
        citations_per_year=scholar_paper.citations_per_year,
        venue=scholar_paper.venue,
        publisher=scholar_paper.publisher,
        description=scholar_paper.description
    )

class SemanticScholarAPI:
    """Semantic Scholar API客户端 - 简化版"""
    
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.session = None
        self._last_request = 0
        self._min_delay = 3.0
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': 'PaperGod/1.0 (Academic Research Tool)',
                'Accept': 'application/json'
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """简化的搜索方法"""
        try:
            # 简化的限频控制
            current_time = time.time()
            time_since_last = current_time - self._last_request
            if time_since_last < self._min_delay:
                await asyncio.sleep(self._min_delay - time_since_last)
            
            session = await self._get_session()
            
            params = {
                'query': query,
                'limit': limit,
                'fields': 'title,authors,abstract,year,journal,url,citationCount,externalIds'
            }
            
            self._last_request = time.time()
            
            async with session.get(f"{self.base_url}/paper/search", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_papers(data.get('data', []))
                elif response.status == 429:
                    logger.warning("Semantic Scholar API限频，等待后重试")
                    await asyncio.sleep(10)
                    return []
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
                authors = []
                if paper_data.get('authors'):
                    authors = [author.get('name', '') for author in paper_data['authors'] if author.get('name')]
                
                # 提取DOI
                doi = None
                external_ids = paper_data.get('externalIds', {})
                if external_ids and 'DOI' in external_ids:
                    doi = external_ids['DOI']
                
                # 期刊信息
                journal_info = paper_data.get('journal', {})
                journal = journal_info.get('name', '') if journal_info else ''
                
                # 安全获取标题
                title = paper_data.get('title', '').strip() if paper_data.get('title') else ''
                
                # 跳过没有标题的论文
                if not title:
                    continue
                
                abstract = paper_data.get('abstract', '').strip() if paper_data.get('abstract') else ''
                
                # 增强年份和引用数的处理
                year = paper_data.get('year')
                if year and not isinstance(year, int):
                    try:
                        year = int(year)
                    except (ValueError, TypeError):
                        year = None
                
                citations = paper_data.get('citationCount', 0)
                if citations and not isinstance(citations, int):
                    try:
                        citations = int(citations)
                        # 合理性检查
                        if citations < 0 or citations > 1000000:
                            citations = 0
                    except (ValueError, TypeError):
                        citations = 0
                
                paper = Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    journal=journal,
                    url=paper_data.get('url', ''),
                    doi=doi,
                    citations=citations,
                    source='semantic_scholar'
                )
                papers.append(paper)
            except Exception as e:
                logger.warning(f"解析论文数据错误: {e}")
                continue
                
        return papers
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

class ArxivAPI:
    """arXiv API客户端"""
    
    def __init__(self):
        self.base_url = "https://export.arxiv.org/api/query"
        self.session = None
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索arXiv预印本"""
        try:
            logger.debug(f"🔍 arXiv搜索开始: {query}")
            session = await self._get_session()
            
            # 优化查询格式：直接使用query，去掉all:前缀
            params = {
                'search_query': query,
                'start': 0,
                'max_results': limit,
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            logger.debug(f"📋 arXiv查询参数: {params}")
            
            async with session.get(self.base_url, params=params) as response:
                logger.debug(f"📡 arXiv响应状态: {response.status}")
                if response.status == 200:
                    xml_content = await response.text()
                    logger.debug(f"📄 arXiv响应内容长度: {len(xml_content)}")
                    papers = self._parse_arxiv_xml(xml_content)
                    logger.debug(f"✅ arXiv搜索完成: 返回 {len(papers)} 篇论文")
                    return papers
                else:
                    logger.warning(f"arXiv API错误: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"arXiv搜索错误: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return []
    
    def _parse_arxiv_xml(self, xml_content: str) -> List[Paper]:
        """解析arXiv XML响应"""
        papers = []
        try:
            root = ET.fromstring(xml_content)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            
            # 调试：检查找到多少entry
            entries = root.findall('atom:entry', namespace)
            logger.debug(f"arXiv XML解析: 找到 {len(entries)} 个entry元素")
            
            for entry in entries:
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
                    
                    # 提取年份 - 增强版本
                    from datetime import datetime
                    current_year = datetime.now().year
                    
                    published = entry.find('atom:published', namespace)
                    year = None
                    if published is not None:
                        try:
                            year_str = published.text.strip()[:4]
                            year = int(year_str)
                            # 年份合理性检查
                            if year < 1900 or year > current_year + 2:
                                year = None
                        except (ValueError, TypeError, AttributeError):
                            # 尝试从更新时间提取
                            updated = entry.find('atom:updated', namespace)
                            if updated is not None:
                                try:
                                    year_candidate = int(updated.text.strip()[:4])
                                    if 1900 <= year_candidate <= current_year + 2:
                                        year = year_candidate
                                except (ValueError, TypeError, AttributeError):
                                    # 如果都失败，设为当前年份（arXiv通常是较新的论文）
                                    year = current_year
                    
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
                        citations=0,  # arXiv通常没有引用数据
                        source='arxiv'
                    )
                    papers.append(paper)
                    logger.debug(f"✅ 成功解析arXiv论文: {title[:50]}...")
                    
                except Exception as e:
                    logger.debug(f"❌ 解析单个arXiv entry失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析arXiv XML错误: {e}")
            
        logger.debug(f"arXiv XML解析完成: 共解析出 {len(papers)} 篇论文")
        return papers
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

class ScholarPyAPI:
    """自定义的Google Scholar API客户端 - 简化且稳定的实现"""
    
    def __init__(self):
        import urllib.request
        import urllib.parse
        from http.cookiejar import MozillaCookieJar
        
        self.base_url = "https://scholar.google.com/scholar"
        # 使用多个真实浏览器User-Agent，随机选择
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        
        # Cookie管理 - 关键的反CAPTCHA机制
        self.cookie_file = os.path.join(os.path.dirname(__file__), '.scholar_cookies.txt')
        self.cjar = MozillaCookieJar()
        
        # 加载已存在的cookies
        if os.path.exists(self.cookie_file):
            try:
                self.cjar.load(self.cookie_file, ignore_discard=True)
                logger.info("✅ 已加载Google Scholar cookies")
            except Exception as e:
                logger.warning(f"⚠️ 无法加载cookies: {e}")
                self.cjar = MozillaCookieJar()
        
        # 创建opener
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cjar))
        
        # 延迟控制 - 极保守的策略
        self.last_request_time = 0
        self.min_delay = 20.0  # 极保守的延迟策略，20秒间隔
        self.request_count = 0
        self.session_start = time.time()
        
        # 错误控制
        self.consecutive_failures = 0
        self.max_failures = 1  # 降低失败阈值，更快触发禁用
        self.is_temporarily_disabled = False
        self.disable_until = 0
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """使用自定义机制搜索Google Scholar，带重试机制"""
        # 检查是否临时禁用
        if self._check_if_disabled():
            logger.info("⏸️ ScholarPy当前临时禁用中，跳过搜索")
            return []
        
        max_retries = 2  # 最大重试次数
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # 延迟控制
                await self._apply_delay()
                
                # 构建查询URL
                url = self._build_query_url(query, limit)
                if retry_count == 0:
                    logger.info(f"🔍 ScholarPy搜索: {query}")
                else:
                    logger.info(f"🔄 ScholarPy重试搜索: {query} (第{retry_count}次重试)")
                
                # 发送请求
                html_content = self._get_http_response(url)
                if html_content is None:
                    # 如果是429错误，增加重试延迟
                    if retry_count < max_retries:
                        retry_delay = 30 + (retry_count * 20)  # 30s, 50s递增延迟
                        logger.warning(f"⏳ ScholarPy请求失败，{retry_delay}秒后重试")
                        await asyncio.sleep(retry_delay)
                        retry_count += 1
                        continue
                    else:
                        self._handle_failure()
                        return []
                
                # 保存cookies
                self._save_cookies()
                
                # 解析结果
                papers = self._parse_results(html_content)
                
                # 重置失败计数
                self.consecutive_failures = 0
                
                logger.info(f"✅ ScholarPy返回 {len(papers)} 篇论文")
                return papers
                
            except Exception as e:
                logger.error(f"ScholarPy搜索错误: {e}")
                if retry_count < max_retries:
                    retry_delay = 20 + (retry_count * 15)
                    logger.warning(f"⏳ 搜索异常，{retry_delay}秒后重试")
                    await asyncio.sleep(retry_delay)
                    retry_count += 1
                    continue
                else:
                    self._handle_failure()
                    return []
        
        return []
    
    def _build_query_url(self, query: str, limit: int) -> str:
        """构建Google Scholar查询URL"""
        import urllib.parse
        
        params = {
            'q': query,
            'hl': 'en',
            'as_sdt': '0,5',  # 包括专利和引用
            'num': min(limit, 20)  # Google Scholar限制
        }
        
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        return url
    
    def _get_http_response(self, url: str) -> str:
        """发送HTTP请求获取响应，专门处理429错误"""
        import urllib.request
        import urllib.error
        import random
        
        try:
            # 随机选择User-Agent
            user_agent = random.choice(self.user_agents)
            req = urllib.request.Request(url, headers={'User-Agent': user_agent})
            response = self.opener.open(req, timeout=15)
            
            if response.getcode() == 200:
                return response.read().decode('utf-8')
            elif response.getcode() == 429:
                logger.warning(f"⚠️ Google Scholar访问频率限制 (HTTP 429) - 将启用智能重试机制")
                return None
            else:
                logger.warning(f"ScholarPy HTTP响应码: {response.getcode()}")
                return None
                
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"⚠️ Google Scholar访问频率限制 (HTTP 429) - 系统将自动切换到其他数据源")
            else:
                logger.warning(f"ScholarPy网络错误: HTTP {e.code}")
            return None
        except Exception as e:
            logger.error(f"ScholarPy HTTP请求失败: {e}")
            return None
    
    def _parse_results(self, html_content: str) -> List[Paper]:
        """解析Google Scholar搜索结果"""
        papers = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找结果条目
            results = soup.find_all('div', class_='gs_ri')
            
            for result in results:
                try:
                    paper = self._parse_single_result(result)
                    if paper:
                        papers.append(paper)
                except Exception as e:
                    logger.debug(f"解析单个结果失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析Scholar结果失败: {e}")
            
        return papers
    
    def _parse_single_result(self, result_div) -> Optional[Paper]:
        """解析单个搜索结果"""
        try:
            # 标题
            title_element = result_div.find('h3', class_='gs_rt')
            if not title_element:
                return None
                
            title_link = title_element.find('a')
            title = title_link.get_text(strip=True) if title_link else title_element.get_text(strip=True)
            url = title_link.get('href', '') if title_link else ''
            
            # 作者和期刊信息
            authors = []
            journal = ''
            year = None
            
            author_element = result_div.find('div', class_='gs_a')
            if author_element:
                author_text = author_element.get_text()
                # 简单解析: 通常格式为 "作者 - 期刊, 年份"
                if ' - ' in author_text:
                    author_part = author_text.split(' - ')[0]
                    authors = [author.strip() for author in author_part.split(',')]
                    
                    # 提取年份 - 增强版本
                    import re
                    import datetime
                    current_year = datetime.now().year
                    
                    # 多种年份匹配模式
                    year_patterns = [
                        r'\b((?:19|20)\d{2})\b(?=\s*-)',  # 年份后跟破折号
                        r'\(((?:19|20)\d{2})\)',           # 括号内的年份
                        r'\b((?:19|20)\d{2})\b'           # 一般4位数年份
                    ]
                    
                    for pattern in year_patterns:
                        year_matches = re.findall(pattern, author_text)
                        if year_matches:
                            for year_str in year_matches:
                                try:
                                    year_candidate = int(year_str)
                                    if 1900 <= year_candidate <= current_year + 2:
                                        year = year_candidate
                                        break
                                except ValueError:
                                    continue
                            if year:
                                break
            
            # 摘要/片段
            abstract = ''
            snippet_element = result_div.find('div', class_='gs_rs')
            if snippet_element:
                abstract = snippet_element.get_text(strip=True)
            
            # 引用数 - 增强版本
            citations = 0
            citation_patterns = [
                ('a', lambda text: text and 'Cited by' in text),
                ('a', lambda text: text and '引用' in text),
                ('a', lambda text: text and '被引用' in text)
            ]
            
            for tag_name, text_filter in citation_patterns:
                citation_element = result_div.find(tag_name, string=text_filter)
                if citation_element:
                    import re
                    citation_patterns_regex = [
                        r'Cited by\s*(\d+)',
                        r'引用\s*(\d+)',
                        r'被引用\s*(\d+)',
                        r'>\s*(\d+)\s*</'
                    ]
                    
                    for pattern in citation_patterns_regex:
                        citation_match = re.search(pattern, citation_element.get_text())
                        if citation_match:
                            try:
                                citations = int(citation_match.group(1))
                                if 0 <= citations <= 1000000:  # 合理性检查
                                    break
                                else:
                                    citations = 0
                            except (ValueError, IndexError):
                                continue
                    if citations > 0:
                        break
            
            # 数据校验和清洗
            if not title or title.strip() == "":
                logger.debug("标题为空，跳过该论文")
                return None
                
            return Paper(
                title=title.strip(),
                authors=authors,
                abstract=abstract.strip() if abstract else "",
                year=year,
                journal=journal.strip() if journal else "",
                url=url.strip() if url else "",
                doi=None,  # Scholar通常不直接提供DOI
                citations=citations,
                source='scholar_py',
                relevance_score=1.0
            )
            
        except Exception as e:
            logger.debug(f"解析结果详情失败: {e}")
            return None
    
    async def _apply_delay(self):
        """应用智能延迟策略"""
        import time
        import random
        
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        session_duration = current_time - self.session_start
        
        # 计算动态延迟
        base_delay = self.min_delay
        
        # 如果是会话开始或长时间间隔，使用更长延迟
        if self.last_request_time == 0 or time_since_last > 300:  # 5分钟
            base_delay = random.uniform(20.0, 35.0)  # 首次/长间隔延迟更保守，增加变化范围
            logger.info(f"🕒 ScholarPy首次/长间隔延迟: {base_delay:.2f}秒")
        elif self.request_count > 2:  # 连续请求增加延迟，降低触发阈值
            base_delay = self.min_delay + (self.request_count - 2) * random.uniform(2.0, 5.0)  # 随机化递增延迟
            logger.debug(f"🕒 ScholarPy递增延迟: {base_delay:.2f}秒 (第{self.request_count}次请求)")
        
        # 应用随机化，模拟人类访问模式
        if time_since_last < base_delay:
            jitter = random.uniform(5.0, 12.0)  # 更大的随机抖动
            delay = base_delay - time_since_last + jitter
            logger.debug(f"🕒 ScholarPy延迟: {delay:.2f}秒")
            await asyncio.sleep(delay)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def _save_cookies(self):
        """保存cookies到文件"""
        try:
            self.cjar.save(self.cookie_file, ignore_discard=True)
            logger.debug("💾 已保存Scholar cookies")
        except Exception as e:
            logger.debug(f"保存cookies失败: {e}")
    
    def _check_if_disabled(self) -> bool:
        """检查是否因连续失败而临时禁用"""
        current_time = time.time()
        if self.is_temporarily_disabled and current_time < self.disable_until:
            return True
        elif self.is_temporarily_disabled and current_time >= self.disable_until:
            # 禁用期已过，重新启用
            self.is_temporarily_disabled = False
            self.consecutive_failures = 0
            logger.info("🔓 ScholarPy临时禁用期已过，重新启用")
            return False
        return False
    
    def _handle_failure(self):
        """处理请求失败"""
        self.consecutive_failures += 1
        logger.warning(f"⚠️ ScholarPy失败计数: {self.consecutive_failures}/{self.max_failures}")
        
        if self.consecutive_failures >= self.max_failures:
            # 临时禁用60分钟，大幅增加禁用时长
            self.is_temporarily_disabled = True
            self.disable_until = time.time() + (60 * 60)  # 60分钟
            logger.info("📍 Google Scholar已暂时限制访问，系统将依靠Semantic Scholar和arXiv提供搜索结果（60分钟后自动重试）")
            
        # 重置请求计数，避免累积效应
        self.request_count = 0
    
    async def close(self):
        """清理资源"""
        pass


class ScholarDockAPI:
    """ScholarDock高效Google Scholar爬虫API包装器"""
    
    def __init__(self):
        self.spider = None
        logger.info("🚀 ScholarDock API初始化")
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """使用ScholarDock技术搜索Google Scholar"""
        try:
            logger.info(f"🔍 ScholarDock开始搜索: {query}")
            
            # 创建并使用ScholarDock爬虫
            async with ScholarDockSpider() as spider:
                scholar_papers = await spider.search(query, limit)
            
            # 转换为标准Paper对象
            papers = []
            for scholar_paper in scholar_papers:
                try:
                    paper = convert_scholar_dock_paper(scholar_paper)
                    papers.append(paper)
                except Exception as e:
                    logger.warning(f"转换论文失败: {e}")
                    continue
            
            logger.info(f"✅ ScholarDock返回 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"ScholarDock搜索失败: {e}")
            return []
    
    async def close(self):
        """清理资源"""
        pass

class CrossrefAPI:
    """Crossref API客户端"""
    
    def __init__(self):
        self.base_url = "https://api.crossref.org/works"
        self.session = None
        self._last_request = 0
        self._min_delay = 1.0
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索论文"""
        if not CROSSREF_ENABLED:
            return []
            
        try:
            # 限频控制
            current_time = time.time()
            time_since_last = current_time - self._last_request
            if time_since_last < self._min_delay:
                await asyncio.sleep(self._min_delay - time_since_last)
            
            session = await self._get_session()
            
            params = {
                'query': query,
                'rows': limit,
                'select': 'DOI,title,author,published,abstract,URL,is-referenced-by-count,publisher,container-title,subtitle'
            }
            
            self._last_request = time.time()
            
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('message', {}).get('items', [])
                    return self._parse_papers(items)
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Crossref搜索出错: {e}")
            return []
            
    def _parse_papers(self, items: List[Dict]) -> List[Paper]:
        """解析Crossref响应数据"""
        papers = []
        for item in items:
            try:
                # 标题
                title_list = item.get('title', [])
                title = (title_list[0] if title_list else "").strip()
                
                # 跳过没有标题的论文
                if not title:
                    continue
                
                # 作者
                authors = []
                for author in item.get('author', []):
                    if 'given' in author and 'family' in author:
                        full_name = f"{author['given']} {author['family']}"
                        authors.append(full_name)
                    elif 'family' in author:
                        authors.append(author['family'])
                
                # 作者信息缺失时保持空列表
                
                # 年份
                year = None
                published = item.get('published-print') or item.get('published-online')
                if published and 'date-parts' in published:
                    date_parts = published['date-parts'][0]
                    if date_parts:
                        try:
                            year = int(date_parts[0])
                        except:
                            pass
                
                # 摘要处理 - 只使用真实数据
                abstract = item.get('abstract', '').strip() if item.get('abstract') else ''
                
                # DOI和URL
                doi = item.get('DOI', '').strip()
                url = item.get('URL', '').strip()
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                
                # 引用数
                citations = item.get('is-referenced-by-count', 0)
                try:
                    citations = int(citations)
                except:
                    citations = 0
                
                # 期刊信息 - 只使用真实数据
                journal = ''
                if item.get('container-title') and len(item['container-title']) > 0:
                    journal = item['container-title'][0].strip()
                elif item.get('publisher'):
                    journal = item['publisher'].strip()
                
                paper = Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    journal=journal,
                    url=url,
                    doi=doi,
                    citations=citations,
                    source="crossref"
                )
                papers.append(paper)
                
            except Exception as e:
                continue
                
        return papers
        
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

class PubMedAPI:
    """PubMed API客户端"""
    
    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.session = None
        self.api_key = PUBMED_API_KEY
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索PubMed文献"""
        try:
            session = await self._get_session()
            
            # 搜索文献ID
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
                    return []
                    
                search_data = await response.json()
                pmids = search_data['esearchresult']['idlist']
                
                if not pmids:
                    return []
                
            # 获取详细信息
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'xml'
            }
            if self.api_key:
                fetch_params['api_key'] = self.api_key
                
            async with session.get(f"{self.base_url}/efetch.fcgi", params=fetch_params) as response:
                if response.status != 200:
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
                    # 基本信息提取
                    pmid = article.find(".//PMID").text
                    
                    title_element = article.find(".//ArticleTitle")
                    title = title_element.text if title_element is not None else ""
                    
                    # 作者
                    authors = []
                    for author in article.findall(".//Author"):
                        last_name = author.find("LastName")
                        fore_name = author.find("ForeName")
                        if last_name is not None and fore_name is not None:
                            authors.append(f"{fore_name.text} {last_name.text}")
                        elif last_name is not None:
                            authors.append(last_name.text)
                    
                    # 摘要
                    abstract_element = article.find(".//Abstract/AbstractText")
                    abstract = abstract_element.text if abstract_element is not None else ""
                    
                    # 年份
                    year = None
                    pub_date = article.find(".//PubDate")
                    if pub_date is not None:
                        year_element = pub_date.find("Year")
                        if year_element is not None:
                            year = int(year_element.text)
                    
                    # 期刊
                    journal_element = article.find(".//Journal/Title")
                    journal = journal_element.text if journal_element is not None else ""
                    
                    # DOI
                    doi = None
                    for article_id in article.findall(".//ArticleId"):
                        if article_id.get("IdType") == "doi":
                            doi = article_id.text
                            break
                    
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    
                    paper = Paper(
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        year=year,
                        journal=journal,
                        url=url,
                        doi=doi,
                        citations=None,
                        source='pubmed',
                        pmid=pmid
                    )
                    papers.append(paper)
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            logger.error(f"解析PubMed XML错误: {e}")
            
        return papers
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

class MultiSourceEngine:
    """多源数据获取引擎 - 简化版"""
    
    def __init__(self):
        # 初始化数据源 - 根据配置启用/禁用
        self.arxiv = ArxivAPI() if ARXIV_ENABLED else None
        
        # Google Scholar访问 - 只使用ScholarDock
        if GOOGLE_SCHOLAR_ENABLED and SCHOLAR_DOCK_ENABLED:
            self.scholarly = ScholarDockAPI()
            logger.info("🚀 使用ScholarDock高效爬虫引擎")
            # 新增：镜像API作为备用方案
            self.scholar_mirror = ScholarMirrorAPI()
        else:
            self.scholarly = None
            self.scholar_mirror = None
            logger.info("🚫 Google Scholar已禁用，使用稳定数据源")
        
        self.semantic_scholar = SemanticScholarAPI() if SEMANTIC_SCHOLAR_ENABLED else None
        self.crossref = CrossrefAPI() if CROSSREF_ENABLED else None
        self.pubmed = PubMedAPI() if PUBMED_ENABLED else None
        
        
        # 显示启用的数据源
        enabled_sources = []
        disabled_sources = []
        
        if self.arxiv:
            enabled_sources.append("arXiv")
        else:
            disabled_sources.append("arXiv")
            
        if self.scholarly:
            enabled_sources.append("ScholarDock高效爬虫")
            if self.scholar_mirror:
                enabled_sources.append("Google Scholar镜像 (备用)")
        else:
            disabled_sources.append("Google Scholar")
            
        if self.semantic_scholar:
            enabled_sources.append("Semantic Scholar") 
        else:
            disabled_sources.append("Semantic Scholar")
            
        if self.crossref:
            enabled_sources.append("Crossref")
        else:
            disabled_sources.append("Crossref")
            
        if self.pubmed:
            enabled_sources.append("PubMed")
        else:
            disabled_sources.append("PubMed")
        
            
        logger.info(f"✅ 多源搜索引擎初始化完成")
        logger.info(f"🟢 启用数据源 ({len(enabled_sources)}): {', '.join(enabled_sources)}")
        if disabled_sources:
            logger.info(f"🔴 禁用数据源 ({len(disabled_sources)}): {', '.join(disabled_sources)}")
    
    async def search_parallel(self, query: str, max_results: int = 20, analysis: Optional[Dict] = None) -> List[Paper]:
        """并行搜索多个数据源（支持统一布尔查询）"""
        return await self.search_parallel_with_filters(query, max_results, analysis=analysis)
    
    def _build_unified_boolean_query(self, query: str, analysis: Optional[Dict] = None, use_fallback: bool = False) -> Dict[str, str]:
        """构建统一的4层权重映射布尔查询，适配不同搜索源"""
        unified_queries = {}
        
        # 构建4层权重映射的布尔查询
        boolean_query = self._build_hierarchical_boolean_query(query, analysis, use_fallback)
        logger.info(f"构建4层权重布尔查询: {boolean_query}")
        
        # 为每个搜索源适配查询格式
        unified_queries['scholar_dock'] = boolean_query  # ScholarDock处理复杂查询
        unified_queries['semantic_scholar'] = self._adapt_query_for_semantic_scholar(boolean_query)
        unified_queries['arxiv'] = self._adapt_query_for_arxiv(boolean_query)
        unified_queries['crossref'] = self._adapt_query_for_crossref(boolean_query)
        unified_queries['pubmed'] = self._adapt_query_for_pubmed(boolean_query)
        
        return unified_queries
    
    def _build_hierarchical_boolean_query(self, query: str, analysis: Optional[Dict] = None, use_fallback: bool = False) -> str:
        """构建4层权重映射的布尔查询
        
        布尔结构：
        (exact_terms) AND 
        (core_synonyms OR exact_terms) AND
        (related_terms OR context_terms)
        
        如果use_fallback=True，则只使用exact_terms进行补充搜索
        """
        try:
            # 如果是降级搜索，只使用exact_terms
            if use_fallback and analysis and analysis.get("hierarchical_keywords"):
                exact_terms = analysis["hierarchical_keywords"].get("exact_terms", {}).get("terms", [])
                if exact_terms:
                    # 简单的精确术语查询
                    fallback_query = ' OR '.join([f'"{term}"' for term in exact_terms])
                    logger.info(f"🔄 使用降级查询(exact_terms): {fallback_query}")
                    return fallback_query
                else:
                    logger.warning("⚠️ 没有exact_terms可用于降级查询，使用原查询")
                    return query
            
            # 如果有LLM分析结果，构建4层权重布尔查询
            if analysis and analysis.get("hierarchical_keywords"):
                hierarchical_keywords = analysis["hierarchical_keywords"]
                
                # 提取各层关键词
                exact_terms = hierarchical_keywords.get("exact_terms", {}).get("terms", [])
                core_synonyms = hierarchical_keywords.get("core_synonyms", {}).get("terms", [])
                related_terms = hierarchical_keywords.get("related_terms", {}).get("terms", [])
                context_terms = hierarchical_keywords.get("context_terms", {}).get("terms", [])
                
                # 构建布尔查询各部分
                query_parts = []
                
                # 第1层：exact_terms（必须匹配）
                if exact_terms:
                    exact_part = '(' + ' OR '.join([f'"{term}"' for term in exact_terms]) + ')'
                    query_parts.append(exact_part)
                
                # 第2层：core_synonyms OR exact_terms（高权重同义词）
                if core_synonyms:
                    synonym_terms = core_synonyms + exact_terms  # 包含精确术语
                    synonym_part = '(' + ' OR '.join([f'"{term}"' for term in synonym_terms]) + ')'
                    query_parts.append(synonym_part)
                
                # 第3层：related_terms OR context_terms（相关扩展）
                related_context_terms = related_terms + context_terms
                if related_context_terms:
                    related_part = '(' + ' OR '.join([f'"{term}"' for term in related_context_terms]) + ')'
                    query_parts.append(related_part)
                
                # 用AND连接各层
                if query_parts:
                    hierarchical_query = ' AND '.join(query_parts)
                    logger.info(f"✅ 构建4层权重布尔查询成功")
                    logger.debug(f"📊 查询层次: exact({len(exact_terms)}) + synonyms({len(core_synonyms)}) + related({len(related_terms)}) + context({len(context_terms)})")
                    return hierarchical_query
                else:
                    logger.warning("⚠️ 无法从层次关键词构建查询，使用原查询")
                    return query
            
            # 如果有简单的优化查询，直接使用
            elif analysis and analysis.get("optimized_boolean_query"):
                boolean_query = analysis["optimized_boolean_query"]
                logger.info(f"使用LLM优化布尔查询: {boolean_query}")
                return boolean_query
            
            # 没有分析结果，使用原始查询
            else:
                logger.info(f"使用原始查询: {query}")
                return query
                
        except Exception as e:
            logger.error(f"❌ 构建层次布尔查询失败: {e}")
            return query
    
    def _adapt_query_for_semantic_scholar(self, boolean_query: str) -> str:
        """为Semantic Scholar适配查询 - 智能提取核心术语"""
        try:
            # Semantic Scholar使用自然语言查询，提取引号内的核心术语
            import re
            
            # 首先提取所有引号内的术语
            quoted_terms = re.findall(r'"([^"]*)"', boolean_query)
            
            if quoted_terms:
                # 使用前6个最重要的术语（去重）
                unique_terms = list(dict.fromkeys(quoted_terms))[:6]
                adapted = ' '.join(unique_terms)
                logger.debug(f"Semantic Scholar查询适配: {boolean_query} -> {adapted}")
                return adapted
            else:
                # 没有引号，简化布尔操作符
                adapted = boolean_query
                adapted = re.sub(r'\s+(AND|OR)\s+', ' ', adapted)
                adapted = re.sub(r'[()"]', '', adapted)
                return adapted.strip()
                
        except Exception as e:
            logger.warning(f"Semantic Scholar查询适配失败: {e}")
            # 降级处理
            simplified = boolean_query.replace(' AND ', ' ').replace(' OR ', ' ')
            return re.sub(r'[()"]', '', simplified).strip()
    
    def _adapt_query_for_arxiv(self, boolean_query: str) -> str:
        """为arXiv适配查询 - 支持布尔操作但简化过长查询"""
        try:
            # arXiv支持布尔操作符，但有长度限制
            if len(boolean_query) > 300:
                # 查询过长，提取核心术语
                import re
                quoted_terms = re.findall(r'"([^"]*)"', boolean_query)
                if quoted_terms:
                    # 使用前4个核心术语构建简单查询
                    core_terms = quoted_terms[:4]
                    simplified = ' OR '.join([f'"{term}"' for term in core_terms])
                    logger.debug(f"arXiv查询简化: {len(boolean_query)}字符 -> {simplified}")
                    return simplified
                else:
                    return boolean_query[:300]
            else:
                return boolean_query
                
        except Exception as e:
            logger.warning(f"arXiv查询适配失败: {e}")
            return boolean_query
    
    def _adapt_query_for_crossref(self, boolean_query: str) -> str:
        """为Crossref适配查询 - 提取关键术语"""
        try:
            # Crossref使用简单查询，提取最重要的术语
            import re
            
            # 提取引号内的术语
            quoted_terms = re.findall(r'"([^"]*)"', boolean_query)
            
            if quoted_terms:
                # 使用前3个最重要的术语
                core_terms = quoted_terms[:3]
                adapted = ' '.join(core_terms)
                logger.debug(f"Crossref查询适配: 提取{len(core_terms)}个核心术语")
                return adapted
            else:
                # 简化布尔操作符
                adapted = re.sub(r'\s+(AND|OR)\s+', ' ', boolean_query)
                adapted = re.sub(r'[()"]', '', adapted)
                return adapted.strip()
                
        except Exception as e:
            logger.warning(f"Crossref查询适配失败: {e}")
            simplified = boolean_query.replace(' AND ', ' ').replace(' OR ', ' ')
            return re.sub(r'[()"]', '', simplified).strip()
    
    def _adapt_query_for_pubmed(self, boolean_query: str) -> str:
        """为PubMed适配查询 - 保持布尔逻辑但调整格式"""
        try:
            # PubMed支持布尔操作符，但对引号处理不同
            adapted = boolean_query.replace('"', '')
            
            # 如果查询过长，简化为主要术语
            if len(adapted) > 400:
                import re
                # 提取主要的AND组合
                and_parts = adapted.split(' AND ')
                if len(and_parts) > 3:
                    # 只保留前3个AND部分
                    adapted = ' AND '.join(and_parts[:3])
                    logger.debug(f"PubMed查询简化: 保留前3个AND部分")
            
            return adapted
            
        except Exception as e:
            logger.warning(f"PubMed查询适配失败: {e}")
            return boolean_query.replace('"', '')

    async def search_parallel_with_filters(
        self, 
        query: str, 
        max_results: int = 20, 
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        sources: Optional[List[str]] = None,
        analysis: Optional[Dict] = None,
        mode: Optional[str] = None  # 新增：搜索模式
    ) -> List[Paper]:
        """并行搜索多个数据源（带筛选参数和统一布尔查询）"""
        logger.info(f"开始多源并行搜索: {query}")
        
        # 构建统一的布尔查询
        unified_queries = self._build_unified_boolean_query(query, analysis)
        logger.info(f"构建统一布尔查询完成，适配{len(unified_queries)}个搜索源")
        
        # 优先级排序：稳定数据源优先，Google Scholar作为补充
        stable_sources = [
            ('semantic_scholar', self.semantic_scholar),
            ('arxiv', self.arxiv),
            ('crossref', self.crossref),
            ('pubmed', self.pubmed)
        ]
        # 过滤掉禁用的数据源
        active_stable_sources_list = [(name, api) for name, api in stable_sources if api is not None]
        active_stable_sources = len(active_stable_sources_list)
        
        # Google Scholar作为补充数据源
        has_scholar = self.scholarly is not None
        active_sources = active_stable_sources + (1 if has_scholar else 0)
        
        # 修复搜索篇数分配逻辑：ScholarDock作为主力搜索源应获得更大配额
        if has_scholar and active_stable_sources > 0:
            # ScholarDock获得70%配额，其他数据源分享30%
            scholar_limit = max(10, int(max_results * 0.7))  # ScholarDock主力搜索70%
            remaining_quota = max_results - scholar_limit
            stable_per_source = max(5, int(remaining_quota // active_stable_sources)) if active_stable_sources > 0 else 0
        elif has_scholar and active_stable_sources == 0:
            # 只有ScholarDock时，获取全部结果
            stable_per_source = 0
            scholar_limit = max_results
        elif not has_scholar and active_stable_sources > 0:
            # 只有稳定数据源时
            stable_per_source = max(10, int(max_results // active_stable_sources))
            scholar_limit = 0
        else:
            stable_per_source = 0
            scholar_limit = 0
            
        logger.info(f"启用 {active_sources} 个数据源：ScholarDock主力搜索{scholar_limit}篇，其他源({active_stable_sources})每源{stable_per_source}篇")
        
        tasks = []
        source_names = []
        timeout = 30.0
        
        # 优先启动稳定数据源，后启动Google Scholar
        sources_to_search = []
        
        # 数据源名称映射（前端标识符 -> 内部标识符）
        source_mapping = {
            'scholarly': 'scholar_dock',
            'scholar_dock': 'scholar_dock',
            'arxiv': 'arxiv',
            'semantic_scholar': 'semantic_scholar', 
            'crossref': 'crossref',
            'pubmed': 'pubmed'
        }
        
        # 🎯 auto-search模式特殊处理：只使用Google Scholar和arXiv各50%
        if mode == "auto-search":
            logger.info("🎯 [auto-search] 使用Google Scholar 50% + arXiv 50%配比")
            
            scholar_limit = max_results // 2  # 50%给Google Scholar
            arxiv_limit = max_results - scholar_limit  # 剩余50%给arXiv
            
            sources_to_search = []
            if self.scholarly:
                sources_to_search.append(('scholar_dock', self.scholarly, 150.0, scholar_limit))
            if self.arxiv:
                sources_to_search.append(('arxiv', self.arxiv, 30.0, arxiv_limit))
            
            logger.info(f"📊 [auto-search] 配额分配: Google Scholar {scholar_limit}篇 + arXiv {arxiv_limit}篇")
            
        # 如果指定了特定数据源，只使用指定的数据源
        elif sources and isinstance(sources, list) and len(sources) > 0:
            logger.info(f"🎯 使用指定数据源: {sources}")
            
            # 重新计算配额分配（针对指定数据源）
            selected_sources = []
            for source_id in sources:
                internal_name = source_mapping.get(source_id, source_id)
                
                if internal_name == 'scholar_dock' and self.scholarly:
                    selected_sources.append(('scholar_dock', self.scholarly, 150.0))
                elif internal_name == 'arxiv' and self.arxiv:
                    selected_sources.append(('arxiv', self.arxiv, 30.0))
                elif internal_name == 'semantic_scholar' and self.semantic_scholar:
                    selected_sources.append(('semantic_scholar', self.semantic_scholar, 30.0))
                elif internal_name == 'crossref' and self.crossref:
                    selected_sources.append(('crossref', self.crossref, 30.0))
                elif internal_name == 'pubmed' and self.pubmed:
                    selected_sources.append(('pubmed', self.pubmed, 30.0))
            
            # 为选定的数据源分配配额
            if selected_sources:
                # 优化配额分配：单一数据源获得全部配额，多数据源合理分配
                if len(selected_sources) == 1:
                    per_source_limit = max_results  # 单一数据源获得全部配额
                    logger.info(f"📊 单一指定数据源: 分配{per_source_limit}篇全部配额")
                else:
                    per_source_limit = max(5, int(max_results // len(selected_sources)))
                    logger.info(f"📊 多数据源配额分配: {len(selected_sources)}个数据源，每源{per_source_limit}篇")
                
                for source_name, source_api, source_timeout in selected_sources:
                    sources_to_search.append((source_name, source_api, source_timeout, per_source_limit))
        else:
            # 使用默认的所有可用数据源
            logger.info("🌐 使用所有可用数据源")
            
            # 稳定数据源（优先级高）
            if self.semantic_scholar:
                sources_to_search.append(('semantic_scholar', self.semantic_scholar, 30.0, stable_per_source))
            if self.arxiv:
                sources_to_search.append(('arxiv', self.arxiv, 30.0, stable_per_source))
            if self.crossref:
                sources_to_search.append(('crossref', self.crossref, 30.0, stable_per_source))
            if self.pubmed:
                sources_to_search.append(('pubmed', self.pubmed, 30.0, stable_per_source))
                
            # ScholarDock（主力搜索源，优先级高）
            if self.scholarly:
                sources_to_search.insert(0, ('scholar_dock', self.scholarly, 150.0, scholar_limit))  # 增加超时到150秒
        
        for source_name, source_api, source_timeout, source_limit in sources_to_search:
            source_names.append(source_name)
            # 使用对应的统一布尔查询
            source_query = unified_queries.get(source_name, query)
            logger.debug(f"{source_name}使用查询: {source_query}")
            
            task = asyncio.create_task(
                asyncio.wait_for(source_api.search(source_query, source_limit), timeout=source_timeout)
            )
            tasks.append(task)
        
        # 执行搜索
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        all_papers = []
        captcha_errors = []
        
        for i, result in enumerate(results):
            source_name = source_names[i] if i < len(source_names) else f"source_{i}"
            
            if isinstance(result, Exception):
                error_str = str(result).lower()
                # 精准的错误检测，只针对真正的访问限制
                is_access_limited = any(keyword in error_str for keyword in [
                    'captcha', 'blocked', 'rate limit', '429', 'too many requests', 'unusual traffic'
                ])
                # 排除正常的网络错误
                is_network_error = any(keyword in error_str for keyword in [
                    'timeout', 'connection', 'ssl', 'handshake'
                ])
                is_access_limited = is_access_limited and not is_network_error
                
                if is_access_limited:
                    captcha_errors.append(source_name)
                    if source_name == 'scholar_dock':
                        logger.warning(f"⚠️ 主力搜索源 ScholarDock 访问受限，准备启用镜像搜索: {result}")
                    else:
                        logger.warning(f"⚠️ 搜索源 {source_name} 访问受限: {result}")
                else:
                    logger.error(f"❌ 搜索源 {source_name} 出错: {result}")
                continue
            elif isinstance(result, list):
                all_papers.extend(result)
                # 标记数据源的成功
                if source_name == 'scholar_dock':
                    logger.info(f"✅ 主力搜索源 {source_name} 返回 {len(result)} 篇论文")
                elif source_name in ['semantic_scholar', 'arxiv', 'crossref', 'pubmed']:
                    logger.info(f"✅ 辅助数据源 {source_name} 返回 {len(result)} 篇论文")
                else:
                    logger.info(f"✅ {source_name} 返回 {len(result)} 篇论文")
        
        # 统计数据源成功情况和实际获取的论文数量
        stable_success_count = len([name for name in source_names 
                                  if name != 'scholar_dock' and name not in captcha_errors])
        scholar_success = 'scholar_dock' not in captcha_errors if has_scholar else False
        
        # 检查主力源是否失败且获得的论文数量不足
        scholar_dock_papers = sum(len(result) for i, result in enumerate(results) 
                            if isinstance(result, list) and i < len(source_names) 
                            and source_names[i] == 'scholar_dock')
        
        need_compensation = False
        if 'scholar_dock' in captcha_errors or (scholar_success and scholar_dock_papers < scholar_limit * 0.3):
            # 主力源失败或获得的论文数量严重不足（少于预期的30%）
            need_compensation = True
            missing_quota = scholar_limit - scholar_dock_papers
            
            logger.warning(f"🔄 主力搜索源未达预期：获得{scholar_dock_papers}篇，预期{scholar_limit}篇，缺口{missing_quota}篇")
            
            # 优先尝试镜像搜索来补偿ScholarDock的缺失
            if 'scholar_dock' in captcha_errors and self.scholar_mirror and missing_quota > 0:
                logger.info(f"🔍 启动镜像搜索来补偿Google Scholar限制，尝试获取{missing_quota}篇论文")
                try:
                    # 镜像搜索也使用统一的布尔查询
                    mirror_query = unified_queries.get('scholar_dock', query)
                    mirror_papers = await asyncio.wait_for(
                        self.scholar_mirror.search(mirror_query, missing_quota), 
                        timeout=60.0
                    )
                    if mirror_papers:
                        all_papers.extend(mirror_papers)
                        logger.info(f"✅ 镜像搜索成功，额外获得 {len(mirror_papers)} 篇论文")
                        missing_quota = max(0, missing_quota - len(mirror_papers))
                    else:
                        logger.warning("⚠️ 镜像搜索未获得结果")
                except Exception as e:
                    logger.warning(f"⚠️ 镜像搜索失败: {e}")
            
            if stable_success_count > 0 and missing_quota > 0:
                # 启动补偿搜索：将缺失的配额分配给可用的辅助源
                logger.info(f"🚀 启动补偿搜索：将{missing_quota}篇配额分配给{stable_success_count}个可用数据源")
                
                compensation_per_source = max(5, missing_quota // stable_success_count)
                compensation_tasks = []
                compensation_source_names = []
                
                # 为成功的辅助数据源分配额外配额
                for source_name, source_api, source_timeout, original_limit in sources_to_search:
                    if source_name != 'scholar_dock' and source_name not in captcha_errors:
                        # 检查该源是否已经达到或接近其原始配额
                        source_papers = sum(len(result) for i, result in enumerate(results) 
                                          if isinstance(result, list) and i < len(source_names) 
                                          and source_names[i] == source_name)
                        
                        if source_papers < original_limit * 1.5:  # 如果没有明显超额，则进行补偿搜索
                            compensation_source_names.append(source_name)
                            # 补偿搜索也使用统一的布尔查询
                            source_query = unified_queries.get(source_name, query)
                            task = asyncio.create_task(
                                asyncio.wait_for(
                                    source_api.search(source_query, compensation_per_source), 
                                    timeout=source_timeout
                                )
                            )
                            compensation_tasks.append(task)
                            logger.debug(f"📈 {source_name}补偿搜索：额外{compensation_per_source}篇")
                
                # 执行补偿搜索
                if compensation_tasks:
                    try:
                        compensation_results = await asyncio.gather(*compensation_tasks, return_exceptions=True)
                        
                        compensation_papers = 0
                        for i, comp_result in enumerate(compensation_results):
                            if isinstance(comp_result, list) and comp_result:
                                all_papers.extend(comp_result)
                                compensation_papers += len(comp_result)
                                source_name = compensation_source_names[i] if i < len(compensation_source_names) else f"补偿源{i}"
                                logger.info(f"✅ 补偿搜索-{source_name}：额外获得{len(comp_result)}篇论文")
                        
                        if compensation_papers > 0:
                            logger.info(f"🎯 补偿搜索成功：总计获得{compensation_papers}篇额外论文")
                        else:
                            logger.info("📍 补偿搜索未获得额外论文，可能是配额已饱和")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ 补偿搜索失败: {e}")
        
        if captcha_errors:
            if 'scholar_dock' in captcha_errors and stable_success_count > 0:
                status = "已启动补偿搜索" if need_compensation else "使用辅助数据源"
                logger.warning(f"⚠️ 主力搜索源 ScholarDock 访问受限，{status}({stable_success_count}个)")
            elif 'scholar_dock' in captcha_errors and stable_success_count == 0:
                logger.warning(f"🚫 主力搜索源和辅助源均访问受限: {', '.join(captcha_errors)}")
                logger.info("💡 建议: 稍后重试或使用不同关键词")
            elif stable_success_count == 0:
                logger.warning(f"🚫 所有数据源访问受限: {', '.join(captcha_errors)}")
                logger.info("💡 建议: 稍后重试或使用不同关键词")
            else:
                logger.info(f"⚠️ 部分数据源受限: {', '.join(captcha_errors)}，但系统正常运行")
        
        # 去重和排序
        deduplicated_papers = self._deduplicate_papers(all_papers)
        
        # 年份筛选
        if year_from is not None or year_to is not None:
            filtered_papers = self._filter_papers_by_year(deduplicated_papers, year_from, year_to)
        else:
            filtered_papers = deduplicated_papers
        
        # 排序并限制数量
        ranked_papers = self._rank_papers(filtered_papers, query)
        traditional_results = ranked_papers[:max_results]
        
        final_results = traditional_results
        
        # 🔄 动态降级策略：如果结果不足，尝试exact_terms补充搜索
        if len(final_results) < max_results and analysis and analysis.get("hierarchical_keywords"):
            logger.warning(f"⚠️ 搜索结果不足({len(final_results)}/{max_results})，启动exact_terms补充搜索")
            
            # 使用降级查询进行补充搜索
            fallback_results = await self._perform_fallback_search(
                query, analysis, max_results - len(final_results), year_from, year_to, sources
            )
            
            if fallback_results:
                # 合并结果并去重
                combined_papers = final_results + fallback_results
                combined_deduplicated = self._deduplicate_papers(combined_papers)
                
                # 重新排序并限制数量
                final_results = self._rank_papers(combined_deduplicated, query)[:max_results]
                logger.info(f"✅ 补充搜索完成，最终获得 {len(final_results)} 篇论文")
        
        logger.info(f"搜索完成: 原始 {len(all_papers)} 篇 → 去重 {len(deduplicated_papers)} 篇 → 最终 {len(final_results)} 篇")
        return final_results
    
    def _deduplicate_papers(self, papers: List[Paper]) -> List[Paper]:
        """简化的去重逻辑"""
        seen_titles = set()
        seen_dois = set()
        unique_papers = []
        
        # 优化排序：稳定数据源优先，引用数次之
        papers_sorted = sorted(papers, key=lambda p: (
            -(p.citations or 0),
            p.doi is not None,
            p.source == 'scholar_dock',  # ScholarDock主力优先
            p.source in ['semantic_scholar', 'arxiv', 'crossref', 'pubmed'],  # 辅助数据源次之
        ), reverse=True)
        
        for paper in papers_sorted:
            # 数据质量过滤：只保留有效标题的论文
            if not paper.title or not paper.title.strip():
                continue
            
            # DOI去重
            if paper.doi and paper.doi.strip():
                if paper.doi in seen_dois:
                    continue
                seen_dois.add(paper.doi)
            
            # 标题去重
            normalized_title = self._normalize_title(paper.title)
            if normalized_title in seen_titles:
                continue
            
            seen_titles.add(normalized_title)
            unique_papers.append(paper)
        
        return unique_papers
    
    def _normalize_title(self, title: str) -> str:
        """标准化标题"""
        if not title:
            return ""
        
        import re
        normalized = title.lower().strip()
        normalized = re.sub(r'[:\-–—\.\s]+', ' ', normalized)
        return normalized.strip()
    
    def _filter_papers_by_year(self, papers: List[Paper], year_from: Optional[int], year_to: Optional[int]) -> List[Paper]:
        """按年份筛选论文"""
        if year_from is None and year_to is None:
            return papers
        
        filtered_papers = []
        for paper in papers:
            if paper.year is None:
                continue
            
            if year_from is not None and paper.year < year_from:
                continue
            if year_to is not None and paper.year > year_to:
                continue
            
            filtered_papers.append(paper)
        
        return filtered_papers
    
    async def _perform_fallback_search(
        self, 
        original_query: str, 
        analysis: Dict, 
        needed_count: int,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        sources: Optional[List[str]] = None
    ) -> List[Paper]:
        """执行降级补充搜索，只使用exact_terms"""
        try:
            logger.info(f"🔄 开始exact_terms补充搜索，需要{needed_count}篇论文")
            
            # 构建降级查询
            fallback_unified_queries = self._build_unified_boolean_query(
                original_query, analysis, use_fallback=True
            )
            
            # 选择最有效的数据源进行补充搜索（优先选择稳定的源）
            fallback_sources = []
            if not sources or 'semantic_scholar' in sources:
                if self.semantic_scholar:
                    fallback_sources.append(('semantic_scholar', self.semantic_scholar, 30.0))
            if not sources or 'arxiv' in sources:
                if self.arxiv:
                    fallback_sources.append(('arxiv', self.arxiv, 30.0))
            if not sources or 'scholar_dock' in sources:
                if self.scholarly:
                    fallback_sources.append(('scholar_dock', self.scholarly, 60.0))
            
            if not fallback_sources:
                logger.warning("⚠️ 没有可用的数据源进行补充搜索")
                return []
            
            # 平分搜索配额
            per_source_limit = max(1, needed_count // len(fallback_sources))
            
            # 并行执行补充搜索
            fallback_tasks = []
            source_names = []
            
            for source_name, source_api, timeout in fallback_sources:
                source_names.append(source_name)
                fallback_query = fallback_unified_queries.get(source_name, original_query)
                
                logger.debug(f"🔍 {source_name}补充搜索: {fallback_query}")
                task = asyncio.create_task(
                    asyncio.wait_for(source_api.search(fallback_query, per_source_limit), timeout=timeout)
                )
                fallback_tasks.append(task)
            
            # 执行并收集结果
            fallback_results = await asyncio.gather(*fallback_tasks, return_exceptions=True)
            
            all_fallback_papers = []
            for i, result in enumerate(fallback_results):
                source_name = source_names[i] if i < len(source_names) else f"fallback_source_{i}"
                
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ 补充搜索 {source_name} 失败: {result}")
                    continue
                elif isinstance(result, list):
                    all_fallback_papers.extend(result)
                    logger.info(f"✅ 补充搜索 {source_name} 获得 {len(result)} 篇论文")
            
            # 年份筛选
            if year_from is not None or year_to is not None:
                filtered_fallback = self._filter_papers_by_year(all_fallback_papers, year_from, year_to)
            else:
                filtered_fallback = all_fallback_papers
            
            logger.info(f"📊 补充搜索共获得 {len(filtered_fallback)} 篇有效论文")
            return filtered_fallback[:needed_count]  # 限制数量
            
        except Exception as e:
            logger.error(f"❌ 补充搜索失败: {e}")
            return []
    
    def _rank_papers(self, papers: List[Paper], query: str) -> List[Paper]:
        """简化的相关性排序"""
        query_terms = set(query.lower().split())
        
        for paper in papers:
            score = 0.0
            
            # 标题匹配
            title_terms = set(paper.title.lower().split())
            title_overlap = len(query_terms.intersection(title_terms))
            score += title_overlap * 2.0
            
            # 摘要匹配
            if paper.abstract:
                abstract_terms = set(paper.abstract.lower().split())
                abstract_overlap = len(query_terms.intersection(abstract_terms))
                score += abstract_overlap * 0.5
            
            # 引用数加权
            if paper.citations:
                score += min(paper.citations / 100.0, 2.0)
            
            # 年份加权
            if paper.year:
                current_year = 2024
                year_bonus = max(0, (paper.year - (current_year - 10)) / 10.0)
                score += year_bonus
            
            paper.relevance_score = score
        
        return sorted(papers, key=lambda p: p.relevance_score, reverse=True)
    
    async def close(self):
        """关闭所有连接"""
        coros = [self.arxiv.close()]
        if self.scholarly:
            coros.append(self.scholarly.close())
        if self.scholar_mirror:
            coros.append(self.scholar_mirror.close())
        if self.semantic_scholar:
            coros.append(self.semantic_scholar.close())
        if self.crossref:
            coros.append(self.crossref.close())
        if self.pubmed:
            coros.append(self.pubmed.close())
        
            
        await asyncio.gather(*coros)