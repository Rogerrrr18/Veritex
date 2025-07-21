"""
语义搜索引擎
基于sentence-transformers实现论文标题和摘要的语义相似度匹配
"""

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from typing import List, Dict, Tuple, Optional
import asyncio
import os
import pickle
import logging
from dataclasses import dataclass
from academic_apis import Paper

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """搜索结果包含相似度分数"""
    paper: Paper
    similarity_score: float
    matched_field: str  # 'title', 'abstract', 'combined'

class SemanticSearchEngine:
    """语义搜索引擎"""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        初始化语义搜索引擎
        
        Args:
            model_name: sentence-transformers模型名称
        """
        self.model_name = model_name
        self.model = None
        self.index = None
        self.papers = []
        self.embeddings = None
        self.cache_dir = "semantic_cache"
        
        # 创建缓存目录
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def load_model(self):
        """加载语义搜索模型"""
        if self.model is None:
            logger.info(f"加载语义搜索模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("模型加载完成")
    
    def _get_text_for_embedding(self, paper: Paper, mode: str = 'combined') -> str:
        """
        获取用于嵌入的文本
        
        Args:
            paper: 论文对象
            mode: 'title', 'abstract', 'combined'
        """
        if mode == 'title':
            return paper.title
        elif mode == 'abstract':
            return paper.abstract[:500]  # 限制摘要长度
        elif mode == 'combined':
            # 组合标题和摘要，标题权重更高
            title_text = paper.title
            abstract_text = paper.abstract[:300] if paper.abstract else ""
            return f"{title_text}. {abstract_text}"
        else:
            raise ValueError(f"不支持的嵌入模式: {mode}")
    
    def build_index(self, papers: List[Paper], mode: str = 'combined'):
        """
        为论文列表构建语义搜索索引
        
        Args:
            papers: 论文列表
            mode: 嵌入模式
        """
        self.load_model()
        self.papers = papers
        
        logger.info(f"为 {len(papers)} 篇论文构建语义索引（模式: {mode}）")
        
        # 提取文本用于嵌入
        texts = []
        for paper in papers:
            text = self._get_text_for_embedding(paper, mode)
            texts.append(text)
        
        # 生成嵌入向量
        logger.info("生成嵌入向量...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        self.embeddings = embeddings
        
        # 构建FAISS索引
        logger.info("构建FAISS索引...")
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # 内积索引（余弦相似度）
        
        # 标准化向量以便使用余弦相似度
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        
        logger.info(f"索引构建完成，包含 {self.index.ntotal} 个向量")
    
    def search(
        self, 
        query: str, 
        top_k: int = 20,
        min_similarity: float = 0.3
    ) -> List[SearchResult]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            min_similarity: 最小相似度阈值
        """
        if self.model is None or self.index is None:
            raise ValueError("请先构建索引")
        
        # 生成查询向量
        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # 搜索相似向量
        similarities, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for similarity, idx in zip(similarities[0], indices[0]):
            if similarity >= min_similarity and idx < len(self.papers):
                result = SearchResult(
                    paper=self.papers[idx],
                    similarity_score=float(similarity),
                    matched_field='combined'
                )
                results.append(result)
        
        logger.info(f"语义搜索找到 {len(results)} 个相关结果")
        return results
    
    def search_multiple_fields(
        self,
        query: str,
        papers: List[Paper],
        top_k: int = 20,
        min_similarity: float = 0.3
    ) -> List[SearchResult]:
        """
        多字段语义搜索（标题、摘要分别搜索后合并）
        
        Args:
            query: 查询文本  
            papers: 论文列表
            top_k: 返回结果数量
            min_similarity: 最小相似度阈值
        """
        self.load_model()
        
        # 生成查询向量
        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        all_results = {}  # paper_id -> SearchResult
        
        # 搜索标题
        logger.info("搜索标题字段...")
        title_texts = [paper.title for paper in papers]
        if title_texts:
            title_embeddings = self.model.encode(title_texts)
            faiss.normalize_L2(title_embeddings)
            
            # 计算相似度
            similarities = np.dot(query_embedding, title_embeddings.T)[0]
            
            for i, similarity in enumerate(similarities):
                if similarity >= min_similarity:
                    paper = papers[i]
                    if paper.paper_id not in all_results or similarity > all_results[paper.paper_id].similarity_score:
                        all_results[paper.paper_id] = SearchResult(
                            paper=paper,
                            similarity_score=float(similarity),
                            matched_field='title'
                        )
        
        # 搜索摘要（如果存在）
        logger.info("搜索摘要字段...")
        abstract_papers = [p for p in papers if p.abstract.strip()]
        if abstract_papers:
            abstract_texts = [p.abstract[:500] for p in abstract_papers]
            abstract_embeddings = self.model.encode(abstract_texts)
            faiss.normalize_L2(abstract_embeddings)
            
            similarities = np.dot(query_embedding, abstract_embeddings.T)[0]
            
            for i, similarity in enumerate(similarities):
                if similarity >= min_similarity:
                    paper = abstract_papers[i]
                    # 摘要匹配的权重稍低
                    adjusted_similarity = similarity * 0.9
                    
                    if paper.paper_id not in all_results or adjusted_similarity > all_results[paper.paper_id].similarity_score:
                        all_results[paper.paper_id] = SearchResult(
                            paper=paper,
                            similarity_score=float(adjusted_similarity),
                            matched_field='abstract'
                        )
        
        # 按相似度排序并返回
        results = list(all_results.values())
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        logger.info(f"多字段语义搜索找到 {len(results)} 个相关结果")
        return results[:top_k]
    
    def save_index(self, filepath: str):
        """保存索引到文件"""
        if self.index is None:
            raise ValueError("没有可保存的索引")
            
        cache_data = {
            'papers': self.papers,
            'embeddings': self.embeddings,
            'model_name': self.model_name
        }
        
        # 保存FAISS索引
        faiss.write_index(self.index, f"{filepath}.faiss")
        
        # 保存其他数据
        with open(f"{filepath}.pkl", 'wb') as f:
            pickle.dump(cache_data, f)
        
        logger.info(f"索引已保存到 {filepath}")
    
    def load_index(self, filepath: str) -> bool:
        """从文件加载索引"""
        try:
            # 加载FAISS索引
            self.index = faiss.read_index(f"{filepath}.faiss")
            
            # 加载其他数据
            with open(f"{filepath}.pkl", 'rb') as f:
                cache_data = pickle.load(f)
            
            self.papers = cache_data['papers']
            self.embeddings = cache_data['embeddings']
            
            # 检查模型是否一致
            if cache_data['model_name'] != self.model_name:
                logger.warning(f"缓存模型 {cache_data['model_name']} 与当前模型 {self.model_name} 不一致")
                return False
            
            self.load_model()  # 确保模型已加载
            
            logger.info(f"成功加载索引，包含 {len(self.papers)} 篇论文")
            return True
            
        except Exception as e:
            logger.warning(f"加载索引失败: {e}")
            return False

class HybridSearchEngine:
    """混合搜索引擎：结合关键词搜索和语义搜索"""
    
    def __init__(self, semantic_model: str = 'all-MiniLM-L6-v2'):
        self.semantic_engine = SemanticSearchEngine(semantic_model)
        
    def hybrid_search(
        self,
        query: str,
        papers: List[Paper],
        top_k: int = 20,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        min_similarity: float = 0.2
    ) -> List[SearchResult]:
        """
        混合搜索：结合语义相似度和关键词匹配
        
        Args:
            query: 查询字符串
            papers: 论文列表
            top_k: 返回结果数量
            semantic_weight: 语义搜索权重
            keyword_weight: 关键词搜索权重
            min_similarity: 最小相似度阈值
        """
        if not papers:
            return []
        
        # 1. 语义搜索
        semantic_results = self.semantic_engine.search_multiple_fields(
            query, papers, top_k=len(papers), min_similarity=min_similarity
        )
        
        # 2. 关键词搜索
        keyword_results = self._keyword_search(query, papers)
        
        # 3. 结合两种搜索结果
        combined_scores = {}
        
        # 添加语义搜索分数
        for result in semantic_results:
            paper_id = result.paper.paper_id
            combined_scores[paper_id] = {
                'paper': result.paper,
                'semantic_score': result.similarity_score,
                'keyword_score': 0.0,
                'matched_field': result.matched_field
            }
        
        # 添加关键词搜索分数
        for paper, keyword_score in keyword_results:
            paper_id = paper.paper_id
            if paper_id in combined_scores:
                combined_scores[paper_id]['keyword_score'] = keyword_score
            else:
                combined_scores[paper_id] = {
                    'paper': paper,
                    'semantic_score': 0.0,
                    'keyword_score': keyword_score,
                    'matched_field': 'keyword'
                }
        
        # 计算混合分数
        final_results = []
        for paper_id, scores in combined_scores.items():
            hybrid_score = (
                scores['semantic_score'] * semantic_weight +
                scores['keyword_score'] * keyword_weight
            )
            
            if hybrid_score > 0:  # 至少有一种搜索匹配
                result = SearchResult(
                    paper=scores['paper'],
                    similarity_score=hybrid_score,
                    matched_field=scores['matched_field']
                )
                final_results.append(result)
        
        # 按混合分数排序
        final_results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        logger.info(f"混合搜索找到 {len(final_results)} 个结果")
        return final_results[:top_k]
    
    def _keyword_search(self, query: str, papers: List[Paper]) -> List[Tuple[Paper, float]]:
        """
        简单的关键词搜索
        
        Returns:
            List of (paper, keyword_score) tuples
        """
        query_terms = set(query.lower().split())
        results = []
        
        for paper in papers:
            # 在标题和摘要中搜索关键词
            title_text = paper.title.lower()
            abstract_text = paper.abstract.lower() if paper.abstract else ""
            combined_text = f"{title_text} {abstract_text}"
            
            # 计算关键词匹配分数
            matches = 0
            for term in query_terms:
                if term in combined_text:
                    matches += 1
                    # 标题匹配加分
                    if term in title_text:
                        matches += 0.5
            
            if matches > 0:
                keyword_score = matches / len(query_terms)
                results.append((paper, keyword_score))
        
        # 按关键词分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results

# 使用示例
async def main():
    """测试语义搜索功能"""
    from academic_apis import AcademicSearchEngine
    
    # 获取一些论文数据
    academic_engine = AcademicSearchEngine()
    papers = await academic_engine.search_papers(
        query="neural networks machine learning",
        max_results=50
    )
    
    if papers:
        # 测试语义搜索
        semantic_engine = SemanticSearchEngine()
        results = semantic_engine.search_multiple_fields(
            query="deep learning artificial intelligence",
            papers=papers,
            top_k=10
        )
        
        print(f"找到 {len(results)} 个语义相关结果:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.paper.title}")
            print(f"   相似度: {result.similarity_score:.3f}")
            print(f"   匹配字段: {result.matched_field}")
            print(f"   引用次数: {result.paper.citation_count}")
            print()
        
        # 测试混合搜索
        print("\n=== 混合搜索结果 ===")
        hybrid_engine = HybridSearchEngine()
        hybrid_results = hybrid_engine.hybrid_search(
            query="transformer attention mechanism",
            papers=papers,
            top_k=10
        )
        
        for i, result in enumerate(hybrid_results, 1):
            print(f"{i}. {result.paper.title}")
            print(f"   混合分数: {result.similarity_score:.3f}")
            print(f"   匹配方式: {result.matched_field}")
            print()

if __name__ == "__main__":
    asyncio.run(main())