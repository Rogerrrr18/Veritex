#!/usr/bin/env python3
"""
测试修复后的搜索功能
"""

import asyncio
import requests
import json
import sys

async def test_search_api():
    """测试搜索API接口"""
    
    # 测试数据
    test_queries = [
        "光热甲烷干重整",
        "machine learning",
        "你好"
    ]
    
    print("🧪 测试搜索API修复情况")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n测试 {i}: {query}")
        print("-" * 30)
        
        try:
            # 发送请求
            response = requests.post(
                "http://127.0.0.1:8000/search_papers",
                json={
                    "query": query,
                    "max_results": 3,
                    "enable_expansion": True
                },
                timeout=30
            )
            
            # 检查响应
            if response.status_code == 200:
                data = response.json()
                success = data.get('success', False)
                error = data.get('error')
                papers = data.get('data', {}).get('papers', [])
                
                print(f"✅ API响应成功")
                print(f"🔍 搜索成功: {success}")
                
                if error:
                    print(f"❌ 错误: {error}")
                else:
                    print(f"📚 找到论文: {len(papers)} 篇")
                    
                    for j, paper in enumerate(papers[:2], 1):
                        title = paper.get('title', '无标题')[:50]
                        print(f"   {j}. {title}...")
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                print(f"响应: {response.text[:200]}...")
                
        except requests.exceptions.Timeout:
            print("❌ 请求超时")
        except requests.exceptions.ConnectionError:
            print("❌ 连接失败 - 服务器可能未启动")
        except Exception as e:
            print(f"❌ 测试失败: {e}")

def test_direct_import():
    """测试直接导入模块"""
    print("\n🧪 测试模块导入")
    print("=" * 50)
    
    try:
        from main import PaperGodSearchEngine
        print("✅ 成功导入 PaperGodSearchEngine")
        
        # 测试实例化
        engine = PaperGodSearchEngine(enable_mcp=False)
        print("✅ 成功实例化搜索引擎")
        
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Paper God - 搜索功能修复测试")
    print("🐛 修复: name 'Any' is not defined")
    print("=" * 60)
    
    # 测试1: 模块导入
    import_success = test_direct_import()
    
    if import_success:
        # 测试2: API接口  
        asyncio.run(test_search_api())
    else:
        print("\n❌ 模块导入失败，跳过API测试")
    
    print("\n✅ 测试完成")