#!/usr/bin/env python3
"""
ScholarPy修复测试脚本
测试Google Scholar HTTP 429错误的修复效果
"""

import asyncio
import logging
from multi_source_engine import MultiSourceEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_scholar_search():
    """测试ScholarPy搜索功能"""
    print("=" * 60)
    print("🧪 开始测试ScholarPy修复效果")
    print("=" * 60)
    
    # 创建搜索引擎实例
    engine = MultiSourceEngine()
    
    # 测试查询
    test_queries = [
        "nanocatalysts methane dry reforming",
        "machine learning artificial intelligence", 
        "quantum computing algorithms"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📋 测试 {i}/{len(test_queries)}: {query}")
        print("-" * 40)
        
        try:
            # 执行搜索
            papers = await engine.search_parallel(query, max_results=10)
            
            if papers:
                print(f"✅ 搜索成功！获得 {len(papers)} 篇论文")
                
                # 显示前3个结果
                for j, paper in enumerate(papers[:3], 1):
                    print(f"  {j}. {paper.title[:80]}...")
                    print(f"     来源: {paper.source}, 年份: {paper.year}")
            else:
                print("⚠️ 搜索结果为空")
                
        except Exception as e:
            print(f"❌ 搜索失败: {e}")
        
        # 在测试之间添加延迟
        if i < len(test_queries):
            print("⏳ 等待30秒后进行下一次测试...")
            await asyncio.sleep(30)
    
    # 关闭引擎
    await engine.close()
    
    print("\n" + "=" * 60)
    print("🏁 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_scholar_search())