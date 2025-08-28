#!/usr/bin/env python3
"""
测试统一布尔搜索功能
验证所有搜索源都能正确使用统一的布尔查询
"""
import asyncio
import sys
import os
import json

# 添加项目根目录到路径
sys.path.append(os.path.dirname(__file__))

from multi_source_engine import MultiSourceEngine

async def test_unified_boolean_search():
    """测试统一布尔搜索功能"""
    print("=" * 60)
    print("🧪 测试统一布尔搜索功能")
    print("=" * 60)
    
    # 初始化搜索引擎
    try:
        engine = MultiSourceEngine()
        print("✅ 搜索引擎初始化成功")
    except Exception as e:
        print(f"❌ 搜索引擎初始化失败: {e}")
        return
    
    # 测试查询
    query = "machine learning"
    
    # 模拟LLM分析结果
    mock_analysis = {
        "optimized_boolean_query": '"deep learning" AND (neural OR networks)',
        "hierarchical_keywords": {
            "exact_terms": {"terms": ["deep learning"], "weight": 1.0},
            "core_synonyms": {"terms": ["neural networks", "artificial intelligence"], "weight": 0.8},
            "related_terms": {"terms": ["machine learning", "AI"], "weight": 0.6}
        },
        "search_strategy": "balanced"
    }
    
    print(f"🔍 原始查询: {query}")
    print(f"🧠 LLM优化布尔查询: {mock_analysis['optimized_boolean_query']}")
    print()
    
    # 测试统一布尔查询构建
    print("📋 测试各搜索源的查询适配:")
    unified_queries = engine._build_unified_boolean_query(query, mock_analysis)
    
    for source, adapted_query in unified_queries.items():
        print(f"  {source}: {adapted_query}")
    
    print()
    
    # 测试实际搜索（少量结果）
    print("🚀 执行统一布尔搜索测试...")
    try:
        results = await engine.search_parallel_with_filters(
            query=query,
            max_results=10,  # 少量测试
            analysis=mock_analysis
        )
        
        print(f"✅ 搜索完成，共获得 {len(results)} 篇论文")
        
        # 统计来源分布
        sources = {}
        for paper in results:
            source = getattr(paper, 'source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print("📊 结果来源分布:")
        for source, count in sources.items():
            print(f"  {source}: {count} 篇")
            
        # 显示前3篇论文的标题
        print("\n📚 前3篇论文:")
        for i, paper in enumerate(results[:3]):
            title = getattr(paper, 'title', 'No title')
            source = getattr(paper, 'source', 'unknown')
            print(f"  {i+1}. [{source}] {title}")
        
    except Exception as e:
        print(f"❌ 搜索测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_query_adaptation():
    """测试查询适配功能"""
    print("\n" + "=" * 60)
    print("🔧 测试查询适配功能")
    print("=" * 60)
    
    engine = MultiSourceEngine()
    
    # 测试不同复杂度的布尔查询
    test_queries = [
        '"machine learning" AND (neural OR networks)',
        '("deep learning" OR "neural networks") AND classification',
        'artificial AND intelligence AND NOT robotics',
        'simple query'
    ]
    
    for query in test_queries:
        print(f"\n🔍 原始查询: {query}")
        unified_queries = engine._build_unified_boolean_query(query, None)
        
        for source, adapted_query in unified_queries.items():
            if adapted_query != query:  # 只显示有变化的
                print(f"  {source}: {adapted_query}")

if __name__ == "__main__":
    asyncio.run(test_unified_boolean_search())
    asyncio.run(test_query_adaptation())