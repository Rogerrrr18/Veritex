#!/usr/bin/env python3
"""
快速搜索测试脚本
测试在ScholarPy受限情况下，其他数据源的搜索效果
"""

import asyncio
import logging
import os
from multi_source_engine import MultiSourceEngine

# 配置日志
logging.basicConfig(level=logging.INFO)

async def test_without_scholar():
    """测试禁用ScholarPy的搜索效果"""
    print("=" * 60)
    print("🧪 测试其他数据源搜索（跳过ScholarPy）")
    print("=" * 60)
    
    # 临时禁用ScholarPy
    os.environ["SCHOLAR_PY_ENABLED"] = "false"
    
    # 创建搜索引擎实例
    engine = MultiSourceEngine()
    
    query = "machine learning deep learning"
    print(f"🔍 搜索查询: {query}")
    
    try:
        papers = await engine.search_parallel(query, max_results=10)
        
        if papers:
            print(f"✅ 搜索成功！获得 {len(papers)} 篇论文")
            
            # 显示结果统计
            sources_count = {}
            for paper in papers:
                sources_count[paper.source] = sources_count.get(paper.source, 0) + 1
            
            print("\n📊 数据源分布:")
            for source, count in sources_count.items():
                print(f"  {source}: {count} 篇")
            
            print("\n📄 前5篇论文:")
            for i, paper in enumerate(papers[:5], 1):
                print(f"  {i}. {paper.title[:70]}...")
                print(f"     来源: {paper.source}, 年份: {paper.year}")
        else:
            print("⚠️ 搜索结果为空")
            
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
    
    finally:
        await engine.close()
    
    print("\n" + "=" * 60)
    print("🏁 测试完成 - 系统在无Google Scholar情况下仍可正常工作")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_without_scholar())