"""
通用MCP工具集成器
支持任意MCP工具的动态加载和使用，便于扩展其他MCP服务
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model
import inspect

logger = logging.getLogger(__name__)


class UniversalMCPToolConfig(BaseModel):
    """通用MCP工具配置"""
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    parameters: Dict[str, Any] = Field(description="参数定义")
    mcp_tool_name: str = Field(description="MCP服务器中的工具名称")
    fallback_enabled: bool = Field(default=True, description="启用回退模式")
    mock_data_generator: Optional[str] = Field(default=None, description="模拟数据生成器函数名")


class UniversalMCPTool(BaseTool):
    """通用MCP工具基类"""
    
    def __init__(self, config: UniversalMCPToolConfig, mcp_client=None, **kwargs):
        # 存储配置（先存储）
        self._tool_config = config
        
        # 设置基本属性
        kwargs['name'] = config.name
        kwargs['description'] = config.description
        kwargs['args_schema'] = self._create_args_schema(config.parameters)
        
        super().__init__(**kwargs)
        
        # 设置MCP客户端
        setattr(self.__class__, f'_mcp_client_{config.name}', mcp_client)
    
    @property
    def tool_config(self):
        """获取工具配置"""
        return getattr(self, '_tool_config', None)
    
    @property
    def mcp_client(self):
        """获取MCP客户端"""
        config = self.tool_config
        if config:
            return getattr(self.__class__, f'_mcp_client_{config.name}', None)
        return None
    
    @staticmethod
    def _create_args_schema(parameters: Dict[str, Any]) -> Type[BaseModel]:
        """动态创建参数模式"""
        fields = {}
        
        for param_name, param_config in parameters.items():
            param_type = param_config.get("type", "string")
            description = param_config.get("description", "")
            optional = param_config.get("optional", False)
            default = param_config.get("default")
            
            # 映射类型
            type_mapping = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": List[str]
            }
            
            field_type = type_mapping.get(param_type, str)
            
            if optional:
                if default is not None:
                    fields[param_name] = (Optional[field_type], Field(default=default, description=description))
                else:
                    fields[param_name] = (Optional[field_type], Field(default=None, description=description))
            else:
                fields[param_name] = (field_type, Field(description=description))
        
        return create_model("UniversalMCPToolInput", **fields)
    
    async def _arun(self, **kwargs) -> str:
        """异步执行工具"""
        try:
            # 尝试使用真实的MCP客户端
            if self.mcp_client:
                result = await self.mcp_client.call_tool(
                    self.tool_config.mcp_tool_name,
                    kwargs
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                # 尝试创建MCP客户端连接
                return await self._try_real_mcp_call(kwargs)
                
        except Exception as e:
            logger.warning(f"MCP工具调用失败: {e}")
            if self.tool_config.fallback_enabled:
                return await self._fallback_response(kwargs)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"工具调用失败: {str(e)}",
                    "tool": self.tool_config.name
                }, ensure_ascii=False, indent=2)
    
    def _run(self, **kwargs) -> str:
        """同步执行工具"""
        return asyncio.run(self._arun(**kwargs))
    
    async def _try_real_mcp_call(self, kwargs: Dict[str, Any]) -> str:
        """尝试真实MCP调用"""
        try:
            # 导入universal_mcp客户端
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from universal_mcp import get_universal_client
            
            client = await get_universal_client()
            
            # 根据工具名称调用相应的服务
            if "google_scholar" in self.tool_config.mcp_tool_name:
                result = await client.search_service(
                    "google_scholar",
                    **kwargs
                )
                
                if result.get("success"):
                    return json.dumps(result, ensure_ascii=False, indent=2)
                else:
                    raise Exception(result.get("error", "未知错误"))
            else:
                # 其他MCP工具的通用调用
                # 这里可以扩展支持更多MCP服务
                raise Exception(f"未知的MCP工具: {self.tool_config.mcp_tool_name}")
                
        except Exception as e:
            logger.warning(f"真实MCP调用失败: {e}")
            raise e
    
    async def _fallback_response(self, kwargs: Dict[str, Any]) -> str:
        """回退响应"""
        if self.tool_config.mock_data_generator:
            # 调用自定义模拟数据生成器
            generator_func = getattr(self, self.tool_config.mock_data_generator, None)
            if generator_func and callable(generator_func):
                return await generator_func(kwargs)
        
        # 默认回退响应
        return json.dumps({
            "status": "success",
            "message": f"使用模拟数据 (真实{self.tool_config.name}暂时不可用)",
            "tool": self.tool_config.name,
            "input_params": kwargs,
            "mock_data": True
        }, ensure_ascii=False, indent=2)


class GoogleScholarKeywordSearchTool(UniversalMCPTool):
    """Google Scholar关键词搜索工具"""
    
    def __init__(self, mcp_client=None, **kwargs):
        self._config = UniversalMCPToolConfig(
            name="search_google_scholar_key_words",
            description="使用关键词搜索Google Scholar论文",
            mcp_tool_name="search_google_scholar_key_words",
            parameters={
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 10,
                    "optional": True
                }
            },
            mock_data_generator="generate_mock_keyword_search"
        )
        super().__init__(self._config, mcp_client, **kwargs)
    
    async def generate_mock_keyword_search(self, params: Dict[str, Any]) -> str:
        """生成关键词搜索模拟数据"""
        query = params.get("query", "")
        num_results = params.get("num_results", 5)
        
        # 基于查询生成相关的模拟论文
        query_lower = query.lower()
        papers = []
        
        templates = self._get_paper_templates(query_lower)
        
        for i in range(min(num_results, len(templates))):
            template = templates[i % len(templates)]
            paper = {
                "title": template["title"].format(query),
                "authors": template["authors"],
                "abstract": template["abstract"].format(query),
                "year": template["year"],
                "venue": template["venue"],
                "citations": template["citations"],
                "url": f"https://scholar.google.com/citations?view_op=view_citation&hl=en&user=mock{i+1}",
                "pdf_url": f"https://example.com/pdf/mock{i+1}.pdf" if i % 2 == 0 else "",
                "doi": f"10.1000/mock.{i+1}",
                "research_type": "实验研究" if i % 2 == 0 else "理论分析",
                "access_status": "开放获取" if i % 2 == 0 else "付费/机构订阅"
            }
            papers.append(paper)
        
        return json.dumps({
            "status": "success",
            "query": query,
            "total_results": len(papers),
            "papers": papers,
            "note": "使用高质量模拟数据（真实Google Scholar暂时不可用）"
        }, ensure_ascii=False, indent=2)
    
    def _get_paper_templates(self, query_lower: str) -> List[Dict[str, Any]]:
        """根据查询获取论文模板"""
        if "machine learning" in query_lower:
            return [
                {
                    "title": "Deep Learning for {}: A Comprehensive Survey",
                    "authors": "Zhang, L., Wang, M., Liu, S.",
                    "abstract": "This paper presents a comprehensive survey of deep learning techniques applied to {}. We review the latest developments and challenges...",
                    "venue": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
                    "year": 2023,
                    "citations": 245
                },
                {
                    "title": "Advances in {} Using Neural Networks",
                    "authors": "Smith, J.A., Brown, K.L.",
                    "abstract": "We propose a novel neural network architecture for {}. Our approach demonstrates significant improvements over existing methods...",
                    "venue": "Nature Machine Intelligence",
                    "year": 2022,
                    "citations": 189
                }
            ]
        elif "methane reforming" in query_lower:
            return [
                {
                    "title": "Catalytic {} Process Optimization: Recent Advances",
                    "authors": "Rodriguez, A.M., Kim, S.H.",
                    "abstract": "We investigate advanced catalytic processes for {}. Our study focuses on process optimization and catalyst design...",
                    "venue": "Applied Catalysis B: Environmental",
                    "year": 2023,
                    "citations": 156
                }
            ]
        else:
            return [
                {
                    "title": "Recent Advances in {}: A Systematic Review",
                    "authors": "Williams, R.J., Martinez, C.A.",
                    "abstract": "This comprehensive review examines recent advances in {}. We identify key trends and future research directions...",
                    "venue": "Science",
                    "year": 2023,
                    "citations": 298
                }
            ]


class GoogleScholarAdvancedSearchTool(UniversalMCPTool):
    """Google Scholar高级搜索工具"""
    
    def __init__(self, mcp_client=None, **kwargs):
        self._config = UniversalMCPToolConfig(
            name="search_google_scholar_advanced",
            description="Google Scholar高级搜索，支持作者和年份筛选",
            mcp_tool_name="search_google_scholar_advanced",
            parameters={
                "query": {
                    "type": "string",
                    "description": "搜索查询"
                },
                "author": {
                    "type": "string",
                    "description": "作者名称",
                    "optional": True
                },
                "year_low": {
                    "type": "integer",
                    "description": "起始年份",
                    "optional": True
                },
                "year_high": {
                    "type": "integer",
                    "description": "结束年份",
                    "optional": True
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 10,
                    "optional": True
                }
            },
            mock_data_generator="generate_mock_advanced_search"
        )
        super().__init__(self._config, mcp_client, **kwargs)
    
    async def generate_mock_advanced_search(self, params: Dict[str, Any]) -> str:
        """生成高级搜索模拟数据"""
        query = params.get("query", "")
        author = params.get("author")
        year_low = params.get("year_low")
        year_high = params.get("year_high") 
        num_results = params.get("num_results", 3)
        
        papers = []
        for i in range(num_results):
            year = 2023 - i
            if year_low and year < year_low:
                continue
            if year_high and year > year_high:
                continue
                
            paper_author = author if author else f"作者 {i+1}, 合作者 {i+1}"
            papers.append({
                "title": f"Advanced Research on {query} - Paper {i+1}",
                "authors": paper_author,
                "abstract": f"这是关于'{query}'的高级研究论文摘要...",
                "year": year,
                "venue": f"Advanced Journal {i+1}",
                "citations": 50 - i*10,
                "url": f"https://example.com/advanced_paper{i+1}",
                "pdf_url": f"https://example.com/pdf/advanced{i+1}.pdf",
                "doi": f"10.1000/adv.{i+1}",
                "research_type": "理论分析",
                "access_status": "开放获取"
            })
        
        return json.dumps({
            "status": "success",
            "query": query,
            "filters": {
                "author": author,
                "year_range": f"{year_low or ''}-{year_high or ''}"
            },
            "total_results": len(papers),
            "papers": papers,
            "note": "使用模拟数据（真实Google Scholar高级搜索暂时不可用）"
        }, ensure_ascii=False, indent=2)


class AuthorInfoTool(UniversalMCPTool):
    """作者信息获取工具"""
    
    def __init__(self, mcp_client=None, **kwargs):
        self._config = UniversalMCPToolConfig(
            name="get_author_info",
            description="获取学者的详细信息，包括研究领域、论文数量、引用情况等",
            mcp_tool_name="get_author_info",
            parameters={
                "author_name": {
                    "type": "string",
                    "description": "作者姓名"
                }
            },
            mock_data_generator="generate_mock_author_info"
        )
        super().__init__(self._config, mcp_client, **kwargs)
    
    async def generate_mock_author_info(self, params: Dict[str, Any]) -> str:
        """生成作者信息模拟数据"""
        author_name = params.get("author_name", "")
        
        # 基于作者名生成不同的信息
        if "hinton" in author_name.lower():
            author_info = {
                "name": author_name,
                "affiliation": "University of Toronto, Vector Institute",
                "research_interests": ["Deep Learning", "Neural Networks", "Machine Learning", "Artificial Intelligence"],
                "total_papers": 200,
                "total_citations": 50000,
                "h_index": 120,
                "recent_papers": [
                    "The Forward-Forward Algorithm: Some Preliminary Investigations",
                    "How to represent part-whole hierarchies in a neural network",
                    "Stacked Capsule Autoencoders"
                ],
                "profile_url": "https://scholar.google.com/citations?user=mock_hinton"
            }
        elif "lecun" in author_name.lower():
            author_info = {
                "name": author_name,
                "affiliation": "New York University, Meta AI Research",
                "research_interests": ["Deep Learning", "Computer Vision", "Convolutional Networks"],
                "total_papers": 180,
                "total_citations": 45000,
                "h_index": 110,
                "recent_papers": [
                    "A Path Towards Autonomous Machine Intelligence",
                    "Self-supervised Learning: The Dark Matter of Intelligence",
                    "Deep Learning for AI"
                ],
                "profile_url": "https://scholar.google.com/citations?user=mock_lecun"
            }
        else:
            author_info = {
                "name": author_name,
                "affiliation": "Research University",
                "research_interests": ["人工智能", "机器学习", "数据科学"],
                "total_papers": 75,
                "total_citations": 2500,
                "h_index": 35,
                "recent_papers": [
                    f"Recent Work by {author_name} - Paper 1",
                    f"Advances in AI by {author_name} - Paper 2",
                    f"Novel Methods by {author_name} - Paper 3"
                ],
                "profile_url": f"https://scholar.google.com/citations?user=mock_{author_name.replace(' ', '_').lower()}"
            }
        
        return json.dumps({
            "status": "success",
            "author_name": author_name,
            "author_info": author_info,
            "note": "使用模拟数据（真实Google Scholar作者信息暂时不可用）"
        }, ensure_ascii=False, indent=2)


class MCPToolFactory:
    """MCP工具工厂，用于动态创建和管理工具"""
    
    def __init__(self):
        self.registered_tools = {}
        self.tool_configs = {}
    
    def register_tool_config(self, tool_name: str, config: UniversalMCPToolConfig):
        """注册工具配置"""
        self.tool_configs[tool_name] = config
    
    def create_tool(self, tool_name: str, mcp_client=None) -> Optional[UniversalMCPTool]:
        """创建工具实例"""
        if tool_name not in self.tool_configs:
            logger.error(f"未找到工具配置: {tool_name}")
            return None
        
        config = self.tool_configs[tool_name]
        
        # 检查是否有专门的工具类
        specialized_tools = {
            "search_google_scholar_key_words": GoogleScholarKeywordSearchTool,
            "search_google_scholar_advanced": GoogleScholarAdvancedSearchTool,
            "get_author_info": AuthorInfoTool
        }
        
        tool_class = specialized_tools.get(tool_name, UniversalMCPTool)
        
        if tool_class == UniversalMCPTool:
            return tool_class(config, mcp_client)
        else:
            return tool_class(mcp_client)
    
    def create_google_scholar_tools(self, mcp_client=None) -> List[UniversalMCPTool]:
        """创建Google Scholar工具集合"""
        return [
            GoogleScholarKeywordSearchTool(mcp_client),
            GoogleScholarAdvancedSearchTool(mcp_client),
            AuthorInfoTool(mcp_client)
        ]
    
    def load_tools_from_config(self, config_file: str = "universal_mcp_config.json") -> List[UniversalMCPTool]:
        """从配置文件加载工具"""
        try:
            import os
            config_path = os.path.join(os.path.dirname(__file__), '..', config_file)
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            tools = []
            google_scholar_config = config.get("mcpServices", {}).get("google_scholar", {})
            
            if google_scholar_config.get("enabled", False):
                # 从配置文件创建Google Scholar工具
                tool_configs = google_scholar_config.get("tools", {})
                for tool_name, tool_config in tool_configs.items():
                    mcp_config = UniversalMCPToolConfig(
                        name=tool_name,
                        description=tool_config.get("description", ""),
                        mcp_tool_name=tool_name,
                        parameters=tool_config.get("parameters", {})
                    )
                    self.register_tool_config(tool_name, mcp_config)
                    tool = self.create_tool(tool_name)
                    if tool:
                        tools.append(tool)
            
            return tools
            
        except Exception as e:
            logger.error(f"从配置文件加载工具失败: {e}")
            # 回退到创建默认Google Scholar工具
            return self.create_google_scholar_tools()


# 全局工具工厂实例
tool_factory = MCPToolFactory()

def create_google_scholar_tools(mcp_client=None) -> List[UniversalMCPTool]:
    """创建Google Scholar工具集合 - 向后兼容函数"""
    return tool_factory.create_google_scholar_tools(mcp_client)

def create_mcp_tools_from_config(config_file: str = "universal_mcp_config.json") -> List[UniversalMCPTool]:
    """从配置文件创建MCP工具"""
    return tool_factory.load_tools_from_config(config_file)


# 测试函数
async def test_universal_mcp_tools():
    """测试通用MCP工具"""
    print("测试通用MCP工具系统...")
    
    tools = create_google_scholar_tools()
    
    # 测试关键词搜索
    print("\n1. 测试关键词搜索:")
    result1 = await tools[0]._arun(query="artificial intelligence ethics", num_results=3)
    print(result1[:500] + "..." if len(result1) > 500 else result1)
    
    # 测试高级搜索  
    print("\n2. 测试高级搜索:")
    result2 = await tools[1]._arun(
        query="machine learning", 
        author="Hinton", 
        year_low=2020, 
        year_high=2023,
        num_results=2
    )
    print(result2[:500] + "..." if len(result2) > 500 else result2)
    
    # 测试作者信息
    print("\n3. 测试作者信息:")
    result3 = await tools[2]._arun(author_name="Geoffrey Hinton")
    print(result3[:500] + "..." if len(result3) > 500 else result3)


if __name__ == "__main__":
    asyncio.run(test_universal_mcp_tools())