#!/usr/bin/env python3
"""
温和优化测试脚本
测试User-Agent轮换和延迟随机化的效果
"""

import asyncio
import logging
from multi_source_engine import MultiSourceEngine

logging.basicConfig(level=logging.INFO)

async def test_gentle_improvements():
    """测试温和优化的效果"""
    print("=" * 60)
    print("🔧 测试ScholarPy温和优化效果")
    print("=" * 60)
    
    engine = MultiSourceEngine()
    
    # 简单测试查询
    query = "artificial intelligence"
    print(f"🔍 测试查询: {query}")
    
    try:
        papers = await engine.search_parallel(query, max_results=5)
        
        if papers:
            print(f"✅ 搜索成功！获得 {len(papers)} 篇论文")
            
            # 显示数据源分布
            sources = {}
            for paper in papers:
                sources[paper.source] = sources.get(paper.source, 0) + 1
            
            print("📊 数据源分布:")
            for source, count in sources.items():
                print(f"  {source}: {count} 篇")
        else:
            print("⚠️ 搜索结果为空")
            
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
    
    await engine.close()
    print("\n🏁 温和优化测试完成")

if __name__ == "__main__":
    asyncio.run(test_gentle_improvements())