"""
语义搜索引擎核心组件
提供基于向量相似度的智能文献检索功能，完全兼容现有系统
"""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class SemanticSearchResult:
    """语义搜索结果数据结构"""
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    year: Optional[int]
    journal: str
    url: str
    doi: Optional[str]
    citations: int
    source: str
    semantic_score: float  # 语义相似度分数
    combined_score: float  # 综合排序分数
    relevance_factors: Dict[str, float]  # 相关性因子分解

class SemanticQueryProcessor:
    """查询语义处理器 - 将自然语言查询转换为向量表示"""
    
    def __init__(self):
        self.model = None
        self.is_initialized = False
        
        # 配置参数
        self.model_name = os.getenv("SEMANTIC_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        self.max_sequence_length = int(os.getenv("SEMANTIC_MAX_LENGTH", "512"))
        
    async def _ensure_initialized(self):
        """延迟初始化模型，避免启动时加载"""
        if self.is_initialized:
            return
            
        try:
            # 动态导入，避免在不使用时加载
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"初始化语义模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.is_initialized = True
            logger.info("✅ 语义模型初始化成功")
            
        except ImportError as e:
            logger.warning(f"⚠️ 语义搜索依赖未安装: {e}")
            logger.info("提示: pip install sentence-transformers")
            raise ImportError("语义搜索功能需要安装sentence-transformers")
        except Exception as e:
            logger.error(f"❌ 语义模型初始化失败: {e}")
            raise
    
    async def encode_query(self, query: str) -> np.ndarray:
        """将查询文本编码为向量"""
        await self._ensure_initialized()
        
        try:
            # 预处理查询
            processed_query = self._preprocess_query(query)
            
            # 生成向量嵌入
            vector = self.model.encode(processed_query, convert_to_numpy=True)
            logger.debug(f"查询向量生成完成，维度: {vector.shape}")
            
            return vector
            
        except Exception as e:
            logger.error(f"查询编码失败: {e}")
            raise
    
    async def encode_batch(self, texts: List[str]) -> np.ndarray:
        """批量编码文本为向量"""
        await self._ensure_initialized()
        
        try:
            # 预处理文本列表
            processed_texts = [self._preprocess_query(text) for text in texts]
            
            # 批量生成向量
            vectors = self.model.encode(processed_texts, convert_to_numpy=True)
            logger.debug(f"批量向量生成完成，数量: {len(vectors)}")
            
            return vectors
            
        except Exception as e:
            logger.error(f"批量编码失败: {e}")
            raise
    
    def _preprocess_query(self, text: str) -> str:
        """预处理查询文本"""
        if not text:
            return ""
        
        # 基础清理
        text = text.strip()
        
        # 截断过长文本
        if len(text) > self.max_sequence_length:
            text = text[:self.max_sequence_length]
            logger.debug("文本已截断至最大长度")
        
        return text

class SemanticSearchEngine:
    """语义搜索引擎 - 核心组件"""
    
    def __init__(self):
        self.query_processor = SemanticQueryProcessor()
        self.is_enabled = os.getenv("ENABLE_SEMANTIC_SEARCH", "false").lower() == "true"
        
        # 搜索参数
        self.top_k_candidates = int(os.getenv("SEMANTIC_TOP_K", "100"))
        self.similarity_threshold = float(os.getenv("SEMANTIC_THRESHOLD", "0.6"))
        self.enhancement_weight = float(os.getenv("SEMANTIC_ENHANCEMENT_WEIGHT", "0.3"))
        
        logger.info(f"语义搜索引擎初始化 - 启用: {self.is_enabled}")
        
    async def enhance_search_results(
        self, 
        query: str, 
        traditional_results: List[Any],
        max_results: int = 50
    ) -> List[Any]:
        """增强传统搜索结果 - 核心功能"""
        
        if not self.is_enabled:
            logger.debug("语义搜索未启用，返回原始结果")
            return traditional_results
        
        if not traditional_results:
            logger.debug("无传统搜索结果可供增强")
            return traditional_results
        
        try:
            logger.info(f"开始语义增强搜索结果，原始数量: {len(traditional_results)}")
            start_time = time.time()
            
            # 1. 编码查询
            query_vector = await self.query_processor.encode_query(query)
            
            # 2. 编码论文摘要和标题
            paper_texts = []
            valid_papers = []
            
            for paper in traditional_results:
                # 组合标题和摘要进行语义匹配
                text_content = self._extract_paper_text(paper)
                if text_content:
                    paper_texts.append(text_content)
                    valid_papers.append(paper)
            
            if not paper_texts:
                logger.warning("无有效的论文文本内容可供语义分析")
                return traditional_results
            
            # 3. 批量编码论文内容
            paper_vectors = await self.query_processor.encode_batch(paper_texts)
            
            # 4. 计算相似度
            similarities = self._calculate_similarities(query_vector, paper_vectors)
            
            # 5. 综合评分和重排序
            enhanced_results = await self._rank_with_semantic_scores(
                valid_papers, similarities, max_results
            )
            
            end_time = time.time()
            logger.info(f"✅ 语义增强完成，耗时: {end_time - start_time:.2f}秒")
            logger.info(f"结果数量: {len(enhanced_results)}")
            
            return enhanced_results
            
        except Exception as e:
            logger.error(f"❌ 语义增强失败: {e}")
            logger.info("回退到传统搜索结果")
            return traditional_results
    
    def _extract_paper_text(self, paper) -> str:
        """提取论文的文本内容用于语义分析"""
        try:
            # 处理不同的论文对象格式
            if hasattr(paper, 'title') and hasattr(paper, 'abstract'):
                # Paper对象
                title = getattr(paper, 'title', '') or ''
                abstract = getattr(paper, 'abstract', '') or ''
            elif isinstance(paper, dict):
                # 字典格式
                title = paper.get('title', '') or ''
                abstract = paper.get('abstract', '') or ''
            else:
                logger.warning(f"未知的论文对象格式: {type(paper)}")
                return ""
            
            # 组合标题和摘要
            combined_text = f"{title}. {abstract}".strip()
            
            # 限制长度
            if len(combined_text) > 1000:
                combined_text = combined_text[:1000]
            
            return combined_text
            
        except Exception as e:
            logger.warning(f"提取论文文本失败: {e}")
            return ""
    
    def _calculate_similarities(self, query_vector: np.ndarray, paper_vectors: np.ndarray) -> List[float]:
        """计算查询与论文的语义相似度"""
        try:
            # 使用余弦相似度
            from sklearn.metrics.pairwise import cosine_similarity
            
            # 确保向量形状正确
            query_vector = query_vector.reshape(1, -1)
            
            # 计算相似度矩阵
            similarities = cosine_similarity(query_vector, paper_vectors)[0]
            
            return similarities.tolist()
            
        except ImportError:
            logger.warning("scikit-learn未安装，使用简单点积计算相似度")
            # 简单的点积相似度
            query_norm = np.linalg.norm(query_vector)
            similarities = []
            
            for paper_vector in paper_vectors:
                paper_norm = np.linalg.norm(paper_vector)
                if query_norm > 0 and paper_norm > 0:
                    similarity = np.dot(query_vector, paper_vector) / (query_norm * paper_norm)
                else:
                    similarity = 0.0
                similarities.append(similarity)
            
            return similarities
        
        except Exception as e:
            logger.error(f"相似度计算失败: {e}")
            # 返回均匀分布的默认相似度
            return [0.5] * len(paper_vectors)
    
    async def _rank_with_semantic_scores(
        self, 
        papers: List[Any], 
        similarities: List[float], 
        max_results: int
    ) -> List[Any]:
        """基于语义相似度重新排序论文"""
        try:
            scored_papers = []
            
            for paper, similarity in zip(papers, similarities):
                # 过滤低相似度结果
                if similarity < self.similarity_threshold:
                    continue
                
                # 计算综合评分
                traditional_score = self._get_traditional_score(paper)
                combined_score = self._combine_scores(traditional_score, similarity)
                
                # 为论文对象添加语义评分（如果可能）
                enhanced_paper = self._add_semantic_metadata(paper, similarity, combined_score)
                scored_papers.append((enhanced_paper, combined_score))
            
            # 按综合评分排序
            scored_papers.sort(key=lambda x: x[1], reverse=True)
            
            # 返回前N个结果
            final_results = [paper for paper, _ in scored_papers[:max_results]]
            
            logger.info(f"语义排序完成，过滤后数量: {len(final_results)}")
            return final_results
            
        except Exception as e:
            logger.error(f"语义排序失败: {e}")
            return papers[:max_results]
    
    def _get_traditional_score(self, paper) -> float:
        """获取传统评分（引用数、时间等）"""
        try:
            # 提取传统评分因子
            citations = 0
            year = 2020  # 默认年份
            
            if hasattr(paper, 'citations'):
                citations = getattr(paper, 'citations', 0) or 0
            elif isinstance(paper, dict):
                citations = paper.get('citations', 0) or 0
            
            if hasattr(paper, 'year'):
                year = getattr(paper, 'year', 2020) or 2020
            elif isinstance(paper, dict):
                year = paper.get('year', 2020) or 2020
            
            # 简单的传统评分计算
            citation_score = min(citations / 100.0, 1.0)  # 归一化引用数
            recency_score = max(0, min((year - 2000) / 25.0, 1.0))  # 时间新近性
            
            traditional_score = (citation_score * 0.6) + (recency_score * 0.4)
            return traditional_score
            
        except Exception as e:
            logger.debug(f"传统评分计算失败: {e}")
            return 0.5  # 默认中等评分
    
    def _combine_scores(self, traditional_score: float, semantic_score: float) -> float:
        """组合传统评分和语义相似度"""
        # 加权组合
        combined = (traditional_score * (1 - self.enhancement_weight)) + \
                  (semantic_score * self.enhancement_weight)
        return combined
    
    def _add_semantic_metadata(self, paper, similarity: float, combined_score: float):
        """为论文添加语义评分元数据（非破坏性）"""
        try:
            # 如果是对象，尝试添加属性
            if hasattr(paper, '__dict__'):
                paper.semantic_score = similarity
                paper.combined_score = combined_score
            
            # 如果是字典，添加字段
            elif isinstance(paper, dict):
                paper['semantic_score'] = similarity
                paper['combined_score'] = combined_score
            
            return paper
            
        except Exception as e:
            logger.debug(f"添加语义元数据失败: {e}")
            return paper
    
    async def close(self):
        """清理资源"""
        try:
            # 清理模型缓存
            if hasattr(self.query_processor, 'model') and self.query_processor.model:
                del self.query_processor.model
                self.query_processor.model = None
                self.query_processor.is_initialized = False
                logger.info("语义搜索引擎资源清理完成")
        except Exception as e:
            logger.warning(f"语义搜索引擎清理失败: {e}")

# 工厂函数
def create_semantic_search_engine() -> SemanticSearchEngine:
    """创建语义搜索引擎实例"""
    return SemanticSearchEngine()

# 测试函数
async def test_semantic_search():
    """测试语义搜索功能"""
    print("🔬 测试语义搜索引擎...")
    
    engine = SemanticSearchEngine()
    
    if not engine.is_enabled:
        print("⚠️ 语义搜索未启用，请设置 ENABLE_SEMANTIC_SEARCH=true")
        return
    
    # 模拟传统搜索结果
    mock_papers = [
        {
            'title': 'Machine Learning in Healthcare',
            'abstract': 'This paper explores the application of machine learning algorithms in medical diagnosis.',
            'authors': ['Dr. Smith'],
            'year': 2023,
            'citations': 150,
            'source': 'mock'
        },
        {
            'title': 'Deep Neural Networks for Image Recognition',
            'abstract': 'We present a novel approach using convolutional neural networks for medical image analysis.',
            'authors': ['Dr. Johnson'],
            'year': 2022,
            'citations': 89,
            'source': 'mock'
        }
    ]
    
    try:
        enhanced_results = await engine.enhance_search_results(
            query="machine learning medical diagnosis",
            traditional_results=mock_papers,
            max_results=10
        )
        
        print(f"✅ 语义增强完成，结果数量: {len(enhanced_results)}")
        
        for i, paper in enumerate(enhanced_results):
            title = paper.get('title', '无标题')
            semantic_score = paper.get('semantic_score', 0)
            print(f"{i+1}. {title} (语义相似度: {semantic_score:.3f})")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    finally:
        await engine.close()

if __name__ == "__main__":
    asyncio.run(test_semantic_search())