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
from scholar_dock_spider import ScholarDockSpider, ScholarDockPaper

# 加载环境变量
load_dotenv()


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取配置 - 只启用三个核心数据源
# ScholarDock高效爬虫（推荐使用，默认启用）
SCHOLAR_DOCK_ENABLED = os.getenv("SCHOLAR_DOCK_ENABLED", "true").lower() == "true"
# 新增：控制是否启用Google Scholar（默认启用作为主力搜索源）
GOOGLE_SCHOLAR_ENABLED = os.getenv("GOOGLE_SCHOLAR_ENABLED", "true").lower() == "true"
# 启用arXiv作为辅助数据源
ARXIV_ENABLED = os.getenv("ARXIV_ENABLED", "true").lower() == "true"
# 启用Crossref作为辅助数据源
CROSSREF_ENABLED = os.getenv("CROSSREF_ENABLED", "true").lower() == "true"

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

class ArxivAPI:
    """arXiv API客户端"""
    
    def __init__(self):
        self.base_url = "https://export.arxiv.org/api/query"
        self.session = None
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            # 🔧 配置代理支持
            http_proxy = os.getenv('HTTP_PROXY')
            https_proxy = os.getenv('HTTPS_PROXY')
            if http_proxy or https_proxy:
                proxy_url = https_proxy or http_proxy
                logger.info(f"🌐 arXiv使用代理: {proxy_url}")
                connector = aiohttp.TCPConnector()
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    trust_env=True
                )
            else:
                self.session = aiohttp.ClientSession()
        return self.session
        
    async def search(self, query: str, limit: int = 20, start_year: Optional[int] = None, end_year: Optional[int] = None) -> List[Paper]:
        """搜索arXiv预印本，支持年限筛选"""
        try:
            logger.debug(f"🔍 arXiv搜索开始: {query}")
            session = await self._get_session()
            
            # 构建搜索查询，包含年限筛选
            search_query = query
            if start_year is not None or end_year is not None:
                # 使用arXiv的submittedDate参数进行年限筛选
                # 格式: submittedDate:[YYYYMMDDHHMISS TO YYYYMMDDHHMISS]
                from datetime import datetime
                
                if start_year is not None:
                    start_date = f"{start_year}0101000000"
                else:
                    start_date = "19910101000000"  # arXiv启动年份
                    
                if end_year is not None:
                    end_date = f"{end_year}1231235959"
                else:
                    current_year = datetime.now().year
                    end_date = f"{current_year}1231235959"
                
                # 将年限筛选添加到查询中
                date_filter = f" AND submittedDate:[{start_date} TO {end_date}]"
                search_query = query + date_filter
                
                logger.info(f"🗓️ arXiv启用年限筛选: {start_year}-{end_year}")
                logger.debug(f"📋 arXiv年限筛选查询: {search_query}")
            
            # 优化查询格式：直接使用search_query
            params = {
                'search_query': search_query,
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
            # 🔧 修复：在网络错误时关闭并重置session，避免连接泄漏
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
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
    
    async def search(self, query: str, limit: int = 20, start_year: Optional[int] = None, end_year: Optional[int] = None) -> List[Paper]:
        """使用ScholarDock技术搜索Google Scholar，支持年限筛选"""
        try:
            if start_year is not None or end_year is not None:
                logger.info(f"🔍 ScholarDock开始搜索: {query} (年限: {start_year}-{end_year})")
            else:
                logger.info(f"🔍 ScholarDock开始搜索: {query}")
            
            # 创建并使用ScholarDock爬虫，传递年限参数
            async with ScholarDockSpider() as spider:
                scholar_papers = await spider.search(query, limit, start_year=start_year, end_year=end_year)
            
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
            # 🔧 基于crossrefapi库的标准请求头配置
            headers = {
                'User-Agent': 'Veritex-Academic-Search/3.0 (https://veritex.ai; mailto:support@veritex.ai)',
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            # 🔧 配置代理支持
            http_proxy = os.getenv('HTTP_PROXY')
            https_proxy = os.getenv('HTTPS_PROXY')
            if http_proxy or https_proxy:
                proxy_url = https_proxy or http_proxy
                logger.info(f"🌐 Crossref使用代理: {proxy_url}")
                connector = aiohttp.TCPConnector()
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    trust_env=True,
                    headers=headers
                )
            else:
                self.session = aiohttp.ClientSession(headers=headers)
            
            logger.debug("✅ Crossref API会话已创建，包含标准请求头")
        return self.session
        
    async def search(self, query: str, limit: int = 20, start_year: Optional[int] = None, end_year: Optional[int] = None) -> List[Paper]:
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
            
            # 🔧 修复：使用Crossref API实际支持的select字段
            params = {
                'query': query,
                'rows': limit,
                # 🎯 只使用Crossref API实际支持的字段（根据错误消息确认）
                'select': 'DOI,title,author,published,abstract,URL,is-referenced-by-count,publisher,container-title,subtitle,type,subject,license,ISSN,issued,created,indexed'
            }
            
            # 🔧 新增：添加年限筛选参数 - 使用Crossref API的from-pub-date和until-pub-date
            filters = []
            if start_year is not None:
                filters.append(f"from-pub-date:{start_year}")
                logger.info(f"🗓️ Crossref添加起始年份筛选: {start_year}")
            
            if end_year is not None:
                filters.append(f"until-pub-date:{end_year}")
                logger.info(f"🗓️ Crossref添加结束年份筛选: {end_year}")
            
            # 如果有筛选条件，添加filter参数
            if filters:
                params['filter'] = ','.join(filters)
                logger.info(f"🎯 Crossref API筛选参数: {params['filter']}")
            
            self._last_request = time.time()
            
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('message', {}).get('items', [])
                    return self._parse_papers(items)
                else:
                    logger.warning(f"⚠️ Crossref API返回状态码: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Crossref搜索出错: {e}")
            # 🔧 修复：在网络错误时关闭并重置session，避免连接泄漏
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
            return []
            
    def _parse_papers(self, items: List[Dict]) -> List[Paper]:
        """解析Crossref响应数据 - 增强元数据处理"""
        papers = []
        for item in items:
            try:
                # 标题处理 - 支持多种标题格式
                title_list = item.get('title', [])
                subtitle_list = item.get('subtitle', [])
                
                title = (title_list[0] if title_list else "").strip()
                
                # 如果标题为空，尝试使用subtitle
                if not title and subtitle_list:
                    title = subtitle_list[0].strip()
                
                # 跳过没有标题的论文
                if not title:
                    continue
                
                # 合并主标题和副标题
                if subtitle_list and title and subtitle_list[0].strip():
                    subtitle = subtitle_list[0].strip()
                    if subtitle not in title:  # 避免重复
                        title = f"{title}: {subtitle}"
                
                # 作者处理 - 更全面的作者信息提取
                authors = []
                for author in item.get('author', []):
                    if 'given' in author and 'family' in author:
                        # 完整姓名
                        full_name = f"{author['given']} {author['family']}"
                        authors.append(full_name)
                    elif 'family' in author:
                        # 只有姓氏
                        authors.append(author['family'])
                    elif 'name' in author:
                        # 备用名称字段
                        authors.append(author['name'])
                
                # 🔧 改进年份处理 - 优先级：published > published-print > published-online > created
                year = None
                # 按优先级尝试获取年份信息
                date_sources = [
                    item.get('published'),
                    item.get('published-print'), 
                    item.get('published-online'), 
                    item.get('created')
                ]
                
                for date_source in date_sources:
                    if date_source and 'date-parts' in date_source:
                        date_parts = date_source['date-parts']
                        if date_parts and len(date_parts) > 0 and len(date_parts[0]) > 0:
                            try:
                                year = int(date_parts[0][0])
                                # 年份合理性检查
                                from datetime import datetime
                                current_year = datetime.now().year
                                if 1900 <= year <= current_year + 2:
                                    break  # 找到有效年份，跳出循环
                                else:
                                    year = None  # 年份不合理，继续尝试下一个源
                            except (ValueError, IndexError, TypeError):
                                continue  # 解析失败，尝试下一个源
                
                # 🎯 基于crossrefapi库的多字段摘要获取策略
                abstract = ""
                abstract_source = ""
                
                # 策略1: 主要摘要字段
                raw_abstract = item.get('abstract')
                if raw_abstract and isinstance(raw_abstract, str) and raw_abstract.strip():
                    abstract = self._clean_html_abstract(raw_abstract.strip())
                    abstract_source = "abstract"
                    logger.debug(f"✅ 从abstract字段获取摘要: {len(abstract)}字符")
                
                # 策略2: 副标题字段（可能包含摘要信息）
                elif item.get('subtitle') and len(item['subtitle']) > 0:
                    subtitle_text = item['subtitle'][0] if isinstance(item['subtitle'], list) else str(item['subtitle'])
                    if len(subtitle_text.strip()) > 50:  # 只有足够长的副标题才考虑作为摘要
                        abstract = self._clean_html_abstract(subtitle_text.strip())
                        abstract_source = "subtitle"
                        logger.debug(f"✅ 从subtitle字段获取摘要: {len(abstract)}字符")
                
                # 策略3: 基于主题词生成描述性摘要（高质量降级）
                elif item.get('subject') and len(item['subject']) > 0:
                    subjects = item['subject'][:5]  # 最多使用5个主题词
                    work_type = item.get('type', '').replace('-', ' ').title()
                    if work_type and subjects:
                        abstract = f"This {work_type.lower()} covers research in: {', '.join(subjects)}."
                        abstract_source = "generated"
                        logger.debug(f"✅ 基于主题词生成描述: {len(abstract)}字符")
                
                # 记录摘要来源用于调试
                if abstract:
                    logger.debug(f"📄 摘要来源: {abstract_source}")
                else:
                    logger.debug(f"❌ 无可用摘要数据")
                    
                # 如果摘要过短，清空处理
                if abstract and len(abstract.strip()) < 20:
                    logger.debug(f"⚠️ 摘要过短({len(abstract)}字符)，清空处理")
                    abstract = ""
                
                # DOI和URL处理 - 改进URL生成逻辑
                doi = item.get('DOI', '').strip()
                url = item.get('URL', '').strip()
                
                # 如果没有URL但有DOI，生成DOI链接
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                
                # 引用数处理
                citations = item.get('is-referenced-by-count', 0)
                try:
                    citations = int(citations) if citations else 0
                except (ValueError, TypeError):
                    citations = 0
                
                # 🎯 基于crossrefapi库的扩展期刊信息处理
                journal = ''
                
                # 策略1: 优先使用container-title (期刊全名)
                if item.get('container-title') and len(item['container-title']) > 0:
                    journal = item['container-title'][0].strip()
                
                # 策略2: 如果没有，使用short-container-title (期刊简称)
                elif item.get('short-container-title') and len(item['short-container-title']) > 0:
                    journal = item['short-container-title'][0].strip()
                
                # 策略3: 最后使用publisher (出版商)
                elif item.get('publisher'):
                    journal = item['publisher'].strip()
                
                # 🎯 扩展元数据处理 - 基于实际可用字段
                # 许可证信息
                license_info = []
                if item.get('license'):
                    for license_item in item['license'][:2]:  # 最多2个许可证
                        if isinstance(license_item, dict) and license_item.get('URL'):
                            license_info.append(license_item['URL'])
                
                # 提取ISSN
                issn_list = item.get('ISSN', [])
                
                # 构建扩展的出版商信息
                publisher_full = item.get('publisher', '')
                
                # 构建描述信息（整合多种元数据）
                description_parts = []
                if license_info:
                    description_parts.append(f"License: {license_info[0]}")  # 只显示第一个许可证
                
                description = " | ".join(description_parts) if description_parts else ""
                
                # 创建增强的Paper对象
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
                    # 🎯 扩展字段映射（基于实际可用字段）
                    pmid=issn_list[0] if issn_list else None,
                    keywords=item.get('subject', [])[:5] if item.get('subject') else None,
                    # ScholarDock增强字段的利用
                    venue=journal.split(' (')[0] if ' (' in journal else journal,  # 提取纯期刊名
                    publisher=publisher_full,
                    description=description
                )
                papers.append(paper)
                
            except Exception as e:
                logger.debug(f"解析Crossref单篇论文失败: {e}")
                continue
                
        logger.info(f"📊 Crossref解析完成: {len(papers)}/{len(items)}篇论文成功解析")
        return papers
    
    def _clean_html_abstract(self, html_abstract: str) -> str:
        """清理HTML标签，转换摘要为纯文本格式"""
        try:
            import re
            
            # 如果不包含HTML标签，直接返回
            if '<' not in html_abstract:
                return html_abstract.strip()
            
            # HTML标签清理规则
            cleaned = html_abstract
            
            # 1. 保持段落结构：<p> 标签转换为双换行
            cleaned = re.sub(r'<p[^>]*>', '\n\n', cleaned)
            cleaned = re.sub(r'</p>', '', cleaned)
            
            # 2. 保持强调格式：<italic>、<em>、<i> 转换为斜体标记
            cleaned = re.sub(r'<(?:italic|em|i)[^>]*>(.*?)</(?:italic|em|i)>', r'*\1*', cleaned)
            
            # 3. 保持加粗格式：<strong>、<b> 转换为加粗标记
            cleaned = re.sub(r'<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>', r'**\1**', cleaned)
            
            # 4. 换行标签：<br> 转换为换行
            cleaned = re.sub(r'<br[^>]*/?>', '\n', cleaned)
            
            # 5. 列表处理：简单转换为文本列表
            cleaned = re.sub(r'<li[^>]*>', '\n• ', cleaned)
            cleaned = re.sub(r'</li>', '', cleaned)
            cleaned = re.sub(r'</?[uo]l[^>]*>', '', cleaned)
            
            # 6. 移除所有剩余的HTML标签
            cleaned = re.sub(r'<[^>]+>', '', cleaned)
            
            # 7. 清理HTML实体
            html_entities = {
                '&amp;': '&',
                '&lt;': '<',
                '&gt;': '>',
                '&quot;': '"',
                '&#39;': "'",
                '&nbsp;': ' ',
                '&mdash;': '—',
                '&ndash;': '–',
                '&hellip;': '…'
            }
            
            for entity, char in html_entities.items():
                cleaned = cleaned.replace(entity, char)
            
            # 8. 清理多余的空白字符
            cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)  # 多个换行合并为双换行
            cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # 多个空格合并为单个空格
            cleaned = cleaned.strip()
            
            # 9. 确保段落间有适当间距
            if '\n\n' in cleaned:
                paragraphs = [p.strip() for p in cleaned.split('\n\n') if p.strip()]
                cleaned = '\n\n'.join(paragraphs)
            
            logger.debug(f"🧹 HTML清理完成: {len(html_abstract)} → {len(cleaned)}字符")
            return cleaned
            
        except Exception as e:
            logger.warning(f"⚠️ HTML清理失败: {e}")
            # 降级处理：移除所有HTML标签
            import re
            fallback = re.sub(r'<[^>]+>', '', html_abstract)
            return fallback.strip()
        
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
            self.scholar_dock = ScholarDockAPI()
            logger.info("🚀 使用ScholarDock高效爬虫引擎")
        else:
            self.scholar_dock = None
            logger.info("🚫 Google Scholar已禁用，使用稳定数据源")
        
        self.crossref = CrossrefAPI() if CROSSREF_ENABLED else None
        
        # 显示启用的数据源
        enabled_sources = []
        disabled_sources = []
        
        if self.arxiv:
            enabled_sources.append("arXiv")
        else:
            disabled_sources.append("arXiv")
            
        if self.scholar_dock:
            enabled_sources.append("ScholarDock高效爬虫")
        else:
            disabled_sources.append("Google Scholar")
            
        if self.crossref:
            enabled_sources.append("Crossref")
        else:
            disabled_sources.append("Crossref")
            
        logger.info(f"✅ 多源搜索引擎初始化完成")
        logger.info(f"🟢 启用数据源 ({len(enabled_sources)}): {', '.join(enabled_sources)}")
        if disabled_sources:
            logger.info(f"🔴 禁用数据源 ({len(disabled_sources)}): {', '.join(disabled_sources)}")
    
    async def search_parallel(self, query: str, max_results: int = 20, analysis: Optional[Dict] = None, year_from: Optional[int] = None, year_to: Optional[int] = None) -> List[Paper]:
        """并行搜索多个数据源（支持统一布尔查询和年限筛选）"""
        return await self.search_parallel_with_filters(query, max_results, year_from=year_from, year_to=year_to, analysis=analysis)
    
    def _build_unified_boolean_query(self, query: str, analysis: Optional[Dict] = None, use_fallback: bool = False, use_chinese: bool = False) -> Dict[str, str]:
        """构建统一的4层权重映射布尔查询，适配不同搜索源，支持双语模式"""
        unified_queries = {}
        
        # 构建4层权重映射的布尔查询
        boolean_query = self._build_hierarchical_boolean_query(query, analysis, use_fallback, use_chinese)
        language_mode = "中文" if use_chinese else "英文"
        logger.info(f"构建4层权重布尔查询({language_mode}): {boolean_query}")
        
        # 为每个搜索源适配查询格式
        unified_queries['scholar_dock'] = boolean_query  # ScholarDock处理复杂查询
        unified_queries['arxiv'] = self._adapt_query_for_arxiv(boolean_query)
        unified_queries['crossref'] = self._adapt_query_for_crossref(boolean_query)
        
        return unified_queries
    
    def _build_hierarchical_boolean_query(self, query: str, analysis: Optional[Dict] = None, use_fallback: bool = False, use_chinese: bool = False) -> str:
        """构建将用于各源的布尔查询。

        新策略（按需）：
        - 若 analysis 中存在 optimized_boolean_query，则无条件优先返回该串（不区分中英文模式）。
        - 若无 optimized_boolean_query：
          - use_fallback=True 时仅用 exact_terms（按指定语言优先）
          - use_chinese=True 时按 4 层 (OR) + 层间 AND 组合
          - 否则回退到原始 query
        """
        try:
            # 1) 优先使用 LLM 返回的优化布尔查询（统一入口，不区分语言）
            if analysis and analysis.get("optimized_boolean_query"):
                boolean_query = analysis["optimized_boolean_query"]
                logger.info(f"🎯 使用LLM优化布尔查询: {boolean_query}")
                return boolean_query
            
            # 如果是降级搜索，只使用exact_terms
            if use_fallback and analysis and analysis.get("hierarchical_keywords"):
                exact_terms_data = analysis["hierarchical_keywords"].get("exact_terms", {})
                # 支持双语关键词选择
                if use_chinese and exact_terms_data.get("chinese"):
                    exact_terms = exact_terms_data["chinese"]
                elif exact_terms_data.get("english"):
                    exact_terms = exact_terms_data["english"]
                else:
                    exact_terms = exact_terms_data.get("terms", [])  # 兼容旧格式
                
                if exact_terms:
                    # 简单的精确术语查询
                    fallback_query = ' OR '.join([f'"{term}"' for term in exact_terms])
                    language_mode = "中文" if use_chinese else "英文"
                    logger.info(f"🔄 使用降级查询(exact_terms-{language_mode}): {fallback_query}")
                    return fallback_query
                else:
                    logger.warning("⚠️ 没有exact_terms可用于降级查询，使用原查询")
                    return query
            
            # 2) 若无 optimized_boolean_query 且中文模式：构建4层权重布尔查询
            if use_chinese and analysis and analysis.get("hierarchical_keywords"):
                hierarchical_keywords = analysis["hierarchical_keywords"]
                
                # 提取各层关键词，支持双语选择
                query_parts = []
                language_mode = "中文" if use_chinese else "英文"
                
                for category in ["exact_terms", "core_synonyms", "related_terms", "context_terms"]:
                    if category in hierarchical_keywords:
                        category_data = hierarchical_keywords[category]
                        
                        # 智能选择语言：优先使用指定语言，降级使用另一种语言
                        if use_chinese:
                            terms = category_data.get("chinese") or category_data.get("english") or category_data.get("terms", [])
                        else:
                            terms = category_data.get("english") or category_data.get("chinese") or category_data.get("terms", [])
                        
                        if terms:
                            part = '(' + ' OR '.join([f'"{term}"' for term in terms]) + ')'
                            query_parts.append(part)
                            logger.debug(f"📊 {category}({language_mode}): {len(terms)}个关键词")
                
                # 用AND连接各层
                if query_parts:
                    hierarchical_query = ' AND '.join(query_parts)
                    logger.info(f"✅ 构建4层权重布尔查询成功 ({language_mode}模式)")
                    return hierarchical_query
                else:
                    logger.warning("⚠️ 无法从层次关键词构建查询，使用原查询")
                    return query
            
            # 3) 没有分析结果或上述路径均不满足，使用原始查询
            else:
                logger.info(f"使用原始查询: {query}")
                return query
                
        except Exception as e:
            logger.error(f"❌ 构建层次布尔查询失败: {e}")
            return query
    
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
    
    async def search_chinese_papers(self, query: str, target_count: int = 20) -> List[Paper]:
        """专门的中文论文搜索方法，确保获取足够的中文论文"""
        logger.info(f"🈶 开始中文论文专项搜索: {query} (目标: {target_count}篇)")
        
        all_papers = []
        
        # 策略1: 使用ScholarDock的智能分批搜索避免CAPTCHA
        if self.scholar_dock:
            try:
                logger.info("🔍 策略1: ScholarDock智能分批搜索")
                all_papers = await self._intelligent_batch_search(query, target_count)
            except Exception as e:
                logger.warning(f"ScholarDock智能搜索失败: {e}")
        
        
        # 过滤和优先排序中文论文
        chinese_papers = []
        english_papers = []
        
        for paper in all_papers:
            if self._is_chinese_paper(paper):
                chinese_papers.append(paper)
            else:
                english_papers.append(paper)
        
        # 优先返回中文论文，不足时补充英文论文
        final_papers = chinese_papers + english_papers
        final_papers = final_papers[:target_count]
        
        chinese_count = len(chinese_papers[:target_count])
        logger.info(f"📊 中文搜索完成: 共{len(final_papers)}篇，中文论文{chinese_count}篇 ({chinese_count/len(final_papers)*100:.1f}%)")
        
        return final_papers
    
    async def _intelligent_batch_search(self, query: str, target_count: int) -> List[Paper]:
        """智能分批搜索策略，避免CAPTCHA限制"""
        all_papers = []
        search_variants = [
            query,  # 原始查询
            f"{query} 研究",  # 添加"研究"
            f"{query} 算法",  # 添加"算法"
            f"{query} 技术",  # 添加"技术"
            f"{query} 应用"   # 添加"应用"
        ]
        
        for i, variant_query in enumerate(search_variants):
            if len(all_papers) >= target_count:
                break
                
            try:
                logger.info(f"🔍 批次{i+1}: 搜索变体查询 '{variant_query}'")
                
                async with ScholarDockSpider() as spider:
                    # 每次搜索较少数量，减少CAPTCHA风险
                    batch_papers = await spider.search(variant_query, limit=15)
                    
                # 去重并添加新论文
                new_papers = []
                for scholar_paper in batch_papers:
                    # 简单去重：检查标题相似度
                    is_duplicate = any(
                        self._is_similar_title(scholar_paper.title, existing.title) 
                        for existing in all_papers
                    )
                    if not is_duplicate:
                        try:
                            paper = convert_scholar_dock_paper(scholar_paper)
                            new_papers.append(paper)
                        except Exception as e:
                            logger.warning(f"转换论文失败: {e}")
                            continue
                
                all_papers.extend(new_papers)
                logger.info(f"📄 批次{i+1}获得{len(new_papers)}篇新论文 (总计: {len(all_papers)}篇)")
                
                # 如果达到目标，提前结束
                if len(all_papers) >= target_count:
                    logger.info(f"🎯 已达到目标论文数: {len(all_papers)}")
                    break
                
                # 批次间延迟，避免频率限制
                if i < len(search_variants) - 1:
                    delay = 30 + i * 10  # 递增延迟时间
                    logger.info(f"⏳ 批次间延迟 {delay} 秒")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.warning(f"批次{i+1}搜索失败: {e}")
                continue
        
        return all_papers
    
    def _is_similar_title(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """简单的标题相似度检测，用于去重"""
        # 移除标点符号和空格，转换为小写
        import re
        clean1 = re.sub(r'[^\w\u4e00-\u9fff]', '', title1.lower())
        clean2 = re.sub(r'[^\w\u4e00-\u9fff]', '', title2.lower())
        
        # 如果一个标题包含在另一个中，且长度相似，认为相似
        if clean1 in clean2 or clean2 in clean1:
            len_ratio = min(len(clean1), len(clean2)) / max(len(clean1), len(clean2))
            return len_ratio > threshold
        
        return False
    
    def _is_chinese_paper(self, paper: Paper) -> bool:
        """判断是否为中文论文"""
        import re
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        
        # 检查标题和作者是否包含中文
        title_has_chinese = bool(chinese_pattern.search(paper.title))
        authors_has_chinese = any(chinese_pattern.search(author) for author in paper.authors)
        
        return title_has_chinese or authors_has_chinese
    
    async def search_parallel_with_filters(
        self, 
        query: str, 
        max_results: int = 20, 
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        sources: Optional[List[str]] = None,
        analysis: Optional[Dict] = None,
        mode: Optional[str] = None,  # 搜索模式
        use_chinese: Optional[bool] = False  # 新增：是否使用中文模式
    ) -> List[Paper]:
        """并行搜索多个数据源（带筛选参数和统一布尔查询）"""
        logger.info(f"开始多源并行搜索: {query}")
        
        
        # 构建统一的布尔查询
        unified_queries = self._build_unified_boolean_query(query, analysis, use_fallback=False, use_chinese=use_chinese)
        language_mode = "中文" if use_chinese else "英文"
        logger.info(f"构建统一布尔查询完成，适配{len(unified_queries)}个搜索源 ({language_mode}模式)")
        
        # 检测中文查询以优化搜索策略
        chinese_query_detected = self._detect_chinese_query(query)
        
        # 获取可用数据源
        available_sources = {}
        if self.arxiv:
            available_sources['arxiv'] = self.arxiv
        if self.crossref:
            available_sources['crossref'] = self.crossref
        if self.scholar_dock:
            available_sources['scholar_dock'] = self.scholar_dock
            
        logger.info(f"可用数据源: {list(available_sources.keys())}")
        
        tasks = []
        source_names = []
        timeout = 30.0
        
        # 数据源选择和配额分配逻辑
        sources_to_search = []
        
        # 数据源名称映射（前端标识符 -> 内部标识符）
        source_mapping = {
            'scholarly': 'scholar_dock',  # 向后兼容：前端仍使用'scholarly'
            'scholar_dock': 'scholar_dock',
            'arxiv': 'arxiv',
            'crossref': 'crossref'
        }
        
        # 🎯 用户指定数据源：严格按用户选择分配
        if sources and isinstance(sources, list) and len(sources) > 0:
            logger.info(f"🎯 用户指定数据源: {sources}")
            
            # 解析用户选择的数据源
            selected_sources = []
            for source_id in sources:
                internal_name = source_mapping.get(source_id, source_id)
                if internal_name in available_sources:
                    source_api = available_sources[internal_name]
                    # 根据数据源特性设置超时时间
                    source_timeout = 300.0 if internal_name == 'scholar_dock' else 30.0
                    selected_sources.append((internal_name, source_api, source_timeout))
                else:
                    logger.warning(f"⚠️ 用户指定的数据源 {source_id} 不可用")
            
            # 配额分配策略
            if len(selected_sources) == 1:
                # 单一数据源：获得100%配额
                source_name, source_api, source_timeout = selected_sources[0]
                sources_to_search.append((source_name, source_api, source_timeout, max_results))
                logger.info(f"📊 单一数据源 {source_name}: 分配100%配额({max_results}篇)")
            else:
                # 🔧 多数据源：更积极的配额分配
                # 基础配额：每源至少20篇，但总和可以超过目标（允许冗余）
                base_quota_per_source = max(20, max_results // len(selected_sources))
                
                # 如果总目标大于30篇，每源分配更多以确保足够结果
                if max_results >= 30:
                    per_source_quota = max(base_quota_per_source, 25)
                else:
                    per_source_quota = base_quota_per_source
                
                for source_name, source_api, source_timeout in selected_sources:
                    sources_to_search.append((source_name, source_api, source_timeout, per_source_quota))
                logger.info(f"📊 多数据源积极分配: {len(selected_sources)}个源，每源{per_source_quota}篇 (总计{per_source_quota * len(selected_sources)}篇冗余)")
            
        
        # 🎯 auto-search模式：使用Google Scholar + arXiv各50%
        elif mode == "auto-search":
            logger.info("🎯 [auto-search] 使用Google Scholar 50% + arXiv 50%配比")
            
            scholar_quota = max_results // 2
            arxiv_quota = max_results - scholar_quota
            
            if 'scholar_dock' in available_sources:
                sources_to_search.append(('scholar_dock', available_sources['scholar_dock'], 300.0, scholar_quota))
            if 'arxiv' in available_sources:
                sources_to_search.append(('arxiv', available_sources['arxiv'], 30.0, arxiv_quota))
            
            logger.info(f"📊 [auto-search] 配额分配: Google Scholar {scholar_quota}篇 + arXiv {arxiv_quota}篇")
        
        # 🌐 默认模式：使用所有可用数据源
        else:
            logger.info("🌐 使用所有可用数据源")
            available_count = len(available_sources)
            if available_count > 0:
                per_source_quota = max(5, max_results // available_count)
                for source_name, source_api in available_sources.items():
                    source_timeout = 300.0 if source_name == 'scholar_dock' else 30.0
                    sources_to_search.append((source_name, source_api, source_timeout, per_source_quota))
                logger.info(f"📊 默认模式配额分配: {available_count}个源，每源{per_source_quota}篇")
        
        # 执行搜索任务
        
        for source_name, source_api, source_timeout, source_limit in sources_to_search:
            source_names.append(source_name)
            # 使用对应的统一布尔查询
            source_query = unified_queries.get(source_name, query)
            logger.debug(f"{source_name}使用查询: {source_query}")
            
            # 🔧 修复：根据不同搜索源传递年限参数
            if source_name == 'scholar_dock' and hasattr(source_api, 'search'):
                # ScholarDock支持年限筛选参数
                if year_from is not None or year_to is not None:
                    logger.info(f"🗓️ ScholarDock启用年限筛选: {year_from}-{year_to}")
                task = asyncio.create_task(
                    asyncio.wait_for(
                        source_api.search(source_query, source_limit, start_year=year_from, end_year=year_to), 
                        timeout=source_timeout
                    )
                )
            elif source_name == 'arxiv' and hasattr(source_api, 'search'):
                # arXiv支持年限筛选参数
                if year_from is not None or year_to is not None:
                    logger.info(f"🗓️ arXiv启用年限筛选: {year_from}-{year_to}")
                task = asyncio.create_task(
                    asyncio.wait_for(
                        source_api.search(source_query, source_limit, start_year=year_from, end_year=year_to), 
                        timeout=source_timeout
                    )
                )
            else:
                # Crossref也需要年限参数支持
                if source_name == 'crossref':
                    task = asyncio.create_task(
                        asyncio.wait_for(
                            source_api.search(source_query, source_limit, start_year=year_from, end_year=year_to), 
                            timeout=source_timeout
                        )
                    )
                else:
                    # 其他搜索源暂时保持原有调用方式
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
                    logger.warning(f"⚠️ 数据源 {source_name} 访问受限: {result}")
                else:
                    logger.error(f"❌ 数据源 {source_name} 出错: {result}")
                continue
            elif isinstance(result, list):
                all_papers.extend(result)
                logger.info(f"✅ {source_name} 返回 {len(result)} 篇论文")
        
        # 🔧 增强智能补偿搜索策略 - 基于用户选择的数据源
        total_papers_obtained = len(all_papers)
        # 🔧 降低补偿搜索阈值，更积极地启动补偿机制
        need_compensation = total_papers_obtained < max_results * 0.9  # 获得结果少于期望的90%时启动补偿
        
        if need_compensation:
            missing_quota = max_results - total_papers_obtained
            logger.warning(f"🔄 搜索结果不足：获得{total_papers_obtained}篇，期望{max_results}篇，缺口{missing_quota}篇")
            
            # 确定补偿搜索源：使用未被选择的其他可用数据源
            compensation_sources = []
            selected_source_names = set(source_names)
            
            for source_name, source_api in available_sources.items():
                # 如果该源未被用户选择，且没有访问错误，则可用于补偿
                if source_name not in selected_source_names and source_name not in captcha_errors:
                    source_timeout = 300.0 if source_name == 'scholar_dock' else 30.0
                    compensation_sources.append((source_name, source_api, source_timeout))
            
            if compensation_sources and missing_quota > 0:
                logger.info(f"🚀 启动补偿搜索：使用{len(compensation_sources)}个备用数据源")
                
                # 🔧 增强配额分配：每个源至少分配10篇，最多20篇
                base_quota_per_source = 15  # 基础配额
                min_quota = 10              # 最小配额
                max_quota = 25              # 最大配额
                
                # 根据缺口和可用源数量动态分配
                if missing_quota <= len(compensation_sources) * min_quota:
                    # 缺口较小，平均分配
                    compensation_per_source = max(min_quota, missing_quota // len(compensation_sources))
                else:
                    # 缺口较大，每个源分配基础配额
                    compensation_per_source = min(max_quota, 
                                                max(base_quota_per_source, 
                                                   missing_quota // len(compensation_sources)))
                
                logger.info(f"📊 补偿搜索配额：每源{compensation_per_source}篇，总计{compensation_per_source * len(compensation_sources)}篇")
                compensation_tasks = []
                compensation_source_names = []
                
                for source_name, source_api, source_timeout in compensation_sources:
                    compensation_source_names.append(source_name)
                    source_query = unified_queries.get(source_name, query)
                    
                    logger.info(f"📈 补偿搜索-{source_name}：分配{compensation_per_source}篇")
                    
                    # 支持年限参数的补偿搜索
                    if source_name == 'scholar_dock' and hasattr(source_api, 'search'):
                        task = asyncio.create_task(
                            asyncio.wait_for(
                                source_api.search(source_query, compensation_per_source, start_year=year_from, end_year=year_to), 
                                timeout=source_timeout
                            )
                        )
                    elif source_name == 'arxiv' and hasattr(source_api, 'search'):
                        task = asyncio.create_task(
                            asyncio.wait_for(
                                source_api.search(source_query, compensation_per_source, start_year=year_from, end_year=year_to), 
                                timeout=source_timeout
                            )
                        )
                    else:
                        # Crossref也需要年限参数支持
                        if source_name == 'crossref':
                            task = asyncio.create_task(
                                asyncio.wait_for(
                                    source_api.search(source_query, compensation_per_source, start_year=year_from, end_year=year_to), 
                                    timeout=source_timeout
                                )
                            )
                        else:
                            task = asyncio.create_task(
                                asyncio.wait_for(
                                    source_api.search(source_query, compensation_per_source), 
                                    timeout=source_timeout
                                )
                            )
                    compensation_tasks.append(task)
                
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
                                logger.info(f"✅ 补偿搜索-{source_name}：获得{len(comp_result)}篇额外论文")
                            elif isinstance(comp_result, Exception):
                                source_name = compensation_source_names[i] if i < len(compensation_source_names) else f"补偿源{i}"
                                logger.warning(f"⚠️ 补偿搜索-{source_name}失败: {comp_result}")
                        
                        if compensation_papers > 0:
                            logger.info(f"🎯 补偿搜索完成：总计获得{compensation_papers}篇额外论文")
                        else:
                            logger.info("📍 补偿搜索未获得额外论文")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ 补偿搜索执行失败: {e}")
            else:
                if not compensation_sources:
                    logger.info("📍 没有可用的补偿数据源")
                else:
                    logger.info("📍 无需补偿搜索，结果数量充足")
        
        # 处理访问受限的数据源
        if captcha_errors:
            successful_sources = [name for name in source_names if name not in captcha_errors]
            
            if len(captcha_errors) == len(source_names):
                # 所有数据源都访问受限
                logger.warning(f"🚫 所有数据源访问受限: {', '.join(captcha_errors)}")
                logger.info("💡 建议: 稍后重试或使用不同关键词")
            elif len(successful_sources) > 0:
                # 部分数据源访问受限，但仍有可用源
                compensation_status = "已启动补偿搜索" if need_compensation else "其他数据源正常"
                logger.info(f"⚠️ 部分数据源受限: {', '.join(captcha_errors)}，{compensation_status} ({len(successful_sources)}个源可用)")
            else:
                logger.info(f"⚠️ 数据源访问受限: {', '.join(captcha_errors)}，系统正常运行")
        
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
        
        # 🔄 动态降级策略：如果结果不足，启动多轮补充搜索
        if len(final_results) < max_results * 0.85 and analysis and analysis.get("hierarchical_keywords"):  # 降低到85%阈值
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
        
        # 🔧 智能源过滤机制：分层过滤策略，保持用户选择源为主，适度保留补偿搜索结果
        if sources and isinstance(sources, list) and len(sources) > 0:
            original_count = len(final_results)
            
            # 统一映射前端标识到内部标识
            user_selected_sources = set()
            for sid in sources:
                mapped = {
                    'scholarly': 'scholar_dock',
                    'scholar_dock': 'scholar_dock',
                    'arxiv': 'arxiv',
                    'crossref': 'crossref'
                }.get(sid, sid)
                user_selected_sources.add(mapped)
            
            # 分类论文：用户选择源 vs 补偿搜索源
            user_source_papers = []
            compensation_papers = []
            source_stats = {}  # 统计各源的论文数量
            
            for paper in final_results:
                paper_source = paper.source.lower()
                
                # 初始化源统计
                if paper_source not in source_stats:
                    source_stats[paper_source] = {'total': 0, 'retained': 0, 'type': ''}
                source_stats[paper_source]['total'] += 1
                
                # 检查是否为用户选择的源（支持模糊匹配）
                is_user_source = (paper_source in user_selected_sources or 
                                any(allowed_source in paper_source for allowed_source in user_selected_sources) or
                                any(paper_source in allowed_source for allowed_source in user_selected_sources))
                
                if is_user_source:
                    user_source_papers.append(paper)
                    source_stats[paper_source]['type'] = '用户选择'
                    source_stats[paper_source]['retained'] += 1
                else:
                    compensation_papers.append(paper)
                    source_stats[paper_source]['type'] = '补偿搜索'
            
            # 对补偿搜索结果进行质量筛选
            filtered_compensation = self._filter_compensation_papers(
                compensation_papers, 
                max_compensation_ratio=0.25,  # 最多占25%
                target_total=len(user_source_papers)
            )
            
            # 更新补偿搜索源的保留统计
            retained_compensation_sources = {paper.source.lower() for paper in filtered_compensation}
            for source, stats in source_stats.items():
                if stats['type'] == '补偿搜索':
                    if source in retained_compensation_sources:
                        stats['retained'] = len([p for p in filtered_compensation if p.source.lower() == source])
                    else:
                        stats['retained'] = 0
            
            # 合并最终结果
            final_results = user_source_papers + filtered_compensation
            
            # 🚀 增强日志记录：详细的源贡献统计
            logger.info(f"📊 搜索源贡献统计：")
            
            # 用户选择源统计
            user_sources_info = []
            for source, stats in source_stats.items():
                if stats['type'] == '用户选择':
                    retention_rate = (stats['retained'] / stats['total'] * 100) if stats['total'] > 0 else 0
                    user_sources_info.append(f"{source}: {stats['retained']}篇 (100%)")
            
            if user_sources_info:
                logger.info(f"✅ 用户选择源：{', '.join(user_sources_info)}")
            
            # 补偿搜索源统计
            compensation_sources_info = []
            for source, stats in source_stats.items():
                if stats['type'] == '补偿搜索':
                    retention_rate = (stats['retained'] / stats['total'] * 100) if stats['total'] > 0 else 0
                    if stats['total'] > 0:
                        compensation_sources_info.append(f"{source}: {stats['retained']}/{stats['total']}篇 ({retention_rate:.0f}%)")
            
            if compensation_sources_info:
                logger.info(f"🔄 补偿搜索源：{', '.join(compensation_sources_info)}")
            
            # 最终构成统计
            user_count = len(user_source_papers)
            comp_count = len(filtered_compensation)
            user_ratio = (user_count / len(final_results) * 100) if len(final_results) > 0 else 0
            comp_ratio = (comp_count / len(final_results) * 100) if len(final_results) > 0 else 0
            
            logger.info(f"📈 最终构成：用户选择源 {user_count}篇 ({user_ratio:.0f}%) + 补偿源 {comp_count}篇 ({comp_ratio:.0f}%) = 总计 {len(final_results)}篇")
            
            if original_count != len(final_results):
                filtered_count = original_count - len(final_results)
                logger.info(f"🔒 智能过滤完成：{original_count} → {len(final_results)} (过滤{filtered_count}篇低质量补偿结果)")
                
                # 如果补偿过滤过于严格，给出提醒
                if comp_count == 0 and len(compensation_papers) > 0:
                    logger.warning(f"⚠️ 补偿搜索结果被完全过滤，可能质量评估过于严格")
            else:
                logger.info(f"✅ 智能过滤完成：保留全部 {len(final_results)} 篇高质量结果")

        logger.info(f"搜索完成: 原始 {len(all_papers)} 篇 → 去重 {len(deduplicated_papers)} 篇 → 最终 {len(final_results)} 篇")
        return final_results
    
    def _deduplicate_papers(self, papers: List[Paper]) -> List[Paper]:
        """🔧 优化的去重逻辑 - 减少误删"""
        seen_titles = set()
        seen_dois = set()
        unique_papers = []
        duplicate_count = 0
        
        # 优化排序：稳定数据源优先，引用数次之
        papers_sorted = sorted(papers, key=lambda p: (
            -(p.citations or 0),
            p.doi is not None,
            p.source == 'scholar_dock',  # ScholarDock主力优先
            p.source in ['arxiv', 'crossref'],  # 辅助数据源次之
        ), reverse=True)
        
        for paper in papers_sorted:
            # 🔧 放宽数据质量过滤：保留更多有用的论文
            if not paper.title or len(paper.title.strip()) < 3:  # 只过滤明显无效的标题
                continue
            
            # DOI去重（保持不变）
            if paper.doi and paper.doi.strip():
                if paper.doi in seen_dois:
                    duplicate_count += 1
                    continue
                seen_dois.add(paper.doi)
            
            # 🔧 优化标题去重：使用更智能的相似度检测
            normalized_title = self._normalize_title(paper.title)
            
            # 检查是否与已存在标题过于相似
            is_similar = False
            for existing_title in seen_titles:
                if self._is_title_duplicate(normalized_title, existing_title):
                    is_similar = True
                    duplicate_count += 1
                    break
            
            if is_similar:
                continue
            
            seen_titles.add(normalized_title)
            unique_papers.append(paper)
        
        logger.info(f"📊 去重统计: 输入{len(papers)}篇 → 去重{duplicate_count}篇 → 保留{len(unique_papers)}篇")
        return unique_papers
    
    def _normalize_title(self, title: str) -> str:
        """🔧 优化标题标准化 - 保留更多信息"""
        if not title:
            return ""
        
        import re
        # 🔧 保留更多标点符号信息，避免过度标准化导致误删
        normalized = title.lower().strip()
        # 只移除多余空格，保留其他标点符号
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()
    
    def _is_title_duplicate(self, title1: str, title2: str, threshold: float = 0.9) -> bool:
        """🔧 智能标题重复检测 - 减少误判"""
        if not title1 or not title2:
            return False
        
        # 完全相同
        if title1 == title2:
            return True
        
        # 长度差异过大，不太可能重复
        len_ratio = min(len(title1), len(title2)) / max(len(title1), len(title2))
        if len_ratio < 0.7:  # 长度差异超过30%，认为不重复
            return False
        
        # 🔧 使用词汇级别的相似度检测，而非字符级别
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        # 计算Jaccard相似度
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return False
        
        jaccard_similarity = intersection / union
        return jaccard_similarity >= threshold
    
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
            
            # 🔧 向后兼容：处理前端传递的'scholarly'标识符
            compatible_sources = []
            if sources:
                for source in sources:
                    if source == 'scholarly':
                        compatible_sources.append('scholar_dock')  # 映射到内部标识符
                    else:
                        compatible_sources.append(source)
            else:
                compatible_sources = sources
            
            # 选择最有效的数据源进行补充搜索（优先选择稳定的源）
            fallback_sources = []
            if not compatible_sources or 'arxiv' in compatible_sources:
                if self.arxiv:
                    fallback_sources.append(('arxiv', self.arxiv, 30.0))
            if not compatible_sources or 'crossref' in compatible_sources:
                if self.crossref:
                    fallback_sources.append(('crossref', self.crossref, 30.0))
            if not compatible_sources or 'scholar_dock' in compatible_sources:
                if self.scholar_dock:
                    fallback_sources.append(('scholar_dock', self.scholar_dock, 180.0))  # 补充搜索也给3分钟超时
            
            if not fallback_sources:
                logger.warning("⚠️ 没有可用的数据源进行补充搜索")
                return []
            
            # 🔧 增强配额分配：补充搜索更积极
            per_source_limit = max(8, needed_count // len(fallback_sources))  # 至少每源8篇
            if needed_count > 20:  # 对于大缺口，每源分配更多
                per_source_limit = max(per_source_limit, 15)
            
            logger.info(f"📊 补充搜索配额：每源{per_source_limit}篇，使用{len(fallback_sources)}个源")
            
            # 并行执行补充搜索
            fallback_tasks = []
            source_names = []
            
            for source_name, source_api, timeout in fallback_sources:
                source_names.append(source_name)
                fallback_query = fallback_unified_queries.get(source_name, original_query)
                
                logger.debug(f"🔍 {source_name}补充搜索: {fallback_query}")
                # 🔧 修复：fallback搜索中也支持年限参数
                if source_name == 'scholar_dock' and hasattr(source_api, 'search'):
                    # ScholarDock补充搜索支持年限筛选参数
                    task = asyncio.create_task(
                        asyncio.wait_for(
                            source_api.search(fallback_query, per_source_limit, start_year=year_from, end_year=year_to), 
                            timeout=timeout
                        )
                    )
                elif source_name == 'arxiv' and hasattr(source_api, 'search'):
                    # arXiv补充搜索支持年限筛选参数
                    task = asyncio.create_task(
                        asyncio.wait_for(
                            source_api.search(fallback_query, per_source_limit, start_year=year_from, end_year=year_to), 
                            timeout=timeout
                        )
                    )
                else:
                    # Crossref也需要年限参数支持
                    if source_name == 'crossref':
                        task = asyncio.create_task(
                            asyncio.wait_for(
                                source_api.search(fallback_query, per_source_limit, start_year=year_from, end_year=year_to), 
                                timeout=timeout
                            )
                        )
                    else:
                        # 其他搜索源保持原有调用方式
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
    
    def _detect_chinese_query(self, query: str) -> bool:
        """检测查询是否包含中文字符"""
        try:
            import re
            
            # 检测中文字符（包括常用汉字、标点符号）
            chinese_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\u20000-\u2a6df\uf900-\ufaff]'
            chinese_matches = re.findall(chinese_pattern, query)
            
            if chinese_matches:
                chinese_char_count = len(chinese_matches)
                
                # 移除空格和标点符号，只计算实际字符
                clean_query = re.sub(r'[^\w\u4e00-\u9fff]', '', query)
                total_char_count = len(clean_query)
                
                # 如果中文字符占比超过30%，认为是中文查询
                if total_char_count > 0:
                    chinese_ratio = chinese_char_count / total_char_count
                    is_chinese = chinese_ratio >= 0.3  # 提高阈值到30%
                    
                    logger.debug(f"查询语言检测: 中文字符{chinese_char_count}个/总计{total_char_count}个 = {chinese_ratio:.2%} → {'中文' if is_chinese else '非中文'}")
                    return is_chinese
                else:
                    # 如果有中文字符但总字符很少，仍认为是中文查询
                    return chinese_char_count > 0
            
            return False
            
        except Exception as e:
            logger.warning(f"中文查询检测失败: {e}")
            return False
    
    def _filter_compensation_papers(self, compensation_papers: List[Paper], max_compensation_ratio: float = 0.25, target_total: int = 0) -> List[Paper]:
        """
        智能筛选补偿搜索结果，基于质量评估保留最优论文
        
        Args:
            compensation_papers: 补偿搜索获得的论文列表
            max_compensation_ratio: 补偿搜索结果最大占比 (默认25%)
            target_total: 用户选择源的论文数量，用于计算补偿配额
        
        Returns:
            筛选后的高质量补偿搜索论文列表
        """
        if not compensation_papers:
            return []
        
        # 计算补偿搜索的最大允许数量
        if target_total > 0:
            max_compensation_count = max(1, int(target_total * max_compensation_ratio / (1 - max_compensation_ratio)))
        else:
            max_compensation_count = max(5, len(compensation_papers) // 2)  # 降级策略：至少5篇或一半
        
        # 如果补偿论文数量已经在限制内，不需要过滤
        if len(compensation_papers) <= max_compensation_count:
            logger.debug(f"📊 补偿搜索论文数量({len(compensation_papers)})在限制内，无需过滤")
            return compensation_papers
        
        # 为每篇论文计算质量评分
        scored_papers = []
        for paper in compensation_papers:
            quality_score = self._calculate_paper_quality_score(paper)
            scored_papers.append((paper, quality_score))
        
        # 按质量评分降序排序
        scored_papers.sort(key=lambda x: x[1], reverse=True)
        
        # 选择前N篇高质量论文
        selected_papers = [paper for paper, _ in scored_papers[:max_compensation_count]]
        
        # 记录质量筛选统计
        total_compensation = len(compensation_papers)
        selected_count = len(selected_papers)
        
        if total_compensation > selected_count:
            min_score = scored_papers[selected_count-1][1] if selected_count > 0 else 0
            max_score = scored_papers[0][1] if scored_papers else 0
            logger.debug(f"📊 补偿搜索质量筛选：{total_compensation} → {selected_count}篇 (质量评分范围: {min_score:.2f}-{max_score:.2f})")
        
        return selected_papers
    
    def _calculate_paper_quality_score(self, paper: Paper) -> float:
        """
        计算论文质量评分，用于补偿搜索结果筛选
        
        评分组成：
        - 引用数评分 (40%): 基于引用数量的对数标准化
        - 年份评分 (30%): 较新的论文得分更高  
        - 相关性评分 (30%): 基于标题和摘要的完整性
        
        Args:
            paper: 论文对象
            
        Returns:
            质量评分 (0-10分)
        """
        import math
        from datetime import datetime
        
        # 基础分数
        citation_score = 0.0  # 引用数评分 (0-4分)
        year_score = 0.0     # 年份评分 (0-3分)
        relevance_score = 0.0 # 相关性评分 (0-3分)
        
        # 1. 引用数评分 (40%权重，最高4分)
        citations = paper.citations or 0
        if citations > 0:
            # 使用对数标准化，避免极值论文主导
            citation_score = min(4.0, math.log10(citations + 1) * 1.2)
        
        # 2. 年份评分 (30%权重，最高3分)
        current_year = datetime.now().year
        if paper.year:
            years_ago = current_year - paper.year
            if years_ago <= 0:  # 当年或未来
                year_score = 3.0
            elif years_ago <= 2:  # 2年内
                year_score = 2.5
            elif years_ago <= 5:  # 5年内
                year_score = 2.0
            elif years_ago <= 10:  # 10年内
                year_score = 1.5
            else:  # 10年以上
                year_score = max(0.5, 1.5 - (years_ago - 10) * 0.1)
        
        # 3. 相关性评分 (30%权重，最高3分)
        # 基于标题和摘要的完整性
        if paper.title and len(paper.title.strip()) > 10:
            relevance_score += 1.0  # 有效标题
        
        if paper.abstract and len(paper.abstract.strip()) > 50:
            relevance_score += 1.0  # 有摘要
            
        # 基于摘要长度的额外评分
        if paper.abstract:
            abstract_length = len(paper.abstract.strip())
            if abstract_length > 200:
                relevance_score += 1.0  # 摘要充实
            elif abstract_length > 100:
                relevance_score += 0.5  # 摘要中等
        
        # 如果有DOI，额外加分
        if paper.doi:
            relevance_score += 0.5
        
        # 限制相关性评分上限
        relevance_score = min(3.0, relevance_score)
        
        # 计算总分 (0-10分)
        total_score = citation_score + year_score + relevance_score
        
        # 记录评分详情（仅在调试模式下）
        logger.debug(f"📊 质量评分: {paper.title[:30]}... → 总分{total_score:.2f}分 "
                    f"(引用{citation_score:.1f} + 年份{year_score:.1f} + 相关性{relevance_score:.1f})")
        
        return total_score
    
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
        if self.scholar_dock:
            coros.append(self.scholar_dock.close())
        if self.crossref:
            coros.append(self.crossref.close())
            
        await asyncio.gather(*coros)
