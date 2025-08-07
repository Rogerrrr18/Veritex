"""
通用MCP引擎 - 零代码集成任何学术搜索API
"""
import json
import asyncio
import logging
import aiohttp
import feedparser
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import re
import os
from difflib import SequenceMatcher

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StandardPaper:
    """标准化论文数据结构"""
    id: str
    title: str
    abstract: Optional[str] = None
    authors: List[Dict[str, str]] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    citations: Optional[int] = None
    doi: Optional[str] = None
    categories: List[str] = None
    source: str = "unknown"
    relevance_score: float = 0.0
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.categories is None:
            self.categories = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

class DataTransformer:
    """数据转换器 - 处理不同API的数据格式差异"""
    
    @staticmethod
    def extract_names(authors_data: Any) -> List[Dict[str, str]]:
        """从各种作者数据格式中提取姓名"""
        if not authors_data:
            return []
        
        authors = []
        if isinstance(authors_data, list):
            for author in authors_data:
                if isinstance(author, dict):
                    if 'name' in author:
                        authors.append({"name": author['name']})
                    elif 'given' in author and 'family' in author:
                        authors.append({"name": f"{author['given']} {author['family']}"})
                elif isinstance(author, str):
                    authors.append({"name": author})
                elif hasattr(author, 'name'):
                    authors.append({"name": author.name})
        
        return authors
    
    @staticmethod
    def extract_author_names(authors_data: Any) -> List[Dict[str, str]]:
        """提取Semantic Scholar格式的作者名"""
        if not authors_data:
            return []
        
        return [{"name": author.get('name', 'Unknown')} for author in authors_data if isinstance(author, dict)]
    
    @staticmethod
    def extract_given_family_names(authors_data: Any) -> List[Dict[str, str]]:
        """提取CrossRef格式的作者名"""
        if not authors_data:
            return []
        
        authors = []
        for author in authors_data:
            if isinstance(author, dict):
                given = author.get('given', '')
                family = author.get('family', '')
                name = f"{given} {family}".strip() or 'Unknown'
                authors.append({"name": name})
        
        return authors
    
    @staticmethod
    def extract_terms(tags_data: Any) -> List[str]:
        """从标签数据中提取术语"""
        if not tags_data:
            return []
        
        if isinstance(tags_data, list):
            return [tag.get('term', '') if isinstance(tag, dict) else str(tag) for tag in tags_data]
        
        return []
    
    @staticmethod
    def extract_from_id(id_data: str) -> str:
        """从ID中提取特定部分"""
        if not id_data:
            return ""
        
        # 提取arXiv ID
        if "/" in id_data:
            return id_data.split("/")[-1]
        
        return id_data
    
    @staticmethod
    def extract_first_element(data: Any) -> str:
        """提取第一个元素"""
        if isinstance(data, list) and data:
            return str(data[0])
        return str(data) if data else ""

class GenericMCPClient:
    """通用MCP客户端 - 自动适配任何学术搜索API"""
    
    def __init__(self, config_file: str = "universal_mcp_config.json"):
        """
        初始化通用MCP客户端
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.transformer = DataTransformer()
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
                logger.info(f"✅ 加载通用MCP配置: {len(self.config.get('mcpServices', {}))} 个服务")
        except FileNotFoundError:
            logger.error(f"❌ 配置文件未找到: {self.config_file}")
            self.config = {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ 配置文件JSON格式错误: {e}")
            self.config = {}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(
                total=self.config.get("global_settings", {}).get("timeout_seconds", 30)
            )
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    def _build_auth_headers(self, service_config: Dict[str, Any]) -> Dict[str, str]:
        """构建认证头"""
        headers = {}
        auth_config = service_config.get("auth", {})
        
        if auth_config.get("type") == "header":
            env_var = auth_config.get("env_var")
            if env_var:
                api_key = os.getenv(env_var)
                if api_key:
                    header_name = auth_config.get("header_name", "authorization")
                    headers[header_name] = api_key
        
        return headers
    
    def _build_search_params(self, service_config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """构建搜索参数"""
        search_config = service_config.get("search_config", {})
        param_mapping = search_config.get("param_mapping", {})
        additional_params = search_config.get("additional_params", {})
        
        # 映射标准参数
        params = {}
        for standard_param, actual_param in param_mapping.items():
            if standard_param in kwargs and kwargs[standard_param] is not None:
                params[actual_param] = kwargs[standard_param]
        
        # 添加额外参数
        params.update(additional_params)
        
        # 处理查询模板
        if "query" in kwargs:
            query = kwargs["query"]
            query_template = search_config.get("query_template")
            category_template = search_config.get("category_template")
            
            try:
                if kwargs.get("category") and category_template:
                    params[param_mapping.get("query", "query")] = category_template.format(
                        query=query, category=kwargs["category"]
                    )
                elif query_template:
                    params[param_mapping.get("query", "query")] = query_template.format(query=query)
            except KeyError as e:
                # 如果模板格式化失败，使用原始查询
                logger.warning(f"模板格式化失败: {e}, 使用原始查询")
                params[param_mapping.get("query", "query")] = query
        
        return params
    
    def _parse_field_path(self, data: Any, path: str) -> Any:
        """解析字段路径"""
        if not path or data is None:
            return data
        
        try:
            current = data
            for part in path.split('.'):
                if '[' in part and ']' in part:
                    # 处理数组索引，如 "date-parts[0][0]"
                    field_name = part.split('[')[0]
                    indices = re.findall(r'\[(\d+)\]', part)
                    
                    if field_name:
                        current = current[field_name]
                    
                    for index in indices:
                        current = current[int(index)]
                else:
                    current = current[part]
            
            return current
        except (KeyError, IndexError, TypeError):
            return None
    
    def _transform_paper_data(self, raw_data: Dict[str, Any], service_config: Dict[str, Any]) -> StandardPaper:
        """转换原始数据为标准论文格式"""
        response_config = service_config.get("response_config", {})
        field_mapping = response_config.get("field_mapping", {})
        transform_config = response_config.get("transform", {})
        
        # 提取基础字段
        paper_data = {}
        for standard_field, raw_field in field_mapping.items():
            value = self._parse_field_path(raw_data, raw_field)
            
            # 应用数据转换
            if standard_field in transform_config:
                transform_method = transform_config[standard_field]
                if hasattr(self.transformer, transform_method):
                    value = getattr(self.transformer, transform_method)(value)
            
            paper_data[standard_field] = value
        
        # 创建标准论文对象
        paper = StandardPaper(
            id=str(paper_data.get("id", "")),
            title=paper_data.get("title", ""),
            abstract=paper_data.get("abstract"),
            authors=paper_data.get("authors", []),
            year=self._extract_year(paper_data.get("year")),
            venue=paper_data.get("venue"),
            url=paper_data.get("url"),
            pdf_url=paper_data.get("pdf_url"),
            citations=self._extract_int(paper_data.get("citations")),
            doi=paper_data.get("doi"),
            categories=paper_data.get("categories", []),
            source=service_config.get("name", "unknown")
        )
        
        return paper
    
    def _extract_year(self, year_data: Any) -> Optional[int]:
        """提取年份"""
        if year_data is None:
            return None
        
        if isinstance(year_data, int):
            return year_data
        
        if isinstance(year_data, str):
            # 从日期字符串中提取年份
            year_match = re.search(r'(\d{4})', year_data)
            if year_match:
                return int(year_match.group(1))
        
        return None
    
    def _extract_int(self, data: Any) -> Optional[int]:
        """提取整数"""
        if data is None:
            return None
        
        try:
            return int(data)
        except (ValueError, TypeError):
            return None
    
    async def search_service(self, service_id: str, **kwargs) -> Dict[str, Any]:
        """
        搜索单个MCP服务
        
        Args:
            service_id: 服务ID
            **kwargs: 搜索参数
            
        Returns:
            搜索结果
        """
        try:
            service_config = self.config.get("mcpServices", {}).get(service_id)
            if not service_config:
                return {"success": False, "error": f"服务未找到: {service_id}", "papers": []}
            
            if not service_config.get("enabled", True):
                return {"success": False, "error": f"服务已禁用: {service_id}", "papers": []}
            
            session = await self._get_session()
            headers = self._build_auth_headers(service_config)
            params = self._build_search_params(service_config, **kwargs)
            
            base_url = service_config["base_url"]
            endpoint = service_config.get("search_config", {}).get("endpoint", "")
            url = f"{base_url}{endpoint}"
            
            method = service_config.get("method", "GET").upper()
            
            logger.info(f"🔍 搜索 {service_id}: {url} with params: {params}")
            
            async with session.request(method, url, params=params, headers=headers) as response:
                if response.status == 200:
                    # 根据响应格式解析数据
                    response_config = service_config.get("response_config", {})
                    format_type = response_config.get("format", "json")
                    
                    if format_type == "json":
                        data = await response.json()
                    elif format_type == "rss":
                        content = await response.text()
                        data = feedparser.parse(content)
                    else:
                        content = await response.text()
                        data = {"raw": content}
                    
                    # 提取论文数据
                    papers_path = response_config.get("papers_path", "")
                    raw_papers = self._parse_field_path(data, papers_path) if papers_path else data
                    
                    if not isinstance(raw_papers, list):
                        raw_papers = []
                    
                    # 转换为标准格式
                    papers = []
                    for raw_paper in raw_papers:
                        try:
                            paper = self._transform_paper_data(raw_paper, service_config)
                            papers.append(paper)
                        except Exception as e:
                            logger.warning(f"转换论文数据失败: {e}")
                            continue
                    
                    return {
                        "success": True,
                        "papers": papers,
                        "count": len(papers),
                        "source": service_id
                    }
                else:
                    error_msg = f"HTTP {response.status}"
                    return {"success": False, "error": error_msg, "papers": [], "source": service_id}
                    
        except Exception as e:
            logger.error(f"搜索服务 {service_id} 失败: {e}")
            return {"success": False, "error": str(e), "papers": [], "source": service_id}
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        if not text1 or not text2:
            return 0.0
        
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _deduplicate_papers(self, papers: List[StandardPaper]) -> List[StandardPaper]:
        """去重论文"""
        if not papers:
            return papers
        
        dedup_config = self.config.get("data_processing", {}).get("deduplication", {})
        if not dedup_config.get("enabled", True):
            return papers
        
        threshold = dedup_config.get("similarity_threshold", 0.85)
        unique_papers = []
        
        for paper in papers:
            is_duplicate = False
            
            for existing_paper in unique_papers:
                # 检查标题相似度
                title_similarity = self._calculate_similarity(paper.title, existing_paper.title)
                
                if title_similarity > threshold:
                    is_duplicate = True
                    # 保留引用数更多的版本
                    if (paper.citations or 0) > (existing_paper.citations or 0):
                        unique_papers.remove(existing_paper)
                        unique_papers.append(paper)
                    break
            
            if not is_duplicate:
                unique_papers.append(paper)
        
        logger.info(f"📝 去重：{len(papers)} -> {len(unique_papers)} 篇论文")
        return unique_papers
    
    async def search_multiple_sources(self, sources: List[str], **kwargs) -> Dict[str, Any]:
        """
        并行搜索多个数据源
        
        Args:
            sources: 数据源列表
            **kwargs: 搜索参数
            
        Returns:
            合并的搜索结果
        """
        try:
            # 并行搜索所有数据源
            search_tasks = [
                self.search_service(source, **kwargs) 
                for source in sources
            ]
            
            results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # 合并结果
            all_papers = []
            source_stats = {}
            errors = []
            
            for result in results:
                if isinstance(result, dict) and result.get("success"):
                    papers = result.get("papers", [])
                    source = result.get("source", "unknown")
                    source_stats[source] = len(papers)
                    all_papers.extend(papers)
                elif isinstance(result, dict):
                    errors.append(f"{result.get('source', 'unknown')}: {result.get('error', 'Unknown error')}")
                else:
                    errors.append(f"Exception: {str(result)}")
            
            # 去重
            unique_papers = self._deduplicate_papers(all_papers)
            
            # 排序（按相关性和引用数）
            unique_papers.sort(key=lambda p: (p.relevance_score, p.citations or 0), reverse=True)
            
            return {
                "success": True,
                "papers": [p.to_dict() for p in unique_papers],
                "total_count": len(unique_papers),
                "source_stats": source_stats,
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"多源搜索失败: {e}")
            return {"success": False, "error": str(e), "papers": []}
    
    async def search_with_strategy(self, strategy: str, query: str, **kwargs) -> Dict[str, Any]:
        """
        使用预定义策略搜索
        
        Args:
            strategy: 搜索策略名称
            query: 搜索查询
            **kwargs: 其他搜索参数
            
        Returns:
            搜索结果
        """
        strategies = self.config.get("search_strategies", {})
        strategy_config = strategies.get(strategy)
        
        if not strategy_config:
            return {"success": False, "error": f"搜索策略未找到: {strategy}", "papers": []}
        
        sources = strategy_config.get("sources", [])
        max_results = strategy_config.get("max_results_per_source", 20)
        
        # 添加策略参数
        search_params = {"query": query, "limit": max_results, **kwargs}
        
        return await self.search_multiple_sources(sources, **search_params)
    
    def get_available_services(self) -> Dict[str, Any]:
        """获取可用服务列表"""
        services = {}
        for service_id, service_config in self.config.get("mcpServices", {}).items():
            services[service_id] = {
                "name": service_config.get("name", service_id),
                "description": service_config.get("description", ""),
                "enabled": service_config.get("enabled", True),
                "base_url": service_config.get("base_url", "")
            }
        
        return services
    
    def get_search_strategies(self) -> Dict[str, Any]:
        """获取搜索策略列表"""
        return self.config.get("search_strategies", {})
    
    async def close(self):
        """关闭客户端"""
        if self.session:
            await self.session.close()
        logger.info("🔒 通用MCP客户端已关闭")

# 全局客户端实例
_universal_client: Optional[GenericMCPClient] = None

async def get_universal_client() -> GenericMCPClient:
    """获取通用MCP客户端实例"""
    global _universal_client
    if _universal_client is None:
        _universal_client = GenericMCPClient()
    return _universal_client

# 便捷函数
async def universal_search(query: str, sources: List[str] = None, strategy: str = None, **kwargs) -> Dict[str, Any]:
    """
    通用搜索函数
    
    Args:
        query: 搜索查询
        sources: 指定数据源列表
        strategy: 搜索策略
        **kwargs: 其他搜索参数
        
    Returns:
        搜索结果
    """
    client = await get_universal_client()
    
    if strategy:
        return await client.search_with_strategy(strategy, query, **kwargs)
    elif sources:
        return await client.search_multiple_sources(sources, query=query, **kwargs)
    else:
        # 默认使用fast策略
        return await client.search_with_strategy("fast", query, **kwargs)

# 测试函数
async def test_universal_mcp():
    """测试通用MCP系统"""
    client = GenericMCPClient()
    
    print("🚀 测试通用MCP系统")
    print("=" * 50)
    
    # 显示可用服务
    services = client.get_available_services()
    print(f"📋 可用服务: {list(services.keys())}")
    
    # 显示搜索策略
    strategies = client.get_search_strategies()
    print(f"🎯 搜索策略: {list(strategies.keys())}")
    
    # 测试单个服务搜索
    print("\n🔍 测试arXiv搜索...")
    result = await client.search_service("arxiv", query="machine learning", limit=3, category="cs.AI")
    print(f"结果: {result.get('success')}, 数量: {result.get('count', 0)}")
    
    # 测试多源搜索
    print("\n🔍 测试多源搜索...")
    result = await client.search_multiple_sources(["arxiv", "crossref"], query="deep learning", limit=5)
    print(f"结果: {result.get('success')}, 总数量: {result.get('total_count', 0)}")
    print(f"来源统计: {result.get('source_stats', {})}")
    
    # 测试策略搜索
    print("\n🎯 测试快速搜索策略...")
    result = await client.search_with_strategy("fast", "neural networks")
    print(f"结果: {result.get('success')}, 总数量: {result.get('total_count', 0)}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_universal_mcp())