#!/usr/bin/env python3
"""
测试scholarly库domain错误修复
"""
import asyncio
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_scholarly_search():
    """测试修复后的scholarly搜索功能"""
    from multi_source_engine import ScholarlyAPI
    
    print("🔬 测试scholarly库搜索功能...")
    
    # 创建API实例
    api = ScholarlyAPI()
    
    # 测试查询
    test_queries = [
        "machine learning",
        "photocatalyst",
        "covid-19 vaccine"
    ]
    
    for query in test_queries:
        print(f"\n📋 测试查询: {query}")
        try:
            results = await api.search(query, limit=3)
            print(f"✅ 搜索成功，获得 {len(results)} 篇论文")
            
            if results:
                print(f"   第一篇: {results[0].title[:50]}...")
            else:
                print("   📍 无搜索结果，可能是访问限制")
                
        except Exception as e:
            error_str = str(e)
            if "domain" in error_str.lower():
                print(f"❌ Domain错误仍然存在: {e}")
            else:
                print(f"⚠️ 其他错误: {e}")
    
    await api.close()
    print("\n✅ scholarly测试完成")

if __name__ == "__main__":
    asyncio.run(test_scholarly_search())