"""
向量数据库接口 - 轻量级实现
为未来扩展提供基础设施，当前使用内存存储，可扩展至外部向量数据库
"""
import asyncio
import logging
import time
import pickle
import os
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class VectorEntry:
    """向量条目数据结构"""
    id: str
    vector: np.ndarray
    metadata: Dict[str, Any]
    timestamp: float
    source: str

class InMemoryVectorStore:
    """内存向量存储 - 轻量级实现"""
    
    def __init__(self):
        self.vectors: Dict[str, VectorEntry] = {}
        self.dimension = None
        self.created_at = time.time()
        
        # 配置参数
        self.max_entries = int(os.getenv("VECTOR_STORE_MAX_ENTRIES", "10000"))
        self.enable_persistence = os.getenv("VECTOR_STORE_PERSISTENCE", "false").lower() == "true"
        self.persist_path = os.getenv("VECTOR_STORE_PATH", "./data/vector_store.pkl")
        
        logger.info(f"内存向量存储初始化 - 最大条目: {self.max_entries}")
        
        # 尝试加载持久化数据
        if self.enable_persistence:
            self._load_from_disk()
    
    async def add_vector(self, id: str, vector: np.ndarray, metadata: Dict[str, Any], source: str = "unknown") -> bool:
        """添加向量到存储"""
        try:
            # 检查向量维度一致性
            if self.dimension is None:
                self.dimension = len(vector)
                logger.info(f"设置向量维度: {self.dimension}")
            elif len(vector) != self.dimension:
                logger.error(f"向量维度不匹配: 期望 {self.dimension}, 得到 {len(vector)}")
                return False
            
            # 检查存储容量
            if len(self.vectors) >= self.max_entries:
                logger.warning("向量存储已满，执行清理")
                await self._cleanup_old_entries()
            
            # 创建向量条目
            entry = VectorEntry(
                id=id,
                vector=vector.copy(),
                metadata=metadata.copy(),
                timestamp=time.time(),
                source=source
            )
            
            self.vectors[id] = entry
            logger.debug(f"向量添加成功: {id} (维度: {len(vector)})")
            
            return True
            
        except Exception as e:
            logger.error(f"向量添加失败: {e}")
            return False
    
    async def search_similar(self, query_vector: np.ndarray, top_k: int = 10, threshold: float = 0.0) -> List[Tuple[str, float, Dict[str, Any]]]:
        """搜索相似向量"""
        try:
            if len(self.vectors) == 0:
                logger.debug("向量存储为空")
                return []
            
            if self.dimension and len(query_vector) != self.dimension:
                logger.error(f"查询向量维度不匹配: 期望 {self.dimension}, 得到 {len(query_vector)}")
                return []
            
            similarities = []
            
            # 计算相似度
            for entry_id, entry in self.vectors.items():
                similarity = self._calculate_cosine_similarity(query_vector, entry.vector)
                
                if similarity >= threshold:
                    similarities.append((entry_id, similarity, entry.metadata))
            
            # 按相似度排序
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # 返回前k个结果
            results = similarities[:top_k]
            logger.debug(f"相似向量搜索完成: {len(results)} 个结果")
            
            return results
            
        except Exception as e:
            logger.error(f"相似向量搜索失败: {e}")
            return []
    
    def _calculate_cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """计算余弦相似度"""
        try:
            # 计算向量的模长
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # 计算余弦相似度
            similarity = np.dot(v1, v2) / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"相似度计算失败: {e}")
            return 0.0
    
    async def get_vector(self, id: str) -> Optional[VectorEntry]:
        """获取指定ID的向量"""
        return self.vectors.get(id)
    
    async def delete_vector(self, id: str) -> bool:
        """删除指定向量"""
        try:
            if id in self.vectors:
                del self.vectors[id]
                logger.debug(f"向量删除成功: {id}")
                return True
            return False
        except Exception as e:
            logger.error(f"向量删除失败: {e}")
            return False
    
    async def _cleanup_old_entries(self):
        """清理旧条目"""
        try:
            if len(self.vectors) <= self.max_entries * 0.8:
                return
            
            # 按时间排序，删除最旧的20%条目
            sorted_entries = sorted(
                self.vectors.items(),
                key=lambda x: x[1].timestamp
            )
            
            num_to_delete = int(len(sorted_entries) * 0.2)
            for i in range(num_to_delete):
                entry_id = sorted_entries[i][0]
                del self.vectors[entry_id]
            
            logger.info(f"清理完成，删除 {num_to_delete} 个旧条目")
            
        except Exception as e:
            logger.error(f"清理失败: {e}")
    
    def _load_from_disk(self):
        """从磁盘加载向量数据"""
        try:
            if not os.path.exists(self.persist_path):
                logger.info("持久化文件不存在，使用空向量存储")
                return
            
            with open(self.persist_path, 'rb') as f:
                data = pickle.load(f)
                self.vectors = data.get('vectors', {})
                self.dimension = data.get('dimension')
                
            logger.info(f"从磁盘加载 {len(self.vectors)} 个向量")
            
        except Exception as e:
            logger.error(f"从磁盘加载失败: {e}")
            self.vectors = {}
    
    async def save_to_disk(self):
        """保存向量数据到磁盘"""
        if not self.enable_persistence:
            return
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            
            data = {
                'vectors': self.vectors,
                'dimension': self.dimension,
                'saved_at': time.time()
            }
            
            with open(self.persist_path, 'wb') as f:
                pickle.dump(data, f)
                
            logger.info(f"向量数据保存到磁盘: {len(self.vectors)} 个条目")
            
        except Exception as e:
            logger.error(f"保存到磁盘失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        return {
            "total_vectors": len(self.vectors),
            "dimension": self.dimension,
            "max_entries": self.max_entries,
            "created_at": self.created_at,
            "memory_usage_mb": self._estimate_memory_usage(),
            "sources": self._count_by_source()
        }
    
    def _estimate_memory_usage(self) -> float:
        """估算内存使用量（MB）"""
        try:
            if not self.vectors or not self.dimension:
                return 0.0
            
            # 估算：每个向量约 dimension * 8 bytes (float64) + 元数据开销
            bytes_per_vector = self.dimension * 8 + 1024  # 1KB元数据开销
            total_bytes = len(self.vectors) * bytes_per_vector
            return total_bytes / (1024 * 1024)  # 转换为MB
            
        except Exception:
            return 0.0
    
    def _count_by_source(self) -> Dict[str, int]:
        """按来源统计向量数量"""
        try:
            source_counts = {}
            for entry in self.vectors.values():
                source = entry.source
                source_counts[source] = source_counts.get(source, 0) + 1
            return source_counts
        except Exception:
            return {}

class VectorDatabase:
    """向量数据库管理器 - 统一接口"""
    
    def __init__(self):
        self.store_type = os.getenv("VECTOR_STORE_TYPE", "memory").lower()
        self.is_enabled = os.getenv("ENABLE_VECTOR_DATABASE", "false").lower() == "true"
        
        # 初始化存储后端
        if self.store_type == "memory":
            self.store = InMemoryVectorStore()
        else:
            logger.warning(f"未支持的向量存储类型: {self.store_type}，使用内存存储")
            self.store = InMemoryVectorStore()
        
        logger.info(f"向量数据库初始化 - 类型: {self.store_type}, 启用: {self.is_enabled}")
    
    async def add_paper_vector(self, paper_id: str, vector: np.ndarray, paper_metadata: Dict[str, Any]) -> bool:
        """添加论文向量"""
        if not self.is_enabled:
            return False
        
        try:
            return await self.store.add_vector(
                id=paper_id,
                vector=vector,
                metadata=paper_metadata,
                source="paper"
            )
        except Exception as e:
            logger.error(f"添加论文向量失败: {e}")
            return False
    
    async def search_similar_papers(self, query_vector: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """搜索相似论文"""
        if not self.is_enabled:
            return []
        
        try:
            results = await self.store.search_similar(query_vector, top_k, threshold=0.1)
            
            # 转换为论文格式
            papers = []
            for paper_id, similarity, metadata in results:
                paper_info = {
                    "id": paper_id,
                    "similarity_score": similarity,
                    **metadata
                }
                papers.append(paper_info)
            
            return papers
            
        except Exception as e:
            logger.error(f"相似论文搜索失败: {e}")
            return []
    
    async def close(self):
        """关闭数据库连接"""
        try:
            if hasattr(self.store, 'save_to_disk'):
                await self.store.save_to_disk()
                
            logger.info("向量数据库关闭完成")
        except Exception as e:
            logger.warning(f"向量数据库关闭失败: {e}")

# 工厂函数
def create_vector_database() -> VectorDatabase:
    """创建向量数据库实例"""
    return VectorDatabase()

# 测试函数
async def test_vector_database():
    """测试向量数据库"""
    print("🔬 测试向量数据库...")
    
    db = VectorDatabase()
    
    if not db.is_enabled:
        print("⚠️ 向量数据库未启用，请设置 ENABLE_VECTOR_DATABASE=true")
        return
    
    try:
        # 生成测试向量
        vector1 = np.random.rand(384).astype(np.float32)
        vector2 = np.random.rand(384).astype(np.float32)
        vector3 = vector1 + 0.1 * np.random.rand(384).astype(np.float32)  # 与vector1相似
        
        # 添加测试数据
        metadata1 = {"title": "Machine Learning Paper", "year": 2023}
        metadata2 = {"title": "Deep Learning Paper", "year": 2022}
        metadata3 = {"title": "ML Applications", "year": 2023}
        
        await db.add_paper_vector("paper1", vector1, metadata1)
        await db.add_paper_vector("paper2", vector2, metadata2)
        await db.add_paper_vector("paper3", vector3, metadata3)
        
        print("✅ 测试向量添加完成")
        
        # 搜索相似向量
        query_vector = vector1 + 0.05 * np.random.rand(384).astype(np.float32)
        similar_papers = await db.search_similar_papers(query_vector, top_k=3)
        
        print(f"✅ 相似搜索完成，找到 {len(similar_papers)} 个结果")
        
        for i, paper in enumerate(similar_papers):
            print(f"{i+1}. {paper['title']} (相似度: {paper['similarity_score']:.3f})")
        
        # 显示统计信息
        if hasattr(db.store, 'get_stats'):
            stats = db.store.get_stats()
            print(f"📊 存储统计: {stats}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(test_vector_database())