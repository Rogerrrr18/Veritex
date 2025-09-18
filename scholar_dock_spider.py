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
import os
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
    1. 直接HTML解析，绕过传统库限制
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
        
        # 请求配置 (采用ScholarDock-master的成功经验)
        self.base_delay = 5.0      # 基础延迟时间（采用ScholarDock的5.0s策略）
        self.max_delay = 8.0       # 最大延迟时间（在ScholarDock基础上增加随机性）
        self.max_retries = 3       # 保持ScholarDock的3次重试
        self.timeout = 30          # 采用ScholarDock的30秒超时
        
        # 🔧 优化：搜索超时配置（基于ScholarDock-master经验优化）
        self.search_timeout = 180  # 单次搜索最大超时3分钟（ScholarDock推荐）
        self.captcha_timeout = 30   # CAPTCHA等待30秒（完全采用ScholarDock策略）
        self.max_pages_before_timeout = 3  # 最多搜索3页（降低被检测风险）
        
        self.session = None
        self.driver = None
        
        # 🔧 新增：服务器自动化优化 - 采用ScholarDock的智能禁用机制
        self.consecutive_captcha_count = 0    # 连续遇到CAPTCHA的次数
        self.max_captcha_tolerance = 1        # 降低容忍度到1次（更快触发保护）
        self.is_temporarily_disabled = False  # 是否临时禁用
        self.disable_until = 0               # 禁用到什么时间
        self.disable_duration = 7200         # 禁用2小时（7200秒，参考ScholarDock策略）
        
        logger.info(f"🚀 ScholarDock Spider初始化: 延迟={self.base_delay}-{self.max_delay}s, CAPTCHA超时={self.captcha_timeout}s, 最大页数={self.max_pages_before_timeout}")
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = requests.Session()
        
        # 🔧 配置代理支持
        http_proxy = os.getenv('HTTP_PROXY')
        https_proxy = os.getenv('HTTPS_PROXY')
        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies['http'] = http_proxy
                logger.info(f"🌐 HTTP代理已配置: {http_proxy}")
            if https_proxy:
                proxies['https'] = https_proxy
                logger.info(f"🔒 HTTPS代理已配置: {https_proxy}")
            self.session.proxies.update(proxies)
        
        # 设置请求头，模拟真实浏览器（参考成功库的策略）
        self.user_agents = [
            # Chrome浏览器
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            # Firefox浏览器
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
            # Safari浏览器
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        
        # 建立基础请求头配置（参考sort-google-scholar-dev的配置）
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            self.session.close()
        if self.driver:
            self.driver.quit()
    
    def _get_dynamic_headers(self):
        """动态生成请求头，模拟真实浏览器行为（参考成功库策略）"""
        import random
        
        # 随机选择User-Agent
        user_agent = random.choice(self.user_agents)
        
        # 构建动态请求头
        headers = self.base_headers.copy()
        headers['User-Agent'] = user_agent
        
        # 根据User-Agent类型调整其他请求头
        if 'Firefox' in user_agent:
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
            headers['Accept-Language'] = 'en-US,en;q=0.5'
        elif 'Safari' in user_agent:
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            headers['Accept-Language'] = 'en-us'
        else:  # Chrome
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            headers['Accept-Language'] = 'en-US,en;q=0.9'
        
        return headers
    
    async def _smart_delay(self, page_number: int = 1, is_retry: bool = False):
        """基于ScholarDock-master成功经验的智能延迟策略"""
        import random
        
        # 基于ScholarDock的5.0秒延迟策略，增加随机性
        base_delay = random.uniform(self.base_delay, self.max_delay)  # 5.0-8.0秒基础延迟
        
        # 重试时增加更长的额外延迟（参考ScholarDock处理）
        if is_retry:
            base_delay += random.uniform(5.0, 10.0)  # 重试时额外增加5-10秒
        
        # 页数增加时增加延迟（避免被检测为批量行为）
        if page_number > 1:
            page_factor = min(page_number * 2.0, 10.0)  # 每页增加2秒，最多增加10秒
            base_delay += page_factor
        
        # 添加随机抖动，模拟人类行为
        jitter = random.uniform(0.8, 1.5)  # 增加抖动范围
        final_delay = base_delay * jitter
        
        # 确保最小延迟不低于ScholarDock的基准
        final_delay = max(final_delay, 5.0)
        
        logger.debug(f"⏳ 智能延迟 {final_delay:.2f}秒 (页数={page_number}, 重试={is_retry})")
        await asyncio.sleep(final_delay)
    
    def _create_search_url(self, query: str, start: int = 0, 
                          start_year: Optional[int] = None, 
                          end_year: Optional[int] = None) -> str:
        """构建搜索URL"""
        import urllib.parse
        
        # 🔧 优化：先进行中文查询优化，提高中文论文比例
        enhanced_query = self._enhance_chinese_query(query)
        
        # 简化复杂的布尔查询 - Google Scholar对复杂嵌套查询支持有限
        simplified_query = self._simplify_boolean_query(enhanced_query)
        
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
            if len(query) > 150 or query.count('(') > 2:  # 🔧 降低复杂度阈值，更早触发简化
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
    
    def _enhance_chinese_query(self, query: str) -> str:
        """优化中文查询，提高中文论文搜索比例"""
        import re
        
        # 检测是否包含中文字符
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        has_chinese = bool(chinese_pattern.search(query))
        
        if has_chinese:
            # 为中文查询添加地域和语言限制，提高中文论文比例
            enhanced_query = f'({query}) AND (中国 OR 中文 OR Chinese OR China)'
            logger.info(f"🔧 中文查询优化: {query} -> {enhanced_query}")
            return enhanced_query
        
        return query
    
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
        """使用Selenium获取内容，采用ScholarDock的CAPTCHA处理策略"""
        if not SELENIUM_AVAILABLE:
            logger.warning("🔧 Selenium不可用，服务器环境下跳过")
            return None
            
        try:
            if not self.driver:
                self.driver = self._setup_selenium_driver()
                
            if not self.driver:
                logger.warning("🔧 无法初始化Selenium驱动，服务器环境下跳过")
                return None
            
            logger.info(f"🌐 使用Selenium访问: {url}")
            self.driver.get(url)
            
            # 等待页面加载
            await asyncio.sleep(3)
            
            body_element = self._get_element_safe(self.driver, "//body")
            if not body_element:
                return None
                
            content = body_element.get_attribute('innerHTML')
            
            # 检查是否需要解决CAPTCHA
            if any(keyword in content.lower() for keyword in self.robot_keywords):
                logger.warning("🚨 Selenium检测到CAPTCHA，采用ScholarDock策略处理")
                self._handle_captcha_detected()
                
                # 🔧 采用ScholarDock的30秒等待策略
                logger.info(f"💡 等待{self.captcha_timeout}秒让用户解决CAPTCHA（ScholarDock策略）")
                await asyncio.sleep(self.captcha_timeout)
                
                # 重新获取页面内容
                try:
                    self.driver.get(url)
                    await asyncio.sleep(3)
                    body_element = self._get_element_safe(self.driver, "//body")
                    if body_element:
                        content = body_element.get_attribute('innerHTML')
                        # 检查CAPTCHA是否已解决
                        if not any(keyword in content.lower() for keyword in self.robot_keywords):
                            logger.info("✅ CAPTCHA已解决，继续搜索")
                            self._handle_successful_request()
                            return content.encode('utf-8')
                        else:
                            logger.warning("⚠️ CAPTCHA仍未解决")
                            return None
                except Exception as e:
                    logger.error(f"重新获取页面失败: {e}")
                    return None
            
            # 如果没有CAPTCHA，标记为成功
            self._handle_successful_request()
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
    
    def _check_if_disabled(self) -> bool:
        """检查是否因连续CAPTCHA而临时禁用"""
        current_time = time.time()
        if self.is_temporarily_disabled and current_time < self.disable_until:
            remaining_minutes = int((self.disable_until - current_time) / 60)
            logger.info(f"⏸️ ScholarDock临时禁用中，剩余{remaining_minutes}分钟")
            return True
        elif self.is_temporarily_disabled and current_time >= self.disable_until:
            # 禁用期已过，重新启用
            self.is_temporarily_disabled = False
            self.consecutive_captcha_count = 0
            logger.info("🔓 ScholarDock禁用期已过，重新启用")
            return False
        return False
    
    def _handle_captcha_detected(self):
        """处理CAPTCHA检测（智能策略）"""
        self.consecutive_captcha_count += 1
        logger.warning(f"🚨 CAPTCHA检测计数: {self.consecutive_captcha_count}/{self.max_captcha_tolerance}")
        
        # 不再立即禁用，而是采用渐进式处理
        if self.consecutive_captcha_count < self.max_captcha_tolerance:
            logger.info(f"🔄 CAPTCHA处理: 将等待更长时间后重试 (第{self.consecutive_captcha_count}次)")
            return False  # 表示可以继续尝试
        else:
            # 达到容忍上限，临时禁用
            import time
            self.is_temporarily_disabled = True
            self.disable_until = time.time() + self.disable_duration
            disable_minutes = self.disable_duration // 60
            logger.warning(f"🚫 ScholarDock连续遇到{self.consecutive_captcha_count}次CAPTCHA，临时禁用{disable_minutes}分钟")
            logger.info("💡 系统将自动使用其他数据源进行搜索")
            return True  # 表示需要停止
    
    def _handle_successful_request(self):
        """处理成功请求，重置CAPTCHA计数器"""
        if self.consecutive_captcha_count > 0:
            logger.info(f"✅ ScholarDock请求成功，重置CAPTCHA计数器（之前: {self.consecutive_captcha_count}）")
            self.consecutive_captcha_count = 0
    
    async def _smart_request_with_retry(self, url: str, page_number: int = 1) -> Optional[str]:
        """基于ScholarDock成功经验的智能请求机制"""
        for retry_count in range(self.max_retries):
            try:
                # 应用智能延迟
                await self._smart_delay(page_number, is_retry=(retry_count > 0))
                
                # 获取动态请求头
                headers = self._get_dynamic_headers()
                
                # 发送请求
                response = self.session.get(url, headers=headers, timeout=self.timeout)
                content = response.content
                
                if response.status_code == 200:
                    content_str = content.decode('utf-8', errors='ignore')
                    
                    # 检查CAPTCHA
                    if any(keyword in content_str.lower() for keyword in self.robot_keywords):
                        logger.warning(f"🚨 第{retry_count + 1}次尝试检测到CAPTCHA")
                        
                        if retry_count < self.max_retries - 1:
                            # 🔧 采用ScholarDock的更长重试延迟策略
                            extra_delay = 10.0 + (retry_count * 10.0)  # 10s, 20s, 30s递增延迟
                            logger.info(f"⏳ CAPTCHA重试延迟: {extra_delay}秒（ScholarDock策略）")
                            await asyncio.sleep(extra_delay)
                            continue
                        else:
                            # 最后一次尝试也失败，尝试Selenium后备
                            logger.warning("🔄 所有重试失败，尝试Selenium后备方案")
                            selenium_content = await self._get_content_with_selenium(url)
                            if selenium_content:
                                return selenium_content.decode('utf-8', errors='ignore')
                            
                            # Selenium也失败
                            should_stop = self._handle_captcha_detected()
                            if should_stop:
                                return None
                            return None
                    else:
                        # 成功获取内容
                        self._handle_successful_request()
                        return content_str
                        
                else:
                    logger.warning(f"HTTP状态码: {response.status_code}, 重试...")
                    
            except Exception as e:
                logger.warning(f"请求失败 (尝试 {retry_count + 1}/{self.max_retries}): {e}")
                
                if retry_count < self.max_retries - 1:
                    # 网络错误时也应用更长的延迟
                    await asyncio.sleep(5.0 + (retry_count * 5.0))  # 5s, 10s, 15s递增延迟
                    continue
        
        # 所有重试都失败
        logger.error(f"❌ 请求彻底失败: {url}")
        return None
    
    async def search(self, query: str, limit: int = 50,
                    start_year: Optional[int] = None,
                    end_year: Optional[int] = None) -> List[ScholarDockPaper]:
        """
        搜索Google Scholar（服务器自动化优化版）
        
        Args:
            query: 搜索查询
            limit: 结果数量限制 (最多1000)
            start_year: 起始年份
            end_year: 结束年份
            
        Returns:
            论文列表
        """
        
        # 🔧 优化：检查是否临时禁用
        if self._check_if_disabled():
            logger.warning("⏸️ ScholarDock当前临时禁用，返回空结果")
            return []
        
        # 限制最大结果数
        limit = min(limit, 1000)
        papers = []
        
        logger.info(f"🔍 ScholarDock搜索开始: {query} (目标: {limit}条)")
        
        # 🔧 新增：整体搜索超时机制
        search_start_time = asyncio.get_event_loop().time()
        
        # 按10条一页进行搜索
        for start_idx in range(0, limit, 10):
            try:
                # 🔧 检查超时
                current_time = asyncio.get_event_loop().time()
                if current_time - search_start_time > self.search_timeout:
                    logger.warning(f"⏰ 搜索超时({self.search_timeout}秒)，返回已获得的 {len(papers)} 篇论文")
                    break
                
                # 🔧 检查页数限制，避免无限等待
                if start_idx >= self.max_pages_before_timeout * 10:
                    logger.info(f"📊 已搜索 {self.max_pages_before_timeout} 页，为避免被限制停止搜索")
                    break
                url = self._create_search_url(query, start_idx, start_year, end_year)
                logger.info(f"📖 获取第{start_idx//10 + 1}页: {url}")
                
                # 使用智能请求机制
                page_number = start_idx//10 + 1
                content_str = await self._smart_request_with_retry(url, page_number)
                
                if content_str is None:
                    logger.warning(f"⚠️ 第{page_number}页请求失败，跳过")
                    continue
                
                # 使用BeautifulSoup解析HTML
                soup = BeautifulSoup(content_str, 'html.parser')
                
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
                
            except Exception as e:
                logger.error(f"❌ 第{start_idx//10 + 1}页搜索失败: {e}")
                continue
        
        logger.info(f"🎉 ScholarDock搜索完成: 共获得 {len(papers)} 篇论文")
        
        # 🔧 新增：中文论文优先排序，确保返回足够的中文论文
        chinese_papers, english_papers = self._separate_chinese_papers(papers)
        
        # 优先返回中文论文，不足时补充英文论文
        final_papers = chinese_papers + english_papers
        final_papers = final_papers[:limit]  # 限制总数
        
        chinese_count = len([p for p in final_papers if self._is_chinese_paper(p)])
        total_count = len(final_papers)
        chinese_ratio = (chinese_count / total_count * 100) if total_count > 0 else 0
        
        logger.info(f"📊 最终结果: 共{total_count}篇，中文论文{chinese_count}篇 ({chinese_ratio:.1f}%)")
        
        return final_papers
    
    def _is_chinese_paper(self, paper: 'ScholarDockPaper') -> bool:
        """判断是否为中文论文"""
        import re
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        
        # 检查标题和作者是否包含中文
        title_has_chinese = bool(chinese_pattern.search(paper.title))
        authors_has_chinese = any(chinese_pattern.search(author) for author in paper.authors)
        
        return title_has_chinese or authors_has_chinese
    
    def _separate_chinese_papers(self, papers: List['ScholarDockPaper']) -> tuple:
        """分离中文和英文论文"""
        chinese_papers = []
        english_papers = []
        
        for paper in papers:
            if self._is_chinese_paper(paper):
                chinese_papers.append(paper)
            else:
                english_papers.append(paper)
        
        return chinese_papers, english_papers

# 异步使用示例
async def test_scholar_dock():
    """测试ScholarDock爬虫"""
    async with ScholarDockSpider() as spider:
        # 测试中文查询
        papers = await spider.search("机器学习", limit=20)
        print(f"🔍 中文搜索结果: 找到 {len(papers)} 篇论文")
        
        chinese_count = sum(1 for paper in papers if spider._is_chinese_paper(paper))
        print(f"📊 中文论文数量: {chinese_count}/{len(papers)} ({chinese_count/len(papers)*100:.1f}%)")
        
        print("\n📄 前5篇论文:")
        for i, paper in enumerate(papers[:5]):
            is_chinese = "🇨🇳" if spider._is_chinese_paper(paper) else "🇺🇸"
            print(f"{i+1}. {is_chinese} {paper.title[:60]}... (引用: {paper.citations})")

if __name__ == "__main__":
    asyncio.run(test_scholar_dock())