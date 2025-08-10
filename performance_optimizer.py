"""
Paper God 性能优化模块
解决API响应慢问题：缓存 + 并发 + 优化
"""

import asyncio
import time
import hashlib
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from functools import wraps
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: float
    ttl: int = 3600  # 默认1小时过期

class MemoryCache:
    """内存缓存管理器"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        
    def _generate_key(self, *args, **kwargs) -> str:
        """生成缓存key"""
        key_data = {"args": args, "kwargs": kwargs}
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.cache:
            return None
            
        entry = self.cache[key]
        
        # 检查是否过期
        if time.time() - entry.timestamp > entry.ttl:
            del self.cache[key]
            return None
            
        return entry.data
    
    def set(self, key: str, data: Any, ttl: int = 3600):
        """设置缓存"""
        # 清理过期缓存
        self._cleanup_expired()
        
        # 如果缓存满了，删除最旧的条目
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k].timestamp)
            del self.cache[oldest_key]
        
        self.cache[key] = CacheEntry(data=data, timestamp=time.time(), ttl=ttl)
    
    def _cleanup_expired(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry.timestamp > entry.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
    
    def stats(self) -> Dict[str, Any]:
        """缓存统计"""
        return {
            "total_entries": len(self.cache),
            "max_size": self.max_size,
            "usage_ratio": len(self.cache) / self.max_size
        }

# 全局缓存实例
keyword_cache = MemoryCache(max_size=500)
discipline_cache = MemoryCache(max_size=200)

def cache_result(cache_instance: MemoryCache, ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存key
            cache_key = cache_instance._generate_key(*args, **kwargs)
            
            # 尝试从缓存获取
            cached_result = cache_instance.get(cache_key)
            if cached_result is not None:
                logger.info(f"缓存命中: {func.__name__}")
                return cached_result
            
            # 执行原函数
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 存入缓存
            cache_instance.set(cache_key, result, ttl)
            logger.info(f"缓存存储: {func.__name__}, 执行时间: {execution_time:.2f}s")
            
            return result
        return wrapper
    return decorator

class OptimizedKeywordExpander:
    """优化的关键词扩展器"""
    
    def __init__(self, groq_client, model_name: str = "gemma2-9b-it"):
        self.groq_client = groq_client
        self.model_name = model_name
        
        # 预定义精准术语扩展（快速响应）
        self.quick_expansions = {
            # 计算机科学
            "machine learning": ["supervised learning", "unsupervised learning", "reinforcement learning", "deep neural networks", "feature engineering"],
            "深度学习": ["deep learning", "convolutional neural networks", "recurrent neural networks", "transformer architecture", "attention mechanism"],
            "机器学习": ["machine learning", "gradient descent", "cross-validation", "feature selection", "ensemble methods"],
            "人工智能": ["artificial intelligence", "neural networks", "computer vision", "natural language processing", "reinforcement learning"],
            
            # 化学工程
            "甲烷干重整": ["methane dry reforming", "CO2 reforming", "syngas production", "Ni-based catalysts", "coke formation"],
            "催化剂": ["heterogeneous catalysis", "catalyst deactivation", "active sites", "support materials", "catalyst characterization"],
            "催化": ["catalysis", "enzymatic catalysis", "photocatalysis", "electrocatalysis", "catalyst turnover frequency"],
            
            # 生物医学
            "癌症治疗": ["immunotherapy", "checkpoint inhibitors", "CAR-T cell therapy", "targeted therapy", "precision oncology"],
            "基因编辑": ["CRISPR-Cas9", "gene editing", "base editing", "prime editing", "guide RNA"],
            "蛋白质": ["protein folding", "protein structure", "protein-protein interactions", "protein purification", "structural biology"],
            
            # 物理学
            "量子计算": ["quantum algorithms", "quantum entanglement", "quantum error correction", "quantum supremacy", "quantum gates"],
            "量子力学": ["wave function", "quantum superposition", "quantum decoherence", "quantum measurement", "quantum field theory"],
            
            # 材料科学
            "纳米材料": ["nanoparticles", "quantum dots", "carbon nanotubes", "graphene", "nanocomposites"],
            "材料表征": ["XRD", "SEM", "TEM", "XPS", "Raman spectroscopy"],
            
            # 其他领域
            "区块链": ["distributed ledger", "consensus mechanisms", "smart contracts", "cryptocurrency", "decentralized finance"]
        }
    
    def get_quick_expansion(self, query: str, max_keywords: int = 5) -> Optional[List[str]]:
        """快速扩展（无API调用）"""
        query_lower = query.lower().strip()
        
        # 精确匹配
        if query_lower in self.quick_expansions:
            return self.quick_expansions[query_lower][:max_keywords]
        
        # 模糊匹配
        for key, expansion in self.quick_expansions.items():
            if key in query_lower or query_lower in key:
                return expansion[:max_keywords]
        
        return None
    
    def _build_precision_prompt(self, query: str, discipline: str, max_keywords: int) -> str:
        """构建高精准度的扩展prompt"""
        
        # 学科特定的指导
        discipline_guides = {
            "computer_science": {
                "focus": "algorithms, methods, systems, architectures, frameworks",
                "examples": "neural networks → CNN, RNN, transformer, attention mechanism, backpropagation",
                "avoid": "general programming terms, basic concepts"
            },
            "biomedical": {
                "focus": "diseases, treatments, mechanisms, biomarkers, pathways",
                "examples": "cancer therapy → immunotherapy, chemotherapy, targeted therapy, CAR-T, checkpoint inhibitors",
                "avoid": "basic anatomy terms, general medical words"
            },
            "chemical_engineering": {
                "focus": "reactions, catalysts, processes, materials, mechanisms",
                "examples": "catalysis → heterogeneous catalysis, enzyme catalysis, photocatalysis, electrocatalysis",
                "avoid": "basic chemistry terms, common chemicals"
            },
            "materials_science": {
                "focus": "properties, synthesis, characterization, applications, structures",
                "examples": "nanomaterials → nanoparticles, nanotubes, graphene, quantum dots, nanocomposites",
                "avoid": "basic material names, general properties"
            },
            "physics": {
                "focus": "phenomena, theories, models, measurements, particles",
                "examples": "quantum mechanics → wave function, entanglement, superposition, decoherence, quantum field theory",
                "avoid": "basic physics concepts, common units"
            }
        }
        
        guide = discipline_guides.get(discipline, {
            "focus": "technical terms, methods, applications, theories",
            "examples": "research topic → specific methods, advanced techniques, key theories",
            "avoid": "overly general terms, basic concepts"
        })
        
        # 根据查询语言选择prompt模板
        if any('\u4e00' <= char <= '\u9fff' for char in query):
            # 中文查询 - 转换为英文术语
            prompt = f"""你是{discipline}领域的资深研究专家。请将中文查询转换为{max_keywords}个最精准的英文学术术语。

学科：{discipline}
中文查询："{query}"
重点关注：{guide['focus']}

要求：
1. 术语必须是该领域的**专业技术术语**，不是通用词汇
2. 包含缩写、全称、核心概念、相关技术

3. 术语要在顶级期刊中常见，具有学术价值
4. 避免：{guide['avoid']}
5. 参考模式：{guide['examples']}

请只返回{max_keywords}个英文术语，用逗号分隔，不要解释："""

        else:
            # 英文查询 - 扩展相关术语
            prompt = f"""You are a {discipline} research expert. Expand this query into {max_keywords} highly specific academic terms.

Field: {discipline}
Query: "{query}"
Focus on: {guide['focus']}

Requirements:
1. Terms must be **technical/specialized** terms in this field, not general words
2. Include abbreviations, full forms, core concepts, related techniques
3. Terms should appear in top-tier journals and have academic significance
4. Avoid: {guide['avoid']}
5. Follow pattern: {guide['examples']}

Return exactly {max_keywords} terms, comma-separated, no explanations:"""

        return prompt
    
    async def expand_with_groq(self, query: str, discipline: str, max_keywords: int = 5) -> List[str]:
        """使用Groq扩展（带缓存）"""
        
        # 手动处理缓存，避免序列化问题
        cache_key = keyword_cache._generate_key(query, discipline, max_keywords)
        
        # 尝试从缓存获取
        cached_result = keyword_cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"关键词扩展缓存命中: {query}")
            return cached_result
        
        # 优化的精准prompt
        prompt = self._build_precision_prompt(query, discipline, max_keywords)
        
        try:
            response = self.groq_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # 稍微提高温度获得更好的术语多样性
                max_tokens=100    # 增加token数量以获得完整响应
            )
            
            raw_terms = response.choices[0].message.content.strip()
            terms = [term.strip().strip('"').strip("'") for term in raw_terms.split(",")]
            
            # 过滤和验证
            valid_terms = []
            for term in terms:
                if term and len(term) > 1 and len(term) < 50:
                    valid_terms.append(term)
            
            result = valid_terms[:max_keywords]
            
            # 缓存结果
            keyword_cache.set(cache_key, result, ttl=7200)
            logger.info(f"关键词扩展结果已缓存: {query}")
            
            return result
            
        except Exception as e:
            logger.error(f"Groq扩展失败: {e}")
            return [query]
    
    async def hybrid_expand(self, query: str, discipline: str, max_keywords: int = 5) -> Dict[str, Any]:
        """混合扩展策略：快速 + 智能"""
        start_time = time.time()
        
        # 1. 尝试快速扩展
        quick_result = self.get_quick_expansion(query, max_keywords)
        
        if quick_result:
            return {
                "expanded_keywords": quick_result,
                "strategy": "quick_expansion",
                "processing_time": time.time() - start_time,
                "cached": True
            }
        
        # 2. 使用Groq扩展（带缓存）
        groq_result = await self.expand_with_groq(query, discipline, max_keywords)
        
        return {
            "expanded_keywords": groq_result,
            "strategy": "groq_expansion", 
            "processing_time": time.time() - start_time,
            "cached": False
        }

async def cached_discipline_detection(query: str, detector) -> Dict[str, Any]:
    """缓存的学科检测"""
    # 手动处理缓存，避免序列化detector对象
    cache_key = discipline_cache._generate_key(query)
    
    # 尝试从缓存获取
    cached_result = discipline_cache.get(cache_key)
    if cached_result is not None:
        logger.info(f"学科检测缓存命中: {query}")
        return cached_result
    
    # 执行检测并缓存结果
    result = detector.expand_with_discipline_context(query)
    discipline_cache.set(cache_key, result, ttl=3600)
    logger.info(f"学科检测结果已缓存: {query}")
    
    return result

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {
            "api_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time": 0.0,
            "total_requests": 0
        }
    
    def record_request(self, response_time: float, cache_hit: bool):
        """记录请求指标"""
        self.metrics["total_requests"] += 1
        
        if cache_hit:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1
            self.metrics["api_calls"] += 1
        
        # 更新平均响应时间
        total_time = self.metrics["avg_response_time"] * (self.metrics["total_requests"] - 1)
        self.metrics["avg_response_time"] = (total_time + response_time) / self.metrics["total_requests"]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        cache_hit_rate = 0.0
        if self.metrics["total_requests"] > 0:
            cache_hit_rate = self.metrics["cache_hits"] / self.metrics["total_requests"]
        
        return {
            **self.metrics,
            "cache_hit_rate": cache_hit_rate,
            "keyword_cache_stats": keyword_cache.stats(),
            "discipline_cache_stats": discipline_cache.stats()
        }

# 全局性能监控器
performance_monitor = PerformanceMonitor()

async def batch_expand_keywords(queries: List[str], expander: OptimizedKeywordExpander) -> List[Dict[str, Any]]:
    """批量扩展关键词（并发处理）"""
    
    async def expand_single(query: str):
        # 简化的学科检测（避免重复API调用）
        discipline = "general"
        if any(cs_term in query.lower() for cs_term in ["machine", "algorithm", "neural"]):
            discipline = "computer_science"
        elif any(bio_term in query.lower() for bio_term in ["cancer", "protein", "gene"]):
            discipline = "biomedical"
        elif any(chem_term in query.lower() for chem_term in ["catalyst", "reaction", "methane"]):
            discipline = "chemical_engineering"
        
        return await expander.hybrid_expand(query, discipline)
    
    # 并发处理多个查询
    results = await asyncio.gather(*[expand_single(q) for q in queries])
    return results

if __name__ == "__main__":
    # 测试缓存性能
    async def test_performance():
        from groq import Groq
        import os
        
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        expander = OptimizedKeywordExpander(groq_client)
        
        test_queries = ["machine learning", "深度学习", "甲烷干重整"]
        
        print("=== 性能测试 ===")
        
        # 第一次调用（无缓存）
        start_time = time.time()
        results1 = await batch_expand_keywords(test_queries, expander)
        first_call_time = time.time() - start_time
        
        print(f"首次调用时间: {first_call_time:.2f}s")
        
        # 第二次调用（有缓存）
        start_time = time.time()
        results2 = await batch_expand_keywords(test_queries, expander)
        second_call_time = time.time() - start_time
        
        print(f"缓存调用时间: {second_call_time:.2f}s")
        print(f"性能提升: {first_call_time/second_call_time:.1f}x")
        
        # 显示性能统计
        print(f"性能统计: {performance_monitor.get_stats()}")
    
    asyncio.run(test_performance())