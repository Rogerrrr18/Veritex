#!/usr/bin/env python3
"""
测试scholarly库的Google Scholar功能
"""
import asyncio
import time
from typing import List

async def test_scholarly_simple():
    """简单测试scholarly库是否能正常工作"""
    try:
        from scholarly import scholarly
        print("✅ scholarly库导入成功")
        
        # 测试简单搜索
        print("🔍 开始测试Google Scholar搜索...")
        start_time = time.time()
        
        search_query = "machine learning"
        search_iterator = scholarly.search_pubs(search_query)
        
        print(f"🎯 搜索查询: {search_query}")
        
        results = []
        max_results = 3  # 只测试获取3篇论文
        
        for i in range(max_results):
            try:
                # 设置每次获取的超时时间
                result = await asyncio.wait_for(
                    asyncio.to_thread(next, search_iterator),
                    timeout=10.0  # 10秒超时
                )
                
                if result:
                    bib = result.get('bib', {})
                    title = bib.get('title', 'No title')
                    authors = bib.get('author', [])
                    year = bib.get('pub_year', 'Unknown')
                    citations = result.get('num_citations', 0)
                    
                    print(f"\n📄 论文 {i+1}:")
                    print(f"   标题: {title[:80]}...")
                    print(f"   作者: {authors[:3] if isinstance(authors, list) else [authors]}")
                    print(f"   年份: {year}")
                    print(f"   引用数: {citations}")
                    
                    results.append({
                        'title': title,
                        'authors': authors,
                        'year': year,
                        'citations': citations
                    })
                    
                # 添加延迟避免被限制
                await asyncio.sleep(1.0)
                
            except asyncio.TimeoutError:
                print(f"⚠️ 获取论文 {i+1} 超时")
                break
            except StopIteration:
                print(f"📚 已获取所有可用结果")
                break
            except Exception as e:
                print(f"❌ 获取论文 {i+1} 时出错: {e}")
                break
        
        elapsed_time = time.time() - start_time
        print(f"\n✅ 测试完成!")
        print(f"📊 耗时: {elapsed_time:.2f}秒")
        print(f"📚 成功获取: {len(results)} 篇论文")
        
        return len(results) > 0
        
    except ImportError:
        print("❌ scholarly库未安装，请运行: pip install scholarly")
        return False
    except Exception as e:
        print(f"❌ scholarly测试失败: {e}")
        return False

async def test_multi_source_engine():
    """测试集成了Google Scholar的多源搜索引擎"""
    try:
        from multi_source_engine import MultiSourceEngine
        print("\n🔧 测试多源搜索引擎...")
        
        engine = MultiSourceEngine()
        
        # 检查Google Scholar是否被正确初始化
        if engine.google_scholar:
            print("✅ Google Scholar API已初始化")
        else:
            print("❌ Google Scholar API未初始化")
            return False
        
        # 简单搜索测试
        print("🔍 执行简单多源搜索测试...")
        start_time = time.time()
        
        results = await engine.search_parallel_with_filters(
            query="artificial intelligence",
            max_results=5
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"📊 搜索结果:")
        print(f"   耗时: {elapsed_time:.2f}秒")
        print(f"   获得论文: {len(results)} 篇")
        
        # 按数据源统计
        source_stats = {}
        for paper in results:
            source = paper.source
            source_stats[source] = source_stats.get(source, 0) + 1
        
        print(f"📈 数据源分布:")
        for source, count in source_stats.items():
            print(f"   {source}: {count} 篇")
        
        await engine.close()
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ 多源搜索引擎测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始scholarly和Google Scholar功能测试")
    print("=" * 50)
    
    # 测试1: scholarly库基础功能
    scholarly_ok = await test_scholarly_simple()
    
    # 测试2: 多源搜索引擎集成
    engine_ok = await test_multi_source_engine()
    
    print("\n" + "=" * 50)
    print("📋 测试总结:")
    print(f"   scholarly库基础功能: {'✅ 通过' if scholarly_ok else '❌ 失败'}")
    print(f"   多源引擎集成功能: {'✅ 通过' if engine_ok else '❌ 失败'}")
    
    if scholarly_ok and engine_ok:
        print("🎉 所有测试通过！Google Scholar功能正常")
        return True
    else:
        print("⚠️ 部分测试失败，请检查配置")
        return False

if __name__ == "__main__":
    asyncio.run(main())