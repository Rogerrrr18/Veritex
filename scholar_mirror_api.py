#!/usr/bin/env python3
"""
Google Scholar镜像API客户端 - 基于thesisCrawl项目策略
使用镜像网站绕过Google Scholar的访问限制和CAPTCHA问题
"""
import asyncio
import aiohttp
import time
import random
import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from dataclasses import dataclass

# 配置日志
logger = logging.getLogger(__name__)

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
    citations: int
    source: str
    relevance_score: float = 1.0

class ScholarMirrorAPI:
    """Google Scholar镜像API客户端 - 稳定的访问方案"""
    
    def __init__(self):
        # 镜像网站列表 - 基于实时状态检查器的可用镜像
        self.mirror_urls = [
            "https://scholar.hacks.tools/scholar",  # 主要镜像（美国）
            "https://scholar.linkedbus.com/scholar",  # 备用镜像1（中国）
            "https://sc.panda985.com/scholar",  # 备用镜像2（中国）
            "https://scholar.google.com.hk/scholar",  # 香港官方站点
        ]
        
        self.current_mirror = 0
        self.session = None
        self.last_request_time = 0
        self.min_delay = 2.0  # 最小延迟2秒
        self.consecutive_failures = 0
        self.max_failures = 3
        
        # User-Agent池 - 模拟真实浏览器
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        
    async def _get_session(self):
        """获取异步HTTP会话"""
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                headers=headers, 
                timeout=timeout,
                connector=aiohttp.TCPConnector(ssl=False)  # 允许不安全连接
            )
        return self.session
    
    async def _apply_delay(self):
        """应用智能延迟策略"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            delay = self.min_delay - time_since_last + random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)
        
        # 额外的随机延迟，避免被识别为机器人
        extra_delay = random.uniform(1.0, 2.0)
        await asyncio.sleep(extra_delay)
        
        self.last_request_time = time.time()
    
    def _get_current_mirror_url(self) -> str:
        """获取当前镜像URL"""
        return self.mirror_urls[self.current_mirror]
    
    def _switch_mirror(self):
        """切换到下一个镜像"""
        self.current_mirror = (self.current_mirror + 1) % len(self.mirror_urls)
        logger.info(f"🔄 切换到镜像网站: {self._get_current_mirror_url()}")
    
    async def search(self, query: str, limit: int = 20) -> List[Paper]:
        """搜索学术文献 - 使用镜像网站"""
        papers = []
        
        try:
            await self._apply_delay()
            session = await self._get_session()
            
            # 构建搜索URL - 使用标准Google Scholar格式
            base_url = self._get_current_mirror_url()
            search_url = f"{base_url}?q={query}&hl=en&as_sdt=0,33&start=0"
            
            logger.info(f"🔍 使用镜像搜索: {query}")
            logger.info(f"🌐 镜像URL: {base_url}")
            
            max_retries = len(self.mirror_urls)
            for attempt in range(max_retries):
                try:
                    async with session.get(search_url) as response:
                        if response.status == 200:
                            html_content = await response.text()
                            papers = self._parse_results(html_content, limit)
                            
                            if papers:
                                self.consecutive_failures = 0
                                logger.info(f"✅ 镜像搜索成功，获得 {len(papers)} 篇论文")
                                return papers
                            else:
                                logger.warning("⚠️ 镜像返回空结果，可能需要切换镜像")
                        
                        elif response.status == 429:
                            logger.warning(f"⚠️ 镜像访问限制 (429)，切换到下一个镜像")
                        
                        else:
                            logger.warning(f"⚠️ 镜像响应错误: {response.status}")
                
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ 镜像访问超时，尝试下一个镜像")
                except Exception as e:
                    logger.warning(f"⚠️ 镜像访问错误: {e}")
                
                # 失败后切换镜像
                if attempt < max_retries - 1:
                    self._switch_mirror()
                    base_url = self._get_current_mirror_url()
                    search_url = f"{base_url}?q={query}&hl=en&as_sdt=0,33&start=0"
                    await asyncio.sleep(random.uniform(3.0, 6.0))  # 切换镜像后等待
            
            self.consecutive_failures += 1
            logger.error(f"❌ 所有镜像都无法访问，连续失败 {self.consecutive_failures} 次")
            
        except Exception as e:
            logger.error(f"❌ 镜像搜索严重错误: {e}")
        
        return papers
    
    def _parse_results(self, html_content: str, limit: int) -> List[Paper]:
        """解析搜索结果HTML - 基于thesisCrawl的解析逻辑"""
        papers = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找结果条目 - 使用thesisCrawl的CSS选择器
            items = soup.find_all('div', class_="gs_r gs_or gs_scl")
            
            for i, item in enumerate(items[:limit]):
                try:
                    paper = self._parse_single_result(item, i)
                    if paper:
                        papers.append(paper)
                except Exception as e:
                    logger.debug(f"解析单个结果失败: {e}")
                    continue
            
            logger.info(f"📄 成功解析 {len(papers)} 篇论文")
            
        except Exception as e:
            logger.error(f"解析搜索结果失败: {e}")
        
        return papers
    
    def _parse_single_result(self, item, index: int) -> Optional[Paper]:
        """解析单个搜索结果 - 基于thesisCrawl的解析逻辑"""
        try:
            # 标题
            title = None
            if item.find('h3', class_='gs_rt') is not None:
                title = item.find('h3', class_='gs_rt').text.strip()
            
            if not title:
                return None
            
            # 作者和类型信息
            author = None
            pub_type = None
            year = None
            
            if item.find('div', class_='gs_a') is not None:
                author_and_type = item.find('div', class_='gs_a').text.strip()
                if '-' in author_and_type:
                    parts = author_and_type.split('-')
                    author = parts[0].strip()
                    if len(parts) > 1:
                        type_part = parts[1]
                        pub_type = type_part.split(',')[0].strip() if ',' in type_part else type_part.strip()
                        # 提取年份
                        year_match = re.search(r'\d{4}', type_part)
                        if year_match:
                            year = int(year_match.group())
            
            # 处理作者列表
            authors = []
            if author:
                # 简单分割作者，可根据需要改进
                authors = [a.strip() for a in author.replace('，', ',').split(',') if a.strip()]
            
            # 摘要
            abstract = ""
            if item.find('div', class_='gs_rs') is not None:
                abstract = item.find('div', class_='gs_rs').text.strip()
            
            # 引用数
            citations = 0
            if item.find('div', class_='gs_fl gs_flb') is not None:
                cite_link = item.find('div', class_='gs_fl gs_flb').find('a', href=lambda href: href and '/scholar?cites=' in href)
                if cite_link:
                    cite_text = cite_link.text.strip()
                    # 提取引用数字
                    cite_match = re.search(r'被引用\s*(\d+)', cite_text)
                    if not cite_match:
                        cite_match = re.search(r'(\d+)', cite_text)
                    if cite_match:
                        citations = int(cite_match.group(1))
            
            # 链接
            url = ""
            if item.find('h3', class_='gs_rt') is not None:
                link_element = item.find('h3', class_='gs_rt').find('a')
                if link_element:
                    url = link_element.get('href', '')
            
            # 创建Paper对象
            paper = Paper(
                title=title,
                authors=authors,
                abstract=abstract[:300] + "..." if len(abstract) > 300 else abstract,
                year=year,
                journal=pub_type or "",
                url=url,
                doi=None,  # 镜像通常不提供DOI
                citations=citations,
                source='scholar_mirror',
                relevance_score=1.0 - (index * 0.1)
            )
            
            return paper
            
        except Exception as e:
            logger.debug(f"解析论文详情失败: {e}")
            return None
    
    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def is_available(self) -> bool:
        """检查镜像是否可用"""
        return self.consecutive_failures < self.max_failures