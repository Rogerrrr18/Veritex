#!/usr/bin/env python3
"""
快速验证搜索优化效果
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))

from multi_source_engine import MultiSourceEngine

async def quick_test():
    """快速测试搜索优化"""
    print("🔍 快速验证搜索优化效果")
    print("=" * 50)
    
    engine = MultiSourceEngine()
    
    # 快速测试：30篇论文
    query = "machine learning applications"
    target = 30
    
    print(f"查询: {query}")
    print(f"目标: {target}篇")
    
    try:
        papers = await engine.search_parallel_with_filters(
            query=query,
            max_results=target,
            sources=['scholar_dock', 'arxiv', 'crossref']
        )
        
        result_count = len(papers)
        print(f"结果: {result_count}篇")
        
        # 数据源统计
        sources = {}
        for p in papers:
            sources[p.source] = sources.get(p.source, 0) + 1
        
        print("数据源分布:")
        for src, count in sources.items():
            print(f"  {src}: {count}篇")
        
        # 评估
        success_rate = result_count / target
        if success_rate >= 0.8:
            print("✅ 测试通过：达到80%以上目标")
        elif success_rate >= 0.6:
            print("👍 测试良好：达到60%以上目标")
        else:
            print("⚠️ 测试需要改进")
        
        print(f"达成率: {success_rate:.1%}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(quick_test())