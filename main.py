"""
Paper God - 学术文献智能搜索系统
重构版本：替换scholarly为多源融合搜索架构
核心功能：Groq关键词扩展 + 多源数据获取 + 智能结果排序
"""

import asyncio
import time
import random
import os
import sys
from typing import List, Dict, Optional
from dotenv import load_dotenv
import logging

# 导入新的核心组件
from multi_source_engine import MultiSourceEngine, Paper
from enhanced_keyword_expander import EnhancedKeywordExpander, KeywordExpansionResult
from discipline_detector import DisciplineDetector

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ 配置 ================
DEFAULT_MAX_RESULTS = 50
load_dotenv()

# 检查配置
if not os.path.exists(".env"):
    print("警告: .env 文件不存在，请创建 .env 文件并配置以下变量：")
    print("- GROQ_API_KEY: 你的 Groq API 密钥")
    print("- GROQ_MODEL: 模型名称 (如 gemma2-9b-it)")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("请在.env文件或环境变量中配置GROQ_API_KEY")

GROQ_MODEL = os.getenv("GROQ_MODEL", "gemma2-9b-it")

print(f"当前配置 - 模型: {GROQ_MODEL}, API密钥: {'已配置' if GROQ_API_KEY else '未配置'}")
print(f"当前 Python 路径: {sys.executable}")

class PaperGodSearchEngine:
    """
    Paper God 核心搜索引擎
    集成多源数据获取 + 智能关键词扩展 + 结果优化
    """
    
    def __init__(self):
        """初始化搜索引擎组件"""
        try:
            self.keyword_expander = EnhancedKeywordExpander(GROQ_API_KEY, GROQ_MODEL)
            self.multi_source_engine = MultiSourceEngine()
            self.discipline_detector = DisciplineDetector()
            logger.info("搜索引擎组件初始化成功")
        except Exception as e:
            logger.error(f"搜索引擎初始化失败: {e}")
            raise
    
    async def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        enable_expansion: bool = True
    ) -> Dict[str, any]:
        """
        智能搜索：关键词扩展 + 多源搜索 + 结果优化
        确保返回指定数量的高相关性结果
        """
        start_time = time.time()
        expansion_result = None
        
        try:
            logger.info(f"开始搜索: query={query}, max_results={max_results}")
            
            # 增加初始搜索数量以确保有足够的候选结果
            search_multiplier = 2
            initial_search_limit = max_results * search_multiplier
            
            # 步骤1: 关键词扩展和学科检测
            search_terms = [query]
            expanded_query = query
            
            if enable_expansion:
                try:
                    logger.info("正在进行关键词扩展...")
                    expansion_result = await self.keyword_expander.detect_and_expand(
                        query, max_keywords=5
                    )
                    search_terms = expansion_result.expanded_keywords
                    expanded_query = " OR ".join(f'"{term}"' for term in search_terms)
                    logger.info(f"关键词扩展完成: {search_terms}")
                except Exception as e:
                    logger.warning(f"关键词扩展失败，使用原始查询: {e}")
                    enable_expansion = False
            
            # 步骤2: 多源并行搜索
            logger.info(f"开始多源搜索: {expanded_query}")
            papers = await self.multi_source_engine.search_parallel(
                expanded_query, initial_search_limit
            )
            
            if not papers:
                logger.warning("未找到任何论文，尝试不使用关键词扩展重新搜索")
                papers = await self.multi_source_engine.search_parallel(
                    query, initial_search_limit
                )
            
            # 步骤3: 结果后处理和优化
            optimized_papers = self._optimize_results(papers, query, search_terms)
            
            # 如果结果不足，尝试降低相关性阈值进行第二次搜索
            if len(optimized_papers) < max_results:
                logger.info("结果数量不足，扩大搜索范围")
                papers = await self.multi_source_engine.search_parallel(
                    expanded_query, initial_search_limit * 2
                )
                optimized_papers = self._optimize_results(papers, query, search_terms)
            
            # 确保返回精确的结果数量
            final_papers = optimized_papers[:max_results]
            
            processing_time = time.time() - start_time
            
            # 步骤4: 构建返回结果
            result = {
                'papers': final_papers,
                'total_found': len(final_papers),
                'query_info': {
                    'original_query': query,
                    'search_terms': search_terms,
                    'expanded_query': expanded_query if enable_expansion else query,
                    'discipline_info': expansion_result.__dict__ if expansion_result else None
                },
                'performance': {
                    'processing_time': processing_time,
                    'sources_used': ['semantic_scholar', 'arxiv', 'paperscraper'],
                    'expansion_enabled': enable_expansion,
                    'average_relevance': sum(p.relevance_score for p in final_papers) / len(final_papers) if final_papers else 0
                }
            }
            
            logger.info(f"搜索完成: 找到 {len(final_papers)} 篇论文")
            return result
            
        except Exception as e:
            logger.error(f"搜索过程出错: {e}")
            processing_time = time.time() - start_time
            
            return {
                'papers': [],
                'total_found': 0,
                'query_info': {
                    'original_query': query,
                    'error': str(e),
                    'search_terms': search_terms if 'search_terms' in locals() else [query],
                    'expanded_query': expanded_query if 'expanded_query' in locals() else query
                },
                'performance': {
                    'processing_time': processing_time,
                    'error': True,
                    'error_message': str(e)
                }
            }
    
    def _optimize_results(self, papers: List[Paper], original_query: str, search_terms: List[str]) -> List[Paper]:
        """优化搜索结果：去重、排序、质量过滤"""
        try:
            if not papers:
                return []
            
            # 1. 基于标题的高级去重
            seen_titles = set()
            unique_papers = []
            
            for paper in papers:
                try:
                    title_key = self._normalize_title(paper.title)
                    if title_key and title_key not in seen_titles:
                        seen_titles.add(title_key)
                        unique_papers.append(paper)
                except Exception as e:
                    logger.warning(f"处理论文时出错，跳过: {e}")
                    continue
            
            # 2. 重新计算相关性分数
            query_terms = set(original_query.lower().split())
            search_terms_set = set(term.lower() for term in search_terms)
            
            for paper in unique_papers:
                try:
                    paper.relevance_score = self._calculate_relevance(
                        paper, query_terms, search_terms_set
                    )
                except Exception as e:
                    logger.warning(f"计算相关性分数时出错: {e}")
                    paper.relevance_score = 0.0
            
            # 3. 按相关性和质量排序
            sorted_papers = sorted(
                unique_papers, 
                key=lambda p: (p.relevance_score, p.citations or 0, p.year or 0), 
                reverse=True
            )
            
            # 4. 质量过滤
            filtered_papers = self._filter_quality(sorted_papers)
            
            return filtered_papers
            
        except Exception as e:
            logger.error(f"优化结果时出错: {e}")
            return papers if papers else []
    
    def _normalize_title(self, title: str) -> str:
        """标准化标题用于去重"""
        import re
        # 移除标点符号，转换为小写，移除多余空格
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _calculate_relevance(self, paper: Paper, query_terms: set, search_terms: set) -> float:
        """计算论文相关性分数"""
        score = 0.0
        
        title_terms = set(paper.title.lower().split())
        abstract_terms = set(paper.abstract.lower().split()) if paper.abstract else set()
        
        # 提高标题匹配权重
        title_query_overlap = len(query_terms.intersection(title_terms))
        title_search_overlap = len(search_terms.intersection(title_terms))
        score += (title_query_overlap * 4.0) + (title_search_overlap * 3.0)  # 提高权重
        
        # 提高摘要匹配权重
        abstract_query_overlap = len(query_terms.intersection(abstract_terms))
        abstract_search_overlap = len(search_terms.intersection(abstract_terms))
        score += (abstract_query_overlap * 2.0) + (abstract_search_overlap * 1.5)  # 提高权重
        
        # 引用数权重（提高影响力要求）
        if paper.citations:
            citation_score = min(paper.citations / 50.0, 4.0)  # 提高上限，降低达到上限的引用数要求
            score += citation_score
        
        # 加强时效性权重
        if paper.year:
            current_year = 2024
            if paper.year >= current_year - 2:  # 近2年
                score += 3.0
            elif paper.year >= current_year - 4:  # 近4年
                score += 2.0
            elif paper.year >= current_year - 6:  # 近6年
                score += 1.0
        
        # 数据源权重
        source_weights = {
            'semantic_scholar': 1.3,  # 略微提高权重
            'arxiv': 1.1,
            'paperscraper': 0.9
        }
        score *= source_weights.get(paper.source, 1.0)
        
        return score
    
    def _filter_quality(self, papers: List[Paper]) -> List[Paper]:
        """过滤低质量论文"""
        filtered = []
        
        for paper in papers:
            # 基本质量检查
            if not paper.title or len(paper.title) < 10:
                continue
                
            # 过滤明显不相关的论文
            title_lower = paper.title.lower()
            if any(spam_word in title_lower for spam_word in ['advertisement', 'spam', 'test']):
                continue
            
            # 保留高质量论文
            if (paper.relevance_score > 1.0 or 
                (paper.citations and paper.citations > 5) or
                (paper.year and paper.year >= 2020)):
                filtered.append(paper)
        
        return filtered
    
    async def close(self):
        """关闭搜索引擎资源"""
        await self.multi_source_engine.close()

# ================ 命令行接口 ================

async def main_search(query: str, max_results: int = 20, enable_expansion: bool = True):
    """主搜索函数 - 用于命令行和外部调用"""
    
    engine = PaperGodSearchEngine()
    
    try:
        # 执行搜索
        result = await engine.search(query, max_results, enable_expansion)
        
        # 显示结果
        papers = result['papers']
        if papers:
            print(f"\n📋 搜索结果 (共 {len(papers)} 篇):")
            print("=" * 80)
            
            for i, paper in enumerate(papers, 1):
                print(f"\n{i}. {paper.title}")
                print(f"   作者: {', '.join(paper.authors[:3])}")
                if len(paper.authors) > 3:
                    print(f"        等 {len(paper.authors)} 位作者")
                print(f"   年份: {paper.year or '未知'}")
                print(f"   期刊: {paper.journal or '未知期刊'}")
                print(f"   引用: {paper.citations or 0} 次")
                print(f"   来源: {paper.source}")
                print(f"   相关性: {paper.relevance_score:.2f}")
                if paper.abstract:
                    abstract_preview = paper.abstract[:200] + "..." if len(paper.abstract) > 200 else paper.abstract
                    print(f"   摘要: {abstract_preview}")
                print(f"   链接: {paper.url}")
        else:
            print("\n❌ 未找到相关论文")
            print("建议：")
            print("- 尝试使用不同的关键词")
            print("- 检查关键词拼写")
            print("- 使用更通用的术语")
        
        return result
        
    finally:
        await engine.close()

def main():
    """命令行入口点"""
    if len(sys.argv) < 2:
        print("使用方法: python main.py \"搜索关键词\" [最大结果数] [--no-expansion]")
        print("示例: python main.py \"machine learning\" 20")
        print("示例: python main.py \"甲烷干重整\" 15 --no-expansion")
        sys.exit(1)
    
    query = sys.argv[1]
    max_results = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 20
    enable_expansion = '--no-expansion' not in sys.argv
    
    print("🚀 Paper God - 学术文献智能搜索系统")
    print("📌 重构版：多源融合 + 智能扩展")
    print("-" * 50)
    
    # 运行异步搜索
    asyncio.run(main_search(query, max_results, enable_expansion))

if __name__ == "__main__":
    main()