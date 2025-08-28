#!/usr/bin/env python3
"""
测试ScholarDock集成功能
验证新增的高效Google Scholar爬虫和增强字段
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(__file__))

from multi_source_engine import MultiSourceEngine

async def test_scholar_dock_integration():
    """测试ScholarDock集成到多源引擎"""
    print("=" * 60)
    print("🧪 测试ScholarDock集成功能")
    print("=" * 60)
    
    # 初始化搜索引擎
    try:
        engine = MultiSourceEngine()
        print("✅ 多源搜索引擎初始化成功")
    except Exception as e:
        print(f"❌ 搜索引擎初始化失败: {e}")
        return
    
    # 测试查询
    query = "machine learning neural networks"
    max_results = 15
    
    print(f"🔍 测试查询: {query}")
    print(f"📊 目标结果数: {max_results}")
    print()
    
    try:
        # 执行搜索
        results = await engine.search_parallel_with_filters(
            query=query,
            max_results=max_results
        )
        
        print(f"✅ 搜索完成，共获得 {len(results)} 篇论文")
        
        # 统计来源分布
        sources = {}
        for paper in results:
            source = getattr(paper, 'source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print("\n📊 结果来源分布:")
        for source, count in sources.items():
            print(f"  {source}: {count} 篇")
        
        # 检查ScholarDock增强字段
        print("\n🔬 ScholarDock增强字段测试:")
        scholar_dock_papers = [p for p in results if hasattr(p, 'source') and p.source == 'scholar_dock']
        
        if scholar_dock_papers:
            print(f"  找到 {len(scholar_dock_papers)} 篇ScholarDock论文")
            
            for i, paper in enumerate(scholar_dock_papers[:3]):
                print(f"\n  论文 {i+1}:")
                print(f"    标题: {paper.title[:60]}...")
                print(f"    年份: {paper.year}")
                print(f"    引用数: {paper.citations}")
                print(f"    年均引用: {paper.citations_per_year}")
                print(f"    期刊: {paper.venue}")
                print(f"    出版商: {paper.publisher}")
                print(f"    摘要长度: {len(paper.description) if paper.description else 0} 字符")
        else:
            print("  ⚠️ 未找到ScholarDock来源的论文")
        
        # 验证增强字段
        enhanced_fields_count = 0
        for paper in results:
            if (hasattr(paper, 'citations_per_year') and paper.citations_per_year > 0) or \
               (hasattr(paper, 'venue') and paper.venue) or \
               (hasattr(paper, 'publisher') and paper.publisher):
                enhanced_fields_count += 1
        
        print(f"\n📈 增强字段统计:")
        print(f"  包含增强字段的论文: {enhanced_fields_count}/{len(results)}")
        
    except Exception as e:
        print(f"❌ 搜索测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_scholar_dock_direct():
    """直接测试ScholarDockSpider"""
    print("\n" + "=" * 60)
    print("🔍 直接测试ScholarDockSpider")
    print("=" * 60)
    
    try:
        from scholar_dock_spider import ScholarDockSpider
        
        async with ScholarDockSpider() as spider:
            papers = await spider.search("artificial intelligence", limit=10)
        
        print(f"✅ 直接搜索成功，获得 {len(papers)} 篇论文")
        
        if papers:
            print("\n📚 前3篇论文详情:")
            for i, paper in enumerate(papers[:3]):
                print(f"\n  {i+1}. {paper.title}")
                print(f"     年份: {paper.year}")
                print(f"     引用: {paper.citations} (年均: {paper.citations_per_year})")
                print(f"     期刊: {paper.venue}")
                print(f"     作者: {', '.join(paper.authors[:2])}{'...' if len(paper.authors) > 2 else ''}")
        
    except Exception as e:
        print(f"❌ 直接测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_scholar_dock_integration())
    asyncio.run(test_scholar_dock_direct())