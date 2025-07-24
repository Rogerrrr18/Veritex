"""
MCP客户端层 - Paper God的核心架构
集成多个MCP服务器，提供统一的学术搜索和分析功能
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import httpx

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPServerType(Enum):
    """MCP服务器类型枚举"""
    PAPER_SEARCH = "paper_search"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    DATA_ANALYSIS = "data_analysis"
    VISUALIZATION = "visualization"


@dataclass
class MCPServer:
    """MCP服务器配置"""
    name: str
    server_type: MCPServerType
    endpoint: str
    enabled: bool = True
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


@dataclass
class SearchResult:
    """统一的搜索结果格式"""
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    url: str
    source: str
    doi: Optional[str] = None
    citations: Optional[int] = None
    venue: Optional[str] = None


class MCPClient:
    """MCP客户端 - 集成多个MCP服务器的核心类"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self._initialize_default_servers()
    
    def _initialize_default_servers(self):
        """初始化默认的MCP服务器配置"""
        # 多源学术搜索MCP服务器
        self.servers["paper_search"] = MCPServer(
            name="openags/paper-search-mcp",
            server_type=MCPServerType.PAPER_SEARCH,
            endpoint="http://localhost:8001",  # MCP服务器端口
            config={
                "sources": ["arxiv", "pubmed", "semantic_scholar", "google_scholar"],
                "max_concurrent": 5
            }
        )
        
        # 知识图谱MCP服务器
        self.servers["knowledge_graph"] = MCPServer(
            name="neo4j-mcp-server",
            server_type=MCPServerType.KNOWLEDGE_GRAPH,
            endpoint="http://localhost:8002",
            config={
                "neo4j_uri": "bolt://localhost:7687",
                "database": "academic_graph"
            }
        )
        
        # 数据分析MCP服务器
        self.servers["data_analysis"] = MCPServer(
            name="pandas-mcp-server", 
            server_type=MCPServerType.DATA_ANALYSIS,
            endpoint="http://localhost:8003",
            config={
                "memory_limit": "1GB",
                "execution_timeout": 30
            }
        )
        
        # 可视化MCP服务器
        self.servers["visualization"] = MCPServer(
            name="antv-mcp-server",
            server_type=MCPServerType.VISUALIZATION,
            endpoint="http://localhost:8004",
            config={
                "chart_types": ["network", "scatter", "timeline", "bubble"]
            }
        )
    
    async def add_server(self, server_id: str, server: MCPServer):
        """添加MCP服务器"""
        self.servers[server_id] = server
        logger.info(f"添加MCP服务器: {server_id} ({server.name})")
    
    async def remove_server(self, server_id: str):
        """移除MCP服务器"""
        if server_id in self.servers:
            del self.servers[server_id]
            logger.info(f"移除MCP服务器: {server_id}")
    
    async def call_mcp(self, server_id: str, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """调用MCP服务器的工具"""
        if server_id not in self.servers:
            raise ValueError(f"MCP服务器不存在: {server_id}")
        
        server = self.servers[server_id]
        if not server.enabled:
            raise ValueError(f"MCP服务器已禁用: {server_id}")
        
        try:
            # 构建MCP调用请求
            request_payload = {
                "jsonrpc": "2.0",
                "id": f"{server_id}_{tool_name}_{id(parameters)}",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": parameters
                }
            }
            
            logger.info(f"调用MCP服务器: {server_id}.{tool_name}")
            
            # 发送HTTP请求到MCP服务器
            response = await self.http_client.post(
                f"{server.endpoint}/mcp",
                json=request_payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                raise Exception(f"MCP调用失败: HTTP {response.status_code}")
            
            result = response.json()
            
            if "error" in result:
                raise Exception(f"MCP工具错误: {result['error']}")
            
            return result.get("result", {})
            
        except Exception as e:
            logger.error(f"MCP调用失败 {server_id}.{tool_name}: {e}")
            raise
    
    async def multi_source_search(self, query: str, max_results: int = 50, 
                                 sources: Optional[List[str]] = None) -> List[SearchResult]:
        """使用MCP进行多源学术搜索"""
        if "paper_search" not in self.servers:
            raise ValueError("论文搜索MCP服务器未配置")
        
        try:
            # 调用论文搜索MCP
            search_params = {
                "query": query,
                "max_results": max_results,
                "sources": sources or ["arxiv", "pubmed", "semantic_scholar"]
            }
            
            mcp_results = await self.call_mcp("paper_search", "search_papers", search_params)
            
            # 转换为统一格式
            papers = []
            for paper_data in mcp_results.get("papers", []):
                paper = SearchResult(
                    title=paper_data.get("title", ""),
                    authors=paper_data.get("authors", []),
                    year=paper_data.get("year"),
                    abstract=paper_data.get("abstract", ""),
                    url=paper_data.get("url", ""),
                    source=paper_data.get("source", "unknown"),
                    doi=paper_data.get("doi"),
                    citations=paper_data.get("citations"),
                    venue=paper_data.get("venue")
                )
                papers.append(paper)
            
            logger.info(f"MCP多源搜索完成: {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"MCP多源搜索失败: {e}")
            # 降级到传统搜索
            return await self._fallback_search(query, max_results)
    
    async def _fallback_search(self, query: str, max_results: int) -> List[SearchResult]:
        """降级搜索：当MCP不可用时使用传统方法"""
        logger.warning("使用降级搜索模式")
        
        try:
            # 这里可以调用原有的scholarly搜索作为后备
            from main import LiteratureCollector
            collector = LiteratureCollector()
            await collector.collect(query, max_results)
            
            # 转换格式
            papers = []
            for result in collector.results:
                paper = SearchResult(
                    title=result.get("title", ""),
                    authors=result.get("authors", "").split("; ") if result.get("authors") else [],
                    year=int(result.get("year")) if result.get("year") and result.get("year").isdigit() else None,
                    abstract=result.get("abstract", ""),
                    url=result.get("url", ""),
                    source="scholarly_fallback"
                )
                papers.append(paper)
            
            return papers
            
        except Exception as e:
            logger.error(f"降级搜索也失败: {e}")
            return []
    
    async def analyze_data(self, data: List[Dict[str, Any]], analysis_type: str = "basic") -> Dict[str, Any]:
        """使用MCP进行数据分析"""
        if "data_analysis" not in self.servers:
            raise ValueError("数据分析MCP服务器未配置")
        
        try:
            analysis_params = {
                "data": data,
                "analysis_type": analysis_type
            }
            
            result = await self.call_mcp("data_analysis", "analyze", analysis_params)
            return result
            
        except Exception as e:
            logger.error(f"MCP数据分析失败: {e}")
            # 返回基本统计
            return {
                "total_papers": len(data),
                "error": str(e),
                "analysis_type": "fallback"
            }
    
    async def generate_visualization(self, data: List[Dict[str, Any]], 
                                   chart_type: str = "network") -> Dict[str, Any]:
        """使用MCP生成可视化"""
        if "visualization" not in self.servers:
            raise ValueError("可视化MCP服务器未配置")
        
        try:
            viz_params = {
                "data": data,
                "chart_type": chart_type,
                "config": {
                    "width": 800,
                    "height": 600,
                    "interactive": True
                }
            }
            
            result = await self.call_mcp("visualization", "generate_chart", viz_params)
            return result
            
        except Exception as e:
            logger.error(f"MCP可视化生成失败: {e}")
            return {
                "error": str(e),
                "chart_type": chart_type,
                "status": "failed"
            }
    
    async def build_knowledge_graph(self, papers: List[SearchResult]) -> Dict[str, Any]:
        """使用MCP构建知识图谱"""
        if "knowledge_graph" not in self.servers:
            raise ValueError("知识图谱MCP服务器未配置")
        
        try:
            # 准备图谱数据
            graph_data = []
            for paper in papers:
                paper_node = {
                    "type": "paper",
                    "title": paper.title,
                    "authors": paper.authors,
                    "year": paper.year,
                    "url": paper.url,
                    "abstract": paper.abstract[:500]  # 限制长度
                }
                graph_data.append(paper_node)
            
            graph_params = {
                "nodes": graph_data,
                "operation": "build_citation_network"
            }
            
            result = await self.call_mcp("knowledge_graph", "build_graph", graph_params)
            return result
            
        except Exception as e:
            logger.error(f"MCP知识图谱构建失败: {e}")
            return {
                "error": str(e),
                "nodes": len(papers),
                "status": "failed"
            }
    
    async def health_check(self) -> Dict[str, bool]:
        """检查所有MCP服务器的健康状态"""
        health_status = {}
        
        for server_id, server in self.servers.items():
            try:
                # 发送健康检查请求
                response = await self.http_client.get(
                    f"{server.endpoint}/health",
                    timeout=5.0
                )
                health_status[server_id] = response.status_code == 200
            except Exception:
                health_status[server_id] = False
        
        return health_status
    
    async def close(self):
        """关闭MCP客户端"""
        await self.http_client.aclose()
        logger.info("MCP客户端已关闭")


# 全局MCP客户端实例
mcp_client = MCPClient()


async def get_mcp_client() -> MCPClient:
    """获取MCP客户端实例"""
    return mcp_client