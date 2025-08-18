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

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取配置 - 只启用指定的三个数据源
SEMANTIC_SCHOLAR_ENABLED = os.getenv("SEMANTIC_SCHOLAR_ENABLED", "true").lower() == "true"
# 启用ScholarPy（自定义的Google Scholar访问实现）
SCHOLAR_PY_ENABLED = os.getenv("SCHOLAR_PY_ENABLED", "false").lower() == "true"  
# 暂时禁用其他数据源
CROSSREF_ENABLED = os.getenv("CROSSREF_ENABLED", "false").lower() == "true"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
PUBMED_ENABLED = False  # 暂时禁用

# 兼容性支持：SCHOLARLY_ENABLED 映射到 SCHOLAR_PY_ENABLED
if os.getenv("SCHOLARLY_ENABLED"):
    SCHOLAR_PY_ENABLED = os.getenv("SCHOLARLY_ENABLED", "true").lower() == "true"

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
    source: str
    relevance_score: float = 0.0
    pmid: Optional[str] = None
    keywords: Optional[List[str]] = None

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
                
                paper = Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=paper_data.get('year'),
                    journal=journal,
                    url=paper_data.get('url', ''),
                    doi=doi,
                    citations=paper_data.get('citationCount', 0),
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
        self.base_url = "http://export.arxiv.org/api/query"
        self.session = None
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索arXiv预印本"""
        try:
            session = await self._get_session()
            
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
                    
                    # 提取年份
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
                        citations=0,
                        source='arxiv'
                    )
                    papers.append(paper)
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            logger.error(f"解析arXiv XML错误: {e}")
            
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
                    
                    # 提取年份
                    import re
                    year_match = re.search(r'\b(19|20)\d{2}\b', author_text)
                    if year_match:
                        year = int(year_match.group())
            
            # 摘要/片段
            abstract = ''
            snippet_element = result_div.find('div', class_='gs_rs')
            if snippet_element:
                abstract = snippet_element.get_text(strip=True)
            
            # 引用数
            citations = 0
            citation_element = result_div.find('a', string=lambda text: text and 'Cited by' in text)
            if citation_element:
                import re
                citation_match = re.search(r'Cited by (\d+)', citation_element.get_text())
                if citation_match:
                    citations = int(citation_match.group(1))
            
            return Paper(
                title=title,
                authors=authors,
                abstract=abstract,
                year=year,
                journal=journal,
                url=url,
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

class ScholarlyAPI:
    """Scholarly库客户端 - 直接访问学术文献数据库，带反CAPTCHA机制"""
    
    def __init__(self):
        self.session = None
        self.is_configured = False
        self.last_request_time = 0
        self.min_delay = 2.0  # 最小延迟时间
        self.captcha_failures = 0  # CAPTCHA失败计数
        self.max_captcha_failures = 3  # 最大允许CAPTCHA失败次数
        self.temporary_disabled = False  # 临时禁用标志
        self.disable_until = 0  # 禁用到什么时候
        
    def _configure_scholarly(self):
        """配置scholarly库，设置代理和反CAPTCHA机制"""
        if self.is_configured:
            return
            
        try:
            from scholarly import scholarly
            import random
            
            # 配置更保守的请求参数
            scholarly.set_timeout(10)
            
            # 使用随机用户代理
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ]
            
            # 尝试配置用户代理（如果scholarly支持）
            try:
                scholarly.set_retries(3)
                scholarly.set_timeout(15)
            except:
                pass
                
            self.is_configured = True
            logger.info("✅ scholarly库配置完成，启用智能访问机制")
            
        except Exception as e:
            logger.warning(f"scholarly库配置失败: {e}")
        
    async def _rate_limit_delay(self):
        """智能延迟，避免触发CAPTCHA"""
        import time
        import random
        
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # 如果是首次请求或距离上次请求很久，使用更长的延迟
        if self.last_request_time == 0 or time_since_last > 300:  # 5分钟
            delay = random.uniform(3.0, 6.0)  # 首次请求延迟3-6秒
            logger.info(f"🕒 首次/长时间间隔延迟: {delay:.2f}秒")
        elif time_since_last < self.min_delay:
            delay = self.min_delay - time_since_last + random.uniform(1.0, 3.0)  # 增加随机延迟
            logger.debug(f"🕒 智能延迟: {delay:.2f}秒")
        else:
            delay = random.uniform(0.5, 1.5)  # 基础随机延迟
            logger.debug(f"🕒 基础延迟: {delay:.2f}秒")
            
        await asyncio.sleep(delay)
        self.last_request_time = time.time()
        
    def _is_temporarily_disabled(self) -> bool:
        """检查是否因CAPTCHA而临时禁用"""
        import time
        if self.temporary_disabled and time.time() < self.disable_until:
            return True
        elif self.temporary_disabled and time.time() >= self.disable_until:
            # 禁用期已过，重置状态
            self.temporary_disabled = False
            self.captcha_failures = 0
            logger.info("🔓 Google Scholar临时禁用期已过，重新启用")
            return False
        return False
    
    def _handle_captcha_failure(self):
        """处理CAPTCHA失败"""
        import time
        self.captcha_failures += 1
        logger.warning(f"⚠️ scholarly库访问限制计数: {self.captcha_failures}/{self.max_captcha_failures}")
        
        if self.captcha_failures >= self.max_captcha_failures:
            # 临时禁用30分钟
            self.temporary_disabled = True
            self.disable_until = time.time() + (30 * 60)  # 30分钟
            logger.warning(f"🚫 scholarly库因连续访问限制已临时禁用30分钟")
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """使用scholarly库搜索学术文献，带智能访问保护"""
        # 检查是否临时禁用
        if self._is_temporarily_disabled():
            logger.info("⏸️ scholarly库当前临时禁用中，跳过搜索")
            return []
            
        try:
            try:
                from scholarly import scholarly
            except ImportError:
                logger.error("scholarly库未安装，请运行: pip install scholarly")
                return []
            
            # 配置scholarly
            self._configure_scholarly()
            
            papers = []
            retry_count = 0
            max_retries = 2  # 减少重试次数
            
            while retry_count < max_retries:
                try:
                    # 智能延迟
                    await self._rate_limit_delay()
                    
                    logger.info(f"🔍 开始scholarly库搜索: {query} (重试次数: {retry_count})")
                    search_generator = scholarly.search_pubs(query)
                    count = 0
                    
                    for pub in search_generator:
                        try:
                            if count >= limit:
                                break
                                
                            # 每个结果之间也要延迟
                            if count > 0:
                                await asyncio.sleep(random.uniform(1.0, 2.0))
                                
                            bib = pub.get('bib', {})
                            title = bib.get('title', '').strip()
                            
                            # 跳过没有标题或标题过短的论文
                            if not title or len(title) < 5:
                                continue
                            
                            # 获取作者
                            authors_raw = bib.get('author', [])
                            if isinstance(authors_raw, list):
                                authors = [str(author).strip() for author in authors_raw if str(author).strip()]
                            else:
                                authors = [str(authors_raw).strip()] if authors_raw else []
                            
                            # 作者信息缺失时保持空列表
                            
                            # 获取年份
                            year = bib.get('pub_year')
                            if year:
                                try:
                                    year = int(year)
                                except:
                                    year = None
                            
                            # 获取摘要
                            abstract = bib.get('abstract', '').strip()
                            if len(abstract) > 500:
                                abstract = abstract[:500] + "..."
                            
                            # 获取其他信息
                            journal = bib.get('venue', '') or bib.get('journal', '')
                            url = pub.get('pub_url', '') or pub.get('eprint_url', '') or ''
                            citations = pub.get('num_citations', 0)
                            try:
                                citations = int(citations) if citations else 0
                            except:
                                citations = 0
                            
                            paper = Paper(
                                title=title,
                                authors=authors,
                                abstract=abstract,
                                year=year,
                                journal=journal,
                                url=url,
                                doi=None,
                                citations=citations,
                                source="scholarly",
                                relevance_score=1.0 - (count * 0.01)
                            )
                            
                            papers.append(paper)
                            count += 1
                            
                        except Exception as e:
                            logger.debug(f"处理单个结果失败: {e}")
                            continue
                    
                    # 如果成功获取到结果，退出重试循环
                    if papers:
                        logger.info(f"✅ scholarly库搜索成功，获得 {len(papers)} 篇论文")
                        break
                        
                except Exception as e:
                    error_str = str(e).lower()
                    # 扩展CAPTCHA和限流检测
                    is_rate_limited = any(keyword in error_str for keyword in [
                        'captcha', 'blocked', 'rate limit', '429', 'too many requests',
                        'cannot fetch', 'forbidden', 'attribute', 'scholar'
                    ])
                    
                    if is_rate_limited:
                        # 处理限流/CAPTCHA失败
                        self._handle_captcha_failure()
                        
                        # 如果已经被临时禁用，直接跳出
                        if self.temporary_disabled:
                            logger.warning("🚫 scholarly库已被临时禁用，停止重试")
                            break
                            
                        retry_count += 1
                        # 增加等待时间，使用指数退避
                        base_wait = min(120, (retry_count * 30))  # 最大等待2分钟
                        wait_time = base_wait + random.uniform(10, 30)
                        logger.warning(f"⚠️ 遇到访问限制，等待 {wait_time:.1f}秒后重试 (第{retry_count}次)")
                        await asyncio.sleep(wait_time)
                        
                        # 重新配置scholarly
                        self.is_configured = False
                        self._configure_scholarly()
                    else:
                        logger.error(f"scholarly库搜索失败: {e}")
                        break
            
            return papers
            
        except Exception as e:
            logger.error(f"scholarly库搜索错误: {e}")
            return []
    
    async def close(self):
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
        # 初始化数据源
        self.arxiv = ArxivAPI()
        # 优先使用scholarly库，ScholarPyAPI作为备选
        self.scholarly = ScholarlyAPI() if not SCHOLAR_PY_ENABLED else ScholarPyAPI()
        self.semantic_scholar = SemanticScholarAPI() if SEMANTIC_SCHOLAR_ENABLED else None
        self.crossref = CrossrefAPI() if CROSSREF_ENABLED else None
        self.pubmed = PubMedAPI() if PUBMED_ENABLED else None
        
        # 显示启用的数据源
        enabled_sources = []
        if self.arxiv:
            enabled_sources.append("Arxiv")
        if self.scholarly:
            if SCHOLAR_PY_ENABLED:
                enabled_sources.append("Scholar.py (自定义)")
            else:
                enabled_sources.append("Scholarly库")
        if self.semantic_scholar:
            enabled_sources.append("Semantic Scholar") 
        if self.crossref:
            enabled_sources.append("Crossref")
        if self.pubmed:
            enabled_sources.append("PubMed")
            
        logger.info(f"多源搜索引擎初始化完成，启用数据源: {', '.join(enabled_sources)}")
        
        if not CROSSREF_ENABLED:
            logger.info("📍 Crossref数据源已暂时禁用")
        if not PUBMED_ENABLED:
            logger.info("📍 PubMed数据源已暂时禁用")
    
    async def search_parallel(self, query: str, max_results: int = 50) -> List[Paper]:
        """并行搜索多个数据源"""
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
        
        # 动态计算每个源的搜索数量，根据启用的源数量调整
        active_sources = sum(1 for _, api in [
            ('arxiv', self.arxiv),
            ('scholar_py', self.scholarly),
            ('semantic_scholar', self.semantic_scholar),
            ('crossref', self.crossref),
            ('pubmed', self.pubmed)
        ] if api is not None)
        
        per_source_limit = max(15, max_results // max(1, active_sources))
        logger.info(f"启用 {active_sources} 个数据源，每源搜索 {per_source_limit} 篇论文")
        
        tasks = []
        source_names = []
        timeout = 30.0
        
        # 创建搜索任务，给ScholarPy更长的超时时间
        sources_to_search = [
            ('arxiv', self.arxiv, 30.0),
            ('scholar_py', self.scholarly, 120.0),  # ScholarPy需要更长超时时间
            ('semantic_scholar', self.semantic_scholar, 30.0),
            ('crossref', self.crossref, 30.0),
            ('pubmed', self.pubmed, 30.0)
        ]
        
        for source_name, source_api, source_timeout in sources_to_search:
            if source_api is not None:
                source_names.append(source_name)
                task = asyncio.create_task(
                    asyncio.wait_for(source_api.search(query, per_source_limit), timeout=source_timeout)
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
                if 'captcha' in error_str or 'blocked' in error_str:
                    captcha_errors.append(source_name)
                    logger.warning(f"⚠️ 搜索源 {source_name} 遇到CAPTCHA限制: {result}")
                else:
                    logger.error(f"❌ 搜索源 {source_name} 出错: {result}")
                continue
            elif isinstance(result, list):
                all_papers.extend(result)
                logger.info(f"✅ {source_name} 返回 {len(result)} 篇论文")
        
        # 如果遇到CAPTCHA错误，记录并提供提示
        if captcha_errors:
            logger.warning(f"🚫 以下搜索源遇到访问限制: {', '.join(captcha_errors)}")
            logger.info("💡 建议: 稍后重试或使用其他关键词进行搜索")
        
        # 去重和排序
        deduplicated_papers = self._deduplicate_papers(all_papers)
        
        # 年份筛选
        if year_from is not None or year_to is not None:
            filtered_papers = self._filter_papers_by_year(deduplicated_papers, year_from, year_to)
        else:
            filtered_papers = deduplicated_papers
        
        # 排序并限制数量
        ranked_papers = self._rank_papers(filtered_papers, query)
        final_results = ranked_papers[:max_results]
        
        logger.info(f"搜索完成: 原始 {len(all_papers)} 篇 → 去重 {len(deduplicated_papers)} 篇 → 最终 {len(final_results)} 篇")
        return final_results
    
    def _deduplicate_papers(self, papers: List[Paper]) -> List[Paper]:
        """简化的去重逻辑"""
        seen_titles = set()
        seen_dois = set()
        unique_papers = []
        
        # 按引用数和来源质量排序
        papers_sorted = sorted(papers, key=lambda p: (
            -(p.citations or 0),
            p.doi is not None,
            p.source == 'semantic_scholar'
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
        if self.semantic_scholar:
            coros.append(self.semantic_scholar.close())
        if self.crossref:
            coros.append(self.crossref.close())
        if self.pubmed:
            coros.append(self.pubmed.close())
        await asyncio.gather(*coros)