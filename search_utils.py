"""
搜索工具模块 - Paper God通用搜索和数据处理工具
包含MCP客户端管理、缓存机制、数据转换等通用功能
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SearchCache:
    """搜索缓存管理"""
    data: Dict[str, Any] = field(default_factory=dict)
    expiry: Dict[str, datetime] = field(default_factory=dict)
    ttl: timedelta = field(default=timedelta(minutes=30))
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if key in self.data and key in self.expiry:
            if datetime.now() < self.expiry[key]:
                return self.data[key]
            else:
                # 过期删除
                del self.data[key]
                del self.expiry[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存数据"""
        self.data[key] = value
        self.expiry[key] = datetime.now() + self.ttl
    
    def clear(self) -> None:
        """清除所有缓存"""
        self.data.clear()
        self.expiry.clear()

class SearchResultProcessor:
    """搜索结果处理器"""
    
    @staticmethod
    def normalize_author_name(name: str) -> str:
        """标准化作者姓名"""
        if not name:
            return ""
        # 移除多余空格和特殊字符
        return ' '.join(name.strip().split())
    
    @staticmethod
    def extract_doi(text: str) -> Optional[str]:
        """从文本中提取DOI"""
        import re
        doi_pattern = r'10\.\d{4,}/[^\s]+'
        match = re.search(doi_pattern, text)
        return match.group() if match else None
    
    @staticmethod
    def calculate_relevance_score(paper: Dict[str, Any], keywords: List[str]) -> float:
        """计算论文相关性得分"""
        score = 0.0
        
        # 标题匹配权重最高
        title = (paper.get('title', '') or '').lower()
        for keyword in keywords:
            if keyword.lower() in title:
                score += 3.0
        
        # 摘要匹配
        abstract = (paper.get('abstract', '') or '').lower()
        for keyword in keywords:
            if keyword.lower() in abstract:
                score += 1.0
        
        # 引用数权重
        citations = paper.get('citation_count', 0) or 0
        if citations > 100:
            score += 2.0
        elif citations > 10:
            score += 1.0
        
        # 发布年份权重（近期论文优先）
        year = paper.get('publication_year', 0) or 0
        current_year = datetime.now().year
        if year >= current_year - 2:
            score += 1.5
        elif year >= current_year - 5:
            score += 1.0
        
        return score

    @staticmethod
    def deduplicate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重论文列表"""
        seen_titles = set()
        seen_dois = set()
        unique_papers = []
        
        for paper in papers:
            title = (paper.get('title', '') or '').lower().strip()
            doi = paper.get('doi', '') or ''
            
            # 跳过空标题
            if not title:
                continue
            
            # DOI去重优先
            if doi and doi not in seen_dois:
                seen_dois.add(doi)
                unique_papers.append(paper)
            # 标题去重
            elif not doi and title not in seen_titles:
                seen_titles.add(title)
                unique_papers.append(paper)
        
        return unique_papers

def format_search_response(papers: List[Dict[str, Any]], 
                          query: str, 
                          total_found: int = None,
                          source: str = "Paper God") -> Dict[str, Any]:
    """格式化搜索响应"""
    return {
        "query": query,
        "source": source,
        "total_results": total_found or len(papers),
        "returned_results": len(papers),
        "papers": papers,
        "timestamp": datetime.now().isoformat(),
        "status": "success"
    }

def validate_search_params(query: str, 
                          max_results: int = 50,
                          min_query_length: int = 2) -> Dict[str, Any]:
    """验证搜索参数"""
    errors = []
    
    if not query or len(query.strip()) < min_query_length:
        errors.append(f"查询关键词长度至少需要{min_query_length}个字符")
    
    if max_results <= 0 or max_results > 200:
        errors.append("结果数量必须在1-200之间")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "cleaned_query": query.strip() if query else "",
        "safe_max_results": min(max(max_results, 1), 200)
    }