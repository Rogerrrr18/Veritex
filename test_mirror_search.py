#!/usr/bin/env python3
"""
测试Google Scholar镜像搜索功能
"""
import asyncio
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_mirror_api():
    """测试镜像API单独功能"""
    from scholar_mirror_api import ScholarMirrorAPI
    
    print("🔬 测试Google Scholar镜像API...")
    
    api = ScholarMirrorAPI()
    
    # 测试查询
    test_queries = [
        "machine learning",
        "deep learning",
        "artificial intelligence"
    ]
    
    for query in test_queries:
        print(f"\n📋 测试查询: {query}")
        try:
            results = await api.search(query, limit=5)
            print(f"✅ 镜像搜索成功，获得 {len(results)} 篇论文")
            
            if results:
                for i, paper in enumerate(results[:2]):  # 显示前2篇
                    print(f"   {i+1}. {paper.title}")
                    print(f"      作者: {', '.join(paper.authors)}")
                    print(f"      年份: {paper.year}")
                    print(f"      引用: {paper.citations}")
            else:
                print("   📍 无搜索结果")
                
        except Exception as e:
            print(f"❌ 镜像搜索错误: {e}")
    
    await api.close()
    print("\n✅ 镜像API测试完成")

async def test_integrated_search():
    """测试集成的多源搜索（包含镜像补偿）"""
    from multi_source_engine import MultiSourceEngine
    
    print("\n🔧 测试集成的多源搜索...")
    
    engine = MultiSourceEngine()
    
    test_query = "photocatalyst"
    print(f"\n📋 测试查询: {test_query}")
    
    try:
        results = await engine.search_parallel(test_query, max_results=20)
        print(f"✅ 多源搜索完成，总计获得 {len(results)} 篇论文")
        
        # 按数据源统计
        source_stats = {}
        for paper in results:
            source = paper.source
            source_stats[source] = source_stats.get(source, 0) + 1
        
        print("📊 数据源统计:")
        for source, count in source_stats.items():
            print(f"   {source}: {count} 篇")
        
        # 显示前3篇论文
        if results:
            print("\n📄 前3篇论文:")
            for i, paper in enumerate(results[:3]):
                print(f"{i+1}. [{paper.source}] {paper.title}")
                if paper.year:
                    print(f"   年份: {paper.year}")
                if paper.citations:
                    print(f"   引用: {paper.citations}")
                
    except Exception as e:
        print(f"❌ 多源搜索错误: {e}")
    
    await engine.close()
    print("✅ 集成搜索测试完成")

async def main():
    """主测试函数"""
    print("🚀 开始测试Google Scholar镜像搜索解决方案...")
    
    # 测试单独的镜像API
    await test_mirror_api()
    
    # 测试集成的多源搜索
    await test_integrated_search()
    
    print("\n🎉 所有测试完成!")

if __name__ == "__main__":
    asyncio.run(main())