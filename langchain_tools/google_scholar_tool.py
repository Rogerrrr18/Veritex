"""
Google Scholar MCP工具
基于LangChain BaseTool和官方MCP标准
"""
import asyncio
import aiohttp
import json
import re
from typing import Dict, List, Any, Optional, Type
from urllib.parse import quote_plus, urljoin
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class GoogleScholarSearchInput(BaseModel):
    """Google Scholar搜索输入模式"""
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=10, description="最大结果数")
    year_from: Optional[int] = Field(default=None, description="起始年份")
    year_to: Optional[int] = Field(default=None, description="结束年份")


class GoogleScholarTool(BaseTool):
    """Google Scholar搜索工具"""
    
    name: str = "google_scholar_search"
    description: str = "搜索Google Scholar学术论文"
    args_schema: Type[BaseModel] = GoogleScholarSearchInput
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://scholar.google.com"
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    def _extract_paper_info(self, result_div) -> Dict[str, Any]:
        """从搜索结果div中提取论文信息"""
        paper = {}
        
        # 提取标题和链接
        title_elem = result_div.find('h3', class_='gs_rt')
        if title_elem:
            link_elem = title_elem.find('a')
            if link_elem:
                paper['title'] = link_elem.get_text(strip=True)
                paper['url'] = link_elem.get('href', '')
            else:
                paper['title'] = title_elem.get_text(strip=True)
                paper['url'] = ''
        
        # 提取作者和发表信息
        authors_elem = result_div.find('div', class_='gs_a')
        if authors_elem:
            authors_text = authors_elem.get_text(strip=True)
            # 解析作者、期刊/会议、年份
            parts = authors_text.split(' - ')
            if len(parts) >= 2:
                paper['authors'] = parts[0]
                paper['venue'] = parts[1]
                if len(parts) >= 3:
                    year_match = re.search(r'\d{4}', parts[2])
                    if year_match:
                        paper['year'] = int(year_match.group())
        
        # 提取摘要
        abstract_elem = result_div.find('div', class_='gs_rs')
        if abstract_elem:
            paper['abstract'] = abstract_elem.get_text(strip=True)
        
        # 提取引用数
        citation_elem = result_div.find('div', class_='gs_fl')
        if citation_elem:
            citation_link = citation_elem.find('a', string=re.compile('Cited by'))
            if citation_link:
                citation_text = citation_link.get_text()
                citation_match = re.search(r'(\d+)', citation_text)
                if citation_match:
                    paper['citations'] = int(citation_match.group(1))
        
        return paper
    
    async def _search_papers(self, query: str, max_results: int = 10, 
                           year_from: Optional[int] = None, 
                           year_to: Optional[int] = None) -> List[Dict[str, Any]]:
        """执行论文搜索"""
        try:
            from bs4 import BeautifulSoup
            
            session = await self._get_session()
            
            # 构建搜索URL
            search_url = f"{self.base_url}/scholar"
            params = {
                'q': query,
                'hl': 'en',
                'num': min(max_results, 20)  # Google Scholar最多返回20个结果
            }
            
            # 添加年份过滤
            if year_from or year_to:
                year_filter = ""
                if year_from:
                    year_filter += f"after:{year_from}"
                if year_to:
                    if year_filter:
                        year_filter += f" before:{year_to}"
                    else:
                        year_filter += f"before:{year_to}"
                params['as_ylo'] = year_from if year_from else ""
                params['as_yhi'] = year_to if year_to else ""
            
            # 发送请求
            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 查找搜索结果
                results = []
                result_divs = soup.find_all('div', class_='gs_r gs_or gs_scl')
                
                for div in result_divs[:max_results]:
                    paper = self._extract_paper_info(div)
                    if paper.get('title'):
                        results.append(paper)
                
                return results
                
        except Exception as e:
            print(f"Google Scholar搜索错误: {e}")
            return []
    
    async def _arun(self, query: str, max_results: int = 10, 
                   year_from: Optional[int] = None, 
                   year_to: Optional[int] = None) -> str:
        """异步运行搜索"""
        papers = await self._search_papers(query, max_results, year_from, year_to)
        
        # 格式化结果
        if not papers:
            return json.dumps({
                "status": "success",
                "query": query,
                "total_results": 0,
                "papers": []
            }, ensure_ascii=False, indent=2)
        
        # 清理和验证数据
        cleaned_papers = []
        for paper in papers:
            cleaned_paper = {
                "title": paper.get('title', '未知标题'),
                "authors": paper.get('authors', ''),
                "venue": paper.get('venue', ''),
                "year": paper.get('year'),
                "abstract": paper.get('abstract', ''),
                "url": paper.get('url', ''),
                "citations": paper.get('citations', 0)
            }
            cleaned_papers.append(cleaned_paper)
        
        result = {
            "status": "success",
            "query": query,
            "total_results": len(cleaned_papers),
            "papers": cleaned_papers
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    def _run(self, query: str, max_results: int = 10, 
            year_from: Optional[int] = None, 
            year_to: Optional[int] = None) -> str:
        """同步运行搜索"""
        return asyncio.run(self._arun(query, max_results, year_from, year_to))
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()


# 创建工具实例
google_scholar_tool = GoogleScholarTool()


# 测试函数
async def test_google_scholar():
    """测试Google Scholar工具"""
    print("测试Google Scholar搜索...")
    
    result = await google_scholar_tool._arun(
        query="machine learning",
        max_results=5
    )
    
    print(result)
    await google_scholar_tool.close()


if __name__ == "__main__":
    asyncio.run(test_google_scholar())