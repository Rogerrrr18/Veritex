#!/usr/bin/env python3
"""
ScholarDock风格的Google Scholar爬虫引擎
移植ScholarDock项目的高效HTML解析技术，支持智能CAPTCHA处理
"""

import requests
import time
import re
import asyncio
import logging
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from datetime import datetime
from dataclasses import dataclass

# 可选Selenium导入
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class ScholarDockPaper:
    """ScholarDock增强的论文数据结构"""
    title: str
    authors: List[str]
    abstract: str = ""
    year: Optional[int] = None
    journal: str = ""
    url: str = ""
    doi: Optional[str] = None
    citations: int = 0
    source: str = "scholar_dock"
    
    # ScholarDock扩展字段
    citations_per_year: float = 0.0
    venue: str = ""
    publisher: str = ""
    description: str = ""

class ScholarDockSpider:
    """
    基于ScholarDock项目的高效Google Scholar爬虫
    特点：
    1. 直接HTML解析，绕过scholarly库限制
    2. 智能CAPTCHA检测和处理
    3. 支持大批量搜索(最多1000条)
    4. 更全面的数据字段提取
    """
    
    def __init__(self):
        self.base_url = 'https://scholar.google.com/scholar?start={}&q={}&hl=en&as_sdt=0,5'
        self.startyear_url = '&as_ylo={}'
        self.endyear_url = '&as_yhi={}'
        
        # CAPTCHA检测关键词
        self.robot_keywords = [
            'unusual traffic from your computer network',
            'not a robot',
            'captcha',
            'blocked'
        ]
        
        # 请求配置
        self.request_delay = 0.8  # 比ScholarDock的0.5s稍保守
        self.max_retries = 3
        self.timeout = 30
        
        self.session = None
        self.driver = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = requests.Session()
        # 设置请求头，模拟真实浏览器
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            self.session.close()
        if self.driver:
            self.driver.quit()
    
    def _create_search_url(self, query: str, start: int = 0, 
                          start_year: Optional[int] = None, 
                          end_year: Optional[int] = None) -> str:
        """构建搜索URL"""
        import urllib.parse
        
        # 简化复杂的布尔查询 - Google Scholar对复杂嵌套查询支持有限
        simplified_query = self._simplify_boolean_query(query)
        
        # 正确的URL编码
        encoded_query = urllib.parse.quote_plus(simplified_query)
        url = self.base_url.format(start, encoded_query)
        
        if start_year:
            url += self.startyear_url.format(start_year)
            
        if end_year and end_year != datetime.now().year:
            url += self.endyear_url.format(end_year)
            
        return url
    
    def _simplify_boolean_query(self, query: str) -> str:
        """简化布尔查询，使其适合Google Scholar"""
        try:
            # 如果查询过长或过于复杂，提取核心关键词
            if len(query) > 200 or query.count('(') > 3:
                logger.info(f"🔧 简化复杂查询: {len(query)} 字符 -> 核心关键词")
                
                # 提取引号内的主要关键词
                import re
                quoted_terms = re.findall(r'"([^"]*)"', query)
                core_terms = []
                
                for term in quoted_terms:
                    if term.strip() and len(term.split()) <= 4:  # 只取短语
                        core_terms.append(f'"{term}"')
                
                # 如果没有引号内容，提取AND/OR前的主要词组
                if not core_terms:
                    # 分割OR部分，取前几个最相关的
                    or_parts = query.split(' OR ')
                    for part in or_parts[:3]:  # 最多取3个OR部分
                        clean_part = re.sub(r'[()"]', '', part).strip()
                        if clean_part and len(clean_part.split()) <= 6:
                            core_terms.append(clean_part)
                
                # 组合为简单查询
                if core_terms:
                    simplified = ' OR '.join(core_terms[:3])  # 最多3个主要词组
                    logger.info(f"✅ 简化结果: {simplified}")
                    return simplified
            
            # 查询不太复杂，直接返回
            return query
            
        except Exception as e:
            logger.warning(f"查询简化失败: {e}，使用原查询前100字符")
            return query[:100]
    
    def _extract_citations(self, content: str) -> int:
        """从内容中提取引用数 - 增强版本"""
        # 支持多种引用格式匹配
        patterns = [
            r'Cited by\s*(\d+)',  # 标准格式: "Cited by 123"
            r'引用\s*(\d+)',      # 中文格式: "引用 123"
            r'被引用\s*(\d+)',    # 中文格式: "被引用 123"
            r'>\s*(\d+)\s*</a>.*[Cc]ited',  # HTML格式
            r'"gs_fl">\s*<a[^>]*>(\d+)</a>.*[Cc]itation',  # HTML具体格式
            r'<a[^>]*>(\d+)</a>\s*citations?',  # 通用HTML citation格式（支持单复数）
            r'href="[^"]*">(\d+)</a>[^<]*citation'  # 更通用的HTML格式
        ]
        
        for pattern in patterns:
            citation_match = re.search(pattern, content, re.IGNORECASE)
            if citation_match:
                try:
                    citations = int(citation_match.group(1))
                    # 合理性检查：引用数不应超过1,000,000
                    if 0 <= citations <= 1000000:
                        return citations
                except (ValueError, IndexError):
                    continue
        return 0
    
    def _extract_year(self, content: str) -> Optional[int]:
        """从内容中提取年份 - 增强版本，提高准确性"""
        import datetime
        current_year = datetime.datetime.now().year
        
        # 多种年份提取模式，按优先级排序
        patterns = [
            r'(\b(?:19|20)\d{2}\b)(?=\s*-\s*[^\d])',  # 年份后跟破折号和非数字
            r'\b((?:19|20)\d{2})\b(?=\s*$)',          # 行尾的年份
            r'\b((?:19|20)\d{2})\b(?=\s*,)',          # 年份后跟逗号
            r'\b((?:19|20)\d{2})\b(?=\s*\))',         # 年份后跟右括号
            r'\(((?:19|20)\d{2})\)',                   # 括号内的年份
            r'\b((?:19|20)\d{2})\b'                   # 通用4位数年份
        ]
        
        for pattern in patterns:
            year_matches = re.findall(pattern, content)
            if year_matches:
                # 筛选合理的年份（1900-当前年份+2）
                valid_years = []
                for year_str in year_matches:
                    try:
                        year = int(year_str)
                        if 1900 <= year <= current_year + 2:  # 允许未来2年的论文
                            valid_years.append(year)
                    except ValueError:
                        continue
                
                if valid_years:
                    # 如果有多个有效年份，选择最接近当前时间但不超过的年份
                    # 或选择在合理发表范围内的年份
                    if len(valid_years) == 1:
                        return valid_years[0]
                    else:
                        # 优先选择较新的年份，但要在合理范围内
                        sorted_years = sorted(valid_years, reverse=True)
                        return sorted_years[0]
        return None
    
    def _extract_author(self, gs_a_text: str) -> str:
        """从gs_a文本中提取作者信息（增强版本，支持多作者解析）"""
        try:
            # 查找第一个破折号前的内容作为作者
            parts = gs_a_text.split('-')
            if len(parts) > 0:
                author_part = parts[0].strip()
                if not author_part:
                    return "作者未知"
                
                # 处理多作者分割，支持常见分隔符
                authors = self._split_multiple_authors(author_part)
                
                # 标准化每个作者姓名
                standardized_authors = [self._standardize_author_name(author.strip()) 
                                      for author in authors if author.strip()]
                
                # 过滤无效作者
                valid_authors = [author for author in standardized_authors 
                               if author and author != "作者未知" and len(author) > 1]
                
                # 返回格式化的作者字符串（用逗号分隔多个作者）
                return ", ".join(valid_authors) if valid_authors else "作者未知"
        except Exception as e:
            logger.debug(f"作者提取失败: {e}")
        return "作者未知"
    
    def _split_multiple_authors(self, author_text: str) -> List[str]:
        """智能分割多个作者"""
        # 常见的作者分隔符模式
        separators = [
            r',\s*and\s+',  # ", and "
            r'\s+and\s+',   # " and "
            r',\s*&\s*',    # ", & "
            r'\s*&\s*',     # " & "
            r',\s+'         # ", " (最后处理，避免误分割)
        ]
        
        authors = [author_text]
        
        # 依次使用分隔符进行分割
        for separator in separators:
            new_authors = []
            for author in authors:
                new_authors.extend(re.split(separator, author))
            authors = new_authors
        
        return authors
    
    def _standardize_author_name(self, name: str) -> str:
        """标准化作者姓名格式"""
        if not name or not name.strip():
            return ""
        
        name = name.strip()
        
        # 处理明显的无效作者
        invalid_patterns = ['作者未知', 'unknown', 'author', '...', 'et al']
        if any(pattern in name.lower() for pattern in invalid_patterns):
            return ""
        
        # 处理缩写姓名（如 "ZH Zhou" -> "Z.H. Zhou"）
        # 匹配模式：大写字母+大写字母+空格+姓氏
        abbreviation_pattern = r'^([A-Z])([A-Z]+)\s+([A-Za-z\-\']+)$'
        match = re.match(abbreviation_pattern, name)
        if match:
            first_initials = match.group(1) + match.group(2)
            last_name = match.group(3)
            # 在每个首字母后添加点号
            formatted_initials = '.'.join(first_initials) + '.'
            return f"{formatted_initials} {last_name}"
        
        # 处理单个首字母缩写（如 "J Smith" -> "J. Smith"）
        single_initial_pattern = r'^([A-Z])\s+([A-Za-z\-\']+)$'
        match = re.match(single_initial_pattern, name)
        if match:
            initial = match.group(1)
            last_name = match.group(2)
            return f"{initial}. {last_name}"
        
        # 处理已经有点号的缩写（如 "J. Smith"）保持不变
        if re.match(r'^[A-Z](\.[A-Z])*\.\s+[A-Za-z\-\']+', name):
            return name
        
        # 标准化姓名格式：首字母大写，其他小写
        parts = name.split()
        if len(parts) >= 2:
            # 处理完整姓名：First Last 或 First Middle Last
            formatted_parts = []
            for part in parts:
                if len(part) > 1:
                    formatted_parts.append(part.capitalize())
                else:
                    formatted_parts.append(part.upper() + '.')
            return ' '.join(formatted_parts)
        
        # 单个词的情况（可能是姓氏）
        return name.capitalize()
    
    def _extract_venue_publisher(self, gs_a_text: str) -> tuple:
        """从gs_a文本中提取期刊和出版商信息"""
        try:
            parts = gs_a_text.split('-')
            if len(parts) >= 3:
                # 通常格式：作者 - 期刊/会议, 年份 - 出版商
                venue_part = parts[1].strip()
                publisher = parts[-1].strip()
                
                # 从期刊部分提取年份前的内容
                venue_clean = re.sub(r',?\s*\d{4}.*', '', venue_part).strip()
                return venue_clean, publisher
            elif len(parts) == 2:
                return "", parts[-1].strip()
        except Exception as e:
            logger.debug(f"期刊出版商提取失败: {e}")
        return "", ""
    
    def _calculate_citations_per_year(self, citations: int, year: Optional[int]) -> float:
        """计算年均引用数"""
        if not year or citations <= 0:
            return 0.0
        
        years_passed = max(1, datetime.now().year - year)
        return round(citations / years_passed, 2)
    
    def _setup_selenium_driver(self):
        """设置Selenium Chrome驱动"""
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium不可用，无法处理CAPTCHA")
            return None
            
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 不使用headless模式，方便用户解决CAPTCHA
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Selenium Chrome驱动初始化成功")
            return driver
            
        except Exception as e:
            logger.error(f"❌ Selenium驱动初始化失败: {e}")
            return None
    
    def _get_element_safe(self, driver, xpath: str, attempts: int = 5) -> Optional[any]:
        """安全获取元素，带重试机制"""
        for attempt in range(attempts):
            try:
                element = driver.find_element(By.XPATH, xpath)
                return element
            except Exception as e:
                if attempt < attempts - 1:
                    logger.debug(f"元素获取失败，重试中... ({attempt + 1}/{attempts})")
                    time.sleep(1)
                else:
                    logger.error(f"元素获取最终失败: {e}")
        return None
    
    async def _get_content_with_selenium(self, url: str) -> Optional[bytes]:
        """使用Selenium获取内容，处理CAPTCHA"""
        if not SELENIUM_AVAILABLE:
            return None
            
        try:
            if not self.driver:
                self.driver = self._setup_selenium_driver()
                
            if not self.driver:
                return None
            
            logger.info(f"🌐 使用Selenium访问: {url}")
            self.driver.get(url)
            
            # 等待页面加载
            await asyncio.sleep(2)
            
            body_element = self._get_element_safe(self.driver, "//body")
            if not body_element:
                return None
                
            content = body_element.get_attribute('innerHTML')
            
            # 检查是否需要解决CAPTCHA
            if any(keyword in content.lower() for keyword in self.robot_keywords):
                logger.warning("🚨 检测到CAPTCHA，请在打开的浏览器中手动解决")
                logger.info("💡 解决CAPTCHA后，程序将自动继续...")
                
                # 等待用户解决CAPTCHA（最多等待5分钟）
                wait = WebDriverWait(self.driver, 300)
                try:
                    # 等待页面变化，表示CAPTCHA已解决
                    wait.until(lambda driver: not any(
                        keyword in driver.page_source.lower() 
                        for keyword in self.robot_keywords
                    ))
                    logger.info("✅ CAPTCHA已解决，继续搜索")
                except Exception:
                    logger.error("⏰ CAPTCHA解决超时，跳过此页面")
                    return None
                
                # 重新获取内容
                body_element = self._get_element_safe(self.driver, "//body")
                if body_element:
                    content = body_element.get_attribute('innerHTML')
            
            return content.encode('utf-8')
            
        except Exception as e:
            logger.error(f"❌ Selenium获取内容失败: {e}")
            return None
    
    def _parse_article_div(self, div) -> Optional[ScholarDockPaper]:
        """解析单个文章div，提取详细信息"""
        try:
            # 1. 提取标题和URL
            title_elem = div.find('h3')
            if not title_elem:
                return None
                
            title_link = title_elem.find('a')
            if title_link:
                title = title_link.get_text(strip=True)
                url = title_link.get('href', '')
            else:
                title = title_elem.get_text(strip=True)
                url = ""
            
            if not title or title == "Could not catch title":
                return None
            
            # 2. 提取引用数
            div_str = str(div)
            citations = self._extract_citations(div_str)
            
            # 3. 提取作者、期刊、出版商信息
            gs_a_div = div.find('div', class_='gs_a')
            if gs_a_div:
                gs_a_text = gs_a_div.get_text()
                
                # 提取年份
                year = self._extract_year(gs_a_text)
                
                # 提取作者
                author = self._extract_author(gs_a_text)
                
                # 提取期刊和出版商
                venue, publisher = self._extract_venue_publisher(gs_a_text)
            else:
                year = None
                author = "作者未知"
                venue = ""
                publisher = ""
            
            # 4. 提取描述/摘要
            description = ""
            gs_rs_div = div.find('div', class_='gs_rs')
            if gs_rs_div:
                description = gs_rs_div.get_text(strip=True)
            
            # 5. 计算年均引用数
            citations_per_year = self._calculate_citations_per_year(citations, year)
            
            # 6. 处理作者列表：将逗号分隔的作者字符串转换为列表
            authors_list = []
            if author and author != "作者未知":
                # 将逗号分隔的作者字符串分割为列表
                authors_list = [a.strip() for a in author.split(',') if a.strip()]
            
            # 7. 创建论文对象
            paper = ScholarDockPaper(
                title=title,
                authors=authors_list,
                abstract=description,
                year=year,
                journal=venue,
                url=url,
                citations=citations,
                citations_per_year=citations_per_year,
                venue=venue,
                publisher=publisher,
                description=description,
                source="scholar_dock"
            )
            
            return paper
            
        except Exception as e:
            logger.error(f"解析文章失败: {e}")
            return None
    
    async def search(self, query: str, limit: int = 50,
                    start_year: Optional[int] = None,
                    end_year: Optional[int] = None) -> List[ScholarDockPaper]:
        """
        搜索Google Scholar
        
        Args:
            query: 搜索查询
            limit: 结果数量限制 (最多1000)
            start_year: 起始年份
            end_year: 结束年份
            
        Returns:
            论文列表
        """
        
        # 限制最大结果数
        limit = min(limit, 1000)
        papers = []
        
        logger.info(f"🔍 ScholarDock搜索开始: {query} (目标: {limit}条)")
        
        # 按10条一页进行搜索
        for start_idx in range(0, limit, 10):
            try:
                url = self._create_search_url(query, start_idx, start_year, end_year)
                logger.info(f"📖 获取第{start_idx//10 + 1}页: {url}")
                
                content = None
                
                # 首先尝试普通HTTP请求
                try:
                    response = self.session.get(url, timeout=self.timeout)
                    content = response.content
                    content_str = content.decode('utf-8', errors='ignore')
                    
                    # 检查是否被机器人检测
                    if any(keyword in content_str.lower() for keyword in self.robot_keywords):
                        logger.warning("🤖 检测到机器人验证，切换到Selenium")
                        content = await self._get_content_with_selenium(url)
                        
                except Exception as e:
                    logger.warning(f"HTTP请求失败: {e}，尝试Selenium")
                    content = await self._get_content_with_selenium(url)
                
                if not content:
                    logger.error("❌ 无法获取页面内容，跳过此页")
                    continue
                
                # 使用BeautifulSoup解析HTML
                soup = BeautifulSoup(content, 'html.parser')
                
                # 查找文章div
                article_divs = soup.find_all("div", class_="gs_or")
                logger.info(f"📄 找到 {len(article_divs)} 个文章div")
                
                if not article_divs:
                    logger.warning("⚠️ 未找到文章，可能已到达结果末尾")
                    break
                
                # 解析每个文章
                page_papers = []
                for div in article_divs:
                    if len(papers) >= limit:
                        break
                        
                    paper = self._parse_article_div(div)
                    if paper:
                        papers.append(paper)
                        page_papers.append(paper)
                        logger.debug(f"✅ 解析成功: {paper.title[:50]}... (引用: {paper.citations})")
                
                logger.info(f"📊 本页成功解析 {len(page_papers)} 篇论文")
                
                if len(papers) >= limit:
                    break
                
                # 延迟控制
                if start_idx < limit - 10:  # 不是最后一页
                    logger.debug(f"⏳ 等待 {self.request_delay} 秒...")
                    await asyncio.sleep(self.request_delay)
                
            except Exception as e:
                logger.error(f"❌ 第{start_idx//10 + 1}页搜索失败: {e}")
                continue
        
        logger.info(f"🎉 ScholarDock搜索完成: 共获得 {len(papers)} 篇论文")
        return papers

# 异步使用示例
async def test_scholar_dock():
    """测试ScholarDock爬虫"""
    async with ScholarDockSpider() as spider:
        papers = await spider.search("machine learning", limit=20)
        print(f"找到 {len(papers)} 篇论文")
        for paper in papers[:3]:
            print(f"- {paper.title} ({paper.year}, 引用: {paper.citations})")

if __name__ == "__main__":
    asyncio.run(test_scholar_dock())