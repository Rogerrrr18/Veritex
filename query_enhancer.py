"""
查询增强器 - 将现有关键词扩展系统升级为语义增强
完全兼容现有的4层关键词体系，同时添加语义向量能力
"""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class QueryEnhancer:
    """查询增强器 - 升级版关键词扩展"""
    
    def __init__(self):
        self.semantic_enabled = os.getenv("ENABLE_SEMANTIC_ENHANCEMENT", "false").lower() == "true"
        self.fallback_to_traditional = os.getenv("FALLBACK_TO_TRADITIONAL", "true").lower() == "true"
        
        # 语义处理器（延迟初始化）
        self.semantic_processor = None
        
        logger.info(f"查询增强器初始化 - 语义增强: {self.semantic_enabled}")
    
    async def _get_semantic_processor(self):
        """延迟初始化语义处理器"""
        if self.semantic_processor is None and self.semantic_enabled:
            try:
                from semantic_search_engine import SemanticQueryProcessor
                self.semantic_processor = SemanticQueryProcessor()
                logger.info("语义查询处理器初始化完成")
            except Exception as e:
                logger.warning(f"语义处理器初始化失败: {e}")
                self.semantic_processor = None
        return self.semantic_processor
    
    async def enhance_keywords_analysis(self, analysis_result: Dict[str, Any], original_query: str) -> Dict[str, Any]:
        """增强LLM生成的关键词分析结果 - 核心功能"""
        
        if not analysis_result:
            logger.warning("无分析结果可供增强")
            return analysis_result
        
        try:
            logger.info(f"开始增强关键词分析: {original_query}")
            start_time = time.time()
            
            # 保持原有结构完全不变
            enhanced_analysis = analysis_result.copy()
            
            # 添加语义增强（可选，不破坏现有结构）
            if self.semantic_enabled:
                semantic_enhancements = await self._generate_semantic_enhancements(
                    analysis_result, original_query
                )
                
                # 添加新字段，不修改现有字段
                if semantic_enhancements:
                    enhanced_analysis.update(semantic_enhancements)
                    logger.info("✅ 语义增强添加成功")
                else:
                    logger.info("📍 语义增强为空，保持原始结果")
            
            end_time = time.time()
            logger.info(f"关键词增强完成，耗时: {end_time - start_time:.2f}秒")
            
            return enhanced_analysis
            
        except Exception as e:
            logger.error(f"❌ 关键词增强失败: {e}")
            if self.fallback_to_traditional:
                logger.info("回退到原始关键词分析")
                return analysis_result
            else:
                raise
    
    async def _generate_semantic_enhancements(self, analysis: Dict[str, Any], query: str) -> Dict[str, Any]:
        """生成语义增强信息"""
        try:
            semantic_processor = await self._get_semantic_processor()
            if not semantic_processor:
                return {}
            
            enhancements = {}
            
            # 1. 生成查询语义向量
            try:
                query_vector = await semantic_processor.encode_query(query)
                enhancements["query_vector"] = query_vector.tolist()  # 序列化为列表
                enhancements["vector_dimension"] = len(query_vector)
                logger.debug(f"查询向量生成完成，维度: {len(query_vector)}")
            except Exception as e:
                logger.warning(f"查询向量生成失败: {e}")
            
            # 2. 增强关键词的语义表示
            hierarchical_keywords = analysis.get("hierarchical_keywords", {})
            if hierarchical_keywords:
                semantic_keywords = await self._enhance_hierarchical_keywords(
                    hierarchical_keywords, semantic_processor
                )
                enhancements["semantic_keywords"] = semantic_keywords
            
            # 3. 生成语义扩展建议
            semantic_suggestions = await self._generate_semantic_suggestions(
                query, analysis, semantic_processor
            )
            if semantic_suggestions:
                enhancements["semantic_suggestions"] = semantic_suggestions
            
            # 4. 添加语义搜索配置
            enhancements["semantic_search_enabled"] = True
            enhancements["enhancement_timestamp"] = time.time()
            
            return enhancements
            
        except Exception as e:
            logger.error(f"语义增强生成失败: {e}")
            return {}
    
    async def _enhance_hierarchical_keywords(self, hierarchical: Dict[str, Any], processor) -> Dict[str, Any]:
        """为分层关键词添加语义向量"""
        try:
            enhanced_keywords = {}
            
            for level, level_data in hierarchical.items():
                if not isinstance(level_data, dict) or 'terms' not in level_data:
                    continue
                
                terms = level_data.get('terms', [])
                if not terms:
                    continue
                
                try:
                    # 为每个层级的关键词生成向量
                    term_vectors = await processor.encode_batch(terms)
                    
                    enhanced_keywords[level] = {
                        **level_data,  # 保留原有数据
                        'term_vectors': term_vectors.tolist(),  # 添加向量信息
                        'vector_count': len(term_vectors)
                    }
                    
                    logger.debug(f"层级 {level} 的 {len(terms)} 个关键词向量化完成")
                    
                except Exception as e:
                    logger.warning(f"层级 {level} 关键词向量化失败: {e}")
                    # 保留原有数据，不添加向量信息
                    enhanced_keywords[level] = level_data
            
            return enhanced_keywords
            
        except Exception as e:
            logger.error(f"分层关键词增强失败: {e}")
            return hierarchical  # 返回原始数据
    
    async def _generate_semantic_suggestions(self, query: str, analysis: Dict[str, Any], processor) -> Dict[str, Any]:
        """基于语义分析生成扩展建议"""
        try:
            suggestions = {
                "expansion_method": "semantic_similarity",
                "confidence_threshold": 0.7,
                "suggestions": []
            }
            
            # 从现有关键词中选择代表性术语进行语义扩展
            hierarchical = analysis.get("hierarchical_keywords", {})
            representative_terms = []
            
            # 收集各层级的代表性术语
            for level in ["exact_terms", "core_synonyms"]:
                level_data = hierarchical.get(level, {})
                terms = level_data.get("terms", [])
                representative_terms.extend(terms[:2])  # 每层取前2个
            
            if representative_terms:
                # 为代表性术语生成向量（用于后续语义匹配）
                try:
                    term_vectors = await processor.encode_batch(representative_terms)
                    suggestions["representative_vectors"] = term_vectors.tolist()
                    suggestions["representative_terms"] = representative_terms
                    
                    logger.debug(f"生成了 {len(representative_terms)} 个代表性术语的语义建议")
                    
                except Exception as e:
                    logger.warning(f"代表性术语向量化失败: {e}")
            
            # 添加查询复杂度评估
            domain = analysis.get("domain", "")
            core_concepts = analysis.get("core_concepts", [])
            
            complexity_score = self._assess_query_complexity(query, core_concepts, domain)
            suggestions["query_complexity"] = complexity_score
            suggestions["recommended_search_strategy"] = self._recommend_search_strategy(complexity_score)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"语义建议生成失败: {e}")
            return {}
    
    def _assess_query_complexity(self, query: str, concepts: List[str], domain: str) -> float:
        """评估查询复杂度"""
        try:
            complexity = 0.0
            
            # 基于查询长度
            query_length_factor = min(len(query.split()) / 10.0, 1.0)
            complexity += query_length_factor * 0.3
            
            # 基于概念数量
            concept_factor = min(len(concepts) / 5.0, 1.0)
            complexity += concept_factor * 0.4
            
            # 基于领域专业性
            specialized_domains = ["medical", "engineering", "physics", "chemistry", "biology"]
            if any(domain_term in domain.lower() for domain_term in specialized_domains):
                complexity += 0.3
            else:
                complexity += 0.1
            
            return min(complexity, 1.0)
            
        except Exception:
            return 0.5  # 默认中等复杂度
    
    def _recommend_search_strategy(self, complexity: float) -> str:
        """基于复杂度推荐搜索策略"""
        if complexity >= 0.8:
            return "precision_focused"
        elif complexity <= 0.3:
            return "recall_focused"
        else:
            return "balanced"
    
    def enhance_boolean_query(self, analysis: Dict[str, Any]) -> Optional[str]:
        """增强布尔查询（保持兼容性）"""
        try:
            # 优先使用LLM生成的布尔查询
            if analysis.get("optimized_boolean_query"):
                return analysis["optimized_boolean_query"]
            
            # 如果有语义增强信息，可以生成更智能的查询
            if analysis.get("semantic_keywords"):
                return self._generate_semantic_aware_boolean_query(analysis)
            
            # 回退到权重驱动构建（保持现有逻辑）
            return None  # 让现有系统处理
            
        except Exception as e:
            logger.error(f"布尔查询增强失败: {e}")
            return None
    
    def _generate_semantic_aware_boolean_query(self, analysis: Dict[str, Any]) -> str:
        """基于语义信息生成智能布尔查询"""
        try:
            semantic_keywords = analysis.get("semantic_keywords", {})
            search_strategy = analysis.get("search_strategy", "balanced")
            
            # 提取高相似度的关键词
            high_similarity_terms = []
            
            for level, level_data in semantic_keywords.items():
                terms = level_data.get("terms", [])
                weight = level_data.get("weight", 0.5)
                
                if weight >= 0.8:  # 高权重术语
                    high_similarity_terms.extend(terms[:2])  # 每层取前2个
            
            if not high_similarity_terms:
                return ""
            
            # 基于策略构建查询
            if search_strategy == "precision_focused":
                # 精准策略：使用AND连接高权重术语
                quoted_terms = [f'"{term}"' if ' ' in term else term for term in high_similarity_terms[:3]]
                return " AND ".join(quoted_terms)
            
            elif search_strategy == "recall_focused":
                # 召回策略：使用OR连接更多术语
                quoted_terms = [f'"{term}"' if ' ' in term else term for term in high_similarity_terms[:6]]
                return " OR ".join(quoted_terms)
            
            else:  # balanced
                # 平衡策略：组合AND和OR
                if len(high_similarity_terms) >= 2:
                    primary = high_similarity_terms[0]
                    secondary = high_similarity_terms[1:][:3]
                    
                    primary_quoted = f'"{primary}"' if ' ' in primary else primary
                    secondary_quoted = [f'"{term}"' if ' ' in term else term for term in secondary]
                    
                    if secondary_quoted:
                        secondary_part = " OR ".join(secondary_quoted)
                        return f"{primary_quoted} AND ({secondary_part})"
                    else:
                        return primary_quoted
                else:
                    term = high_similarity_terms[0]
                    return f'"{term}"' if ' ' in term else term
            
        except Exception as e:
            logger.error(f"语义感知布尔查询生成失败: {e}")
            return ""
    
    def extract_enhanced_keywords_for_search(self, analysis: Dict[str, Any]) -> List[str]:
        """提取增强后的关键词用于传统搜索兜底"""
        try:
            keywords = []
            
            # 从语义增强结果中提取
            semantic_suggestions = analysis.get("semantic_suggestions", {})
            if semantic_suggestions.get("representative_terms"):
                keywords.extend(semantic_suggestions["representative_terms"])
            
            # 从传统关键词层级中提取
            hierarchical = analysis.get("hierarchical_keywords", {})
            for level in ["exact_terms", "core_synonyms", "related_terms"]:
                level_data = hierarchical.get(level, {})
                terms = level_data.get("terms", [])
                keywords.extend(terms[:3])  # 每层取前3个
            
            # 去重并限制数量
            unique_keywords = list(dict.fromkeys(keywords))[:10]
            
            return unique_keywords
            
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []
    
    async def close(self):
        """清理资源"""
        try:
            if self.semantic_processor:
                if hasattr(self.semantic_processor, '_ensure_initialized'):
                    self.semantic_processor.is_initialized = False
                    if hasattr(self.semantic_processor, 'model'):
                        self.semantic_processor.model = None
                logger.info("查询增强器资源清理完成")
        except Exception as e:
            logger.warning(f"查询增强器清理失败: {e}")

# 工厂函数
def create_query_enhancer() -> QueryEnhancer:
    """创建查询增强器实例"""
    return QueryEnhancer()

# 测试函数
async def test_query_enhancer():
    """测试查询增强器"""
    print("🔬 测试查询增强器...")
    
    enhancer = QueryEnhancer()
    
    # 模拟LLM生成的分析结果
    mock_analysis = {
        "original_query": "机器学习在医疗诊断中的应用",
        "core_concepts": ["machine learning", "medical diagnosis"],
        "hierarchical_keywords": {
            "exact_terms": {
                "terms": ["machine learning", "medical diagnosis", "healthcare AI"],
                "weight": 1.0
            },
            "core_synonyms": {
                "terms": ["artificial intelligence", "ML", "computer-aided diagnosis"],
                "weight": 0.9
            },
            "related_terms": {
                "terms": ["deep learning", "neural networks", "pattern recognition"],
                "weight": 0.5
            }
        },
        "domain": "medical AI",
        "search_strategy": "balanced"
    }
    
    try:
        enhanced_result = await enhancer.enhance_keywords_analysis(
            mock_analysis, 
            "机器学习在医疗诊断中的应用"
        )
        
        print("✅ 关键词增强完成")
        print(f"原始字段数量: {len(mock_analysis)}")
        print(f"增强后字段数量: {len(enhanced_result)}")
        
        # 显示新增的语义字段
        new_fields = set(enhanced_result.keys()) - set(mock_analysis.keys())
        if new_fields:
            print(f"新增语义字段: {list(new_fields)}")
        
        # 测试布尔查询增强
        boolean_query = enhancer.enhance_boolean_query(enhanced_result)
        if boolean_query:
            print(f"增强布尔查询: {boolean_query}")
        
        # 测试关键词提取
        keywords = enhancer.extract_enhanced_keywords_for_search(enhanced_result)
        print(f"提取关键词: {keywords[:5]}")  # 显示前5个
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    finally:
        await enhancer.close()

if __name__ == "__main__":
    asyncio.run(test_query_enhancer())