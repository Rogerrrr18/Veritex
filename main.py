"""
Paper God - 智能学术文献搜索系统
新版本：集成LLM智能对话 + 专业关键词扩展 + 多源融合搜索
核心功能：LangGraph工作流 + 层次化关键词分析 + 多源数据获取 + 智能结果排序
"""

import asyncio
import time
import random
import os
import sys
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
import logging

# 导入新的智能搜索组件
from multi_source_engine import MultiSourceEngine, Paper
from langchain_workflows.paper_search_workflow import chat_with_search_strategy, get_intelligent_paper_search_agent
from llm_interface import get_universal_llm, get_model_config_manager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ 配置 ================
DEFAULT_MAX_RESULTS = 50
load_dotenv()

# 检查LLM配置
def check_llm_config():
    """检查LLM配置"""
    try:
        config_manager = get_model_config_manager()
        active_model = config_manager.get_active_model_name()
        available_models = config_manager.list_available_models()
        
        if not available_models:
            print("警告: 未找到可用的LLM模型配置")
            print("请在.env文件中配置至少一个模型的API密钥:")
            print("- OPENAI_API_KEY: OpenAI API 密钥")
            print("- QWEN_API_KEY: 通义千问 API 密钥")
            print("- CLAUDE_API_KEY: Claude API 密钥")
            print("- DEEPSEEK_API_KEY: DeepSeek API 密钥")
            return False
            
        print(f"当前激活模型: {active_model}")
        print(f"可用模型: {', '.join(available_models)}")
        print(f"Python 路径: {sys.executable}")
        return True
        
    except Exception as e:
        print(f"配置检查失败: {e}")
        return False

# 检查配置
if not check_llm_config():
    print("退出: LLM配置不完整")
    sys.exit(1)

class PaperGodSearchEngine:
    """
    Paper God 核心搜索引擎 - 智能对话版
    集成LLM智能分析 + 专业关键词扩展 + 多源数据获取 + 结果优化
    注意: 这个类保持向后兼容，实际由LangGraph工作流驱动
    """
    
    def __init__(self, enable_mcp: bool = False):
        """初始化搜索引擎组件"""
        try:
            # 使用多源引擎作为基础搜索能力
            self.multi_source_engine = MultiSourceEngine(enable_mcp=enable_mcp)
            self.enable_mcp = enable_mcp
            
            logger.info(f"搜索引擎组件初始化成功 - MCP: {enable_mcp}")
            
            # 初始化智能工作流组件（延迟加载）
            self._intelligent_agent = None
            
        except Exception as e:
            logger.error(f"搜索引擎初始化失败: {e}")
            raise
    
    async def _get_intelligent_agent(self):
        """获取智能搜索Agent（延迟加载）"""
        if self._intelligent_agent is None:
            self._intelligent_agent = get_intelligent_paper_search_agent()
        return self._intelligent_agent
    
    async def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        enable_expansion: bool = True
    ) -> Dict[str, Any]:
        """
        智能搜索（兼容接口）：使用LangGraph工作流进行智能分析和搜索
        向后兼容接口，实际由LangGraph工作流驱动
        """
        start_time = time.time()
        
        try:
            logger.info(f"开始智能搜索: query={query}, max_results={max_results}")
            
            # 使用智能工作流进行搜索
            intelligent_agent = await self._get_intelligent_agent()
            workflow_result = await intelligent_agent.search_papers(
                query=query, 
                max_results=max_results
            )
            
            processing_time = time.time() - start_time
            
            if workflow_result.get('success'):
                # 转换为兼容格式
                search_results = workflow_result.get('search_results', [])
                # 将字典转换为Paper对象（如果需要）
                papers = []
                for result in search_results:
                    if isinstance(result, dict):
                        # 创建一个类似Paper的对象
                        paper = type('Paper', (), result)()
                        papers.append(paper)
                    else:
                        papers.append(result)
                
                return {
                    'papers': papers,
                    'total_found': len(papers),
                    'query_info': {
                        'original_query': query,
                        'search_terms': [query],
                        'expanded_query': query,
                        'intelligent_workflow': True,
                        'analysis_result': workflow_result.get('analysis_result')
                    },
                    'performance': {
                        'processing_time': processing_time,
                        'intelligent_workflow': True,
                        'is_academic_query': workflow_result.get('is_academic_query', False),
                        'llm_analysis': True
                    }
                }
            else:
                # 工作流失败，使用传统搜索作为后备
                logger.warning("智能工作流失败，使用传统搜索后备")
                return await self._fallback_search(query, max_results, processing_time)
                
        except Exception as e:
            logger.error(f"智能搜索出错: {e}")
            processing_time = time.time() - start_time
            return await self._fallback_search(query, max_results, processing_time)
    
    async def _fallback_search(self, query: str, max_results: int, processing_time: float) -> Dict[str, Any]:
        """后备搜索方法 - 使用基础多源搜索"""
        try:
            logger.info("使用后备搜索方法")
            papers = await self.multi_source_engine.search_parallel(query, max_results)
            
            return {
                'papers': papers[:max_results],
                'total_found': len(papers[:max_results]),
                'query_info': {
                    'original_query': query,
                    'search_terms': [query],
                    'expanded_query': query,
                    'fallback_mode': True
                },
                'performance': {
                    'processing_time': processing_time,
                    'fallback_mode': True,
                    'intelligent_workflow': False
                }
            }
        except Exception as fallback_error:
            logger.error(f"后备搜索也失败: {fallback_error}")
            return {
                'papers': [],
                'total_found': 0,
                'query_info': {
                    'original_query': query,
                    'error': str(fallback_error)
                },
                'performance': {
                    'processing_time': processing_time,
                    'error': True,
                    'error_message': str(fallback_error)
                }
            }
    
    # 移除了旧的结果优化方法，现在由LangGraph工作流处理
    
    # 移除了_normalize_title方法
    
    # 移除了_calculate_relevance方法
    
    # 移除了_filter_quality方法
    
    async def close(self):
        """关闭搜索引擎资源"""
        if hasattr(self, 'multi_source_engine'):
            await self.multi_source_engine.close()

# ================ 命令行接口 ================

async def main_search(query: str, max_results: int = 20, enable_expansion: bool = True):
    """主搜索函数 - 用于命令行和外部调用（新版本：智能对话）"""
    
    try:
        # 使用智能工作流进行搜索
        print(f"\n🚀 启动智能学术搜索工作流...")
        print(f"🔍 查询: {query}")
        print("-" * 50)
        
        # 调用智能工作流
        result = await chat_with_search_strategy(query)
        
        if result.get('success'):
            # 显示结果
            if result.get('is_academic_query'):
                print("🎯 识别为学术查询")
                search_results = result.get('search_results', [])
                
                if search_results:
                    print(f"\n📋 搜索结果 (共 {len(search_results)} 篇):")
                    print("=" * 80)
                    
                    for i, paper in enumerate(search_results[:10], 1):  # 限制显示10篇
                        print(f"\n{i}. {paper.get('title', '无标题')}")
                        
                        authors = paper.get('authors', [])
                        if authors:
                            author_str = ', '.join(authors[:3])
                            if len(authors) > 3:
                                author_str += f" 等 {len(authors)} 位作者"
                            print(f"   作者: {author_str}")
                        
                        year = paper.get('year', '')
                        journal = paper.get('journal', '')
                        if year:
                            print(f"   年份: {year}")
                        if journal:
                            print(f"   期刊: {journal}")
                        
                        citations = paper.get('citations', 0)
                        if citations:
                            print(f"   引用: {citations} 次")
                        
                        relevance = paper.get('relevance_score', 0)
                        if relevance:
                            print(f"   相关性: {relevance:.2f}")
                        
                        abstract = paper.get('abstract', '')
                        if abstract:
                            preview = abstract[:200] + "..." if len(abstract) > 200 else abstract
                            print(f"   摘要: {preview}")
                        
                        url = paper.get('url', '')
                        if url:
                            print(f"   链接: {url}")
                else:
                    print("\n❌ 未找到相关论文")
                    print("建议:")
                    print("- 尝试使用不同的关键词")
                    print("- 检查关键词拼写")
                    print("- 使用更通用的术语")
            else:
                print("💬 识别为普通对话")
                print(f"\n回复: {result.get('response', '')}")
        else:
            print(f"\n❌ 搜索失败: {result.get('error_message', '未知错误')}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 搜索过程发生错误: {e}")
        return {
            'success': False,
            'error_message': str(e),
            'is_academic_query': False,
            'search_results': [],
            'response': f"搜索失败: {e}"
        }

def main():
    """命令行入口点 - 智能对话版"""
    if len(sys.argv) < 2:
        print("使用方法: python main.py \"查询内容\"")
        print("示例: python main.py \"machine learning的最新研究\"")
        print("示例: python main.py \"你好，请介绍一下甲烷干重整技术\"")
        print("示例: python main.py \"我需要10篇关于深度学习的论文\"")
        sys.exit(1)
    
    query = sys.argv[1]
    
    print("🚀 Paper God - 智能学术搜索系统")
    print("🤖 新版本：LLM智能对话 + 专业关键词分析")
    print("-" * 50)
    
    # 运行智能搜索
    asyncio.run(main_search(query, 20, True))

if __name__ == "__main__":
    main()