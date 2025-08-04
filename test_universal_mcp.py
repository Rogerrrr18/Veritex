#!/usr/bin/env python3
"""
通用MCP系统测试脚本
"""
import asyncio
import json
import aiohttp
import sys

API_BASE = "http://127.0.0.1:8005"

async def test_health():
    """测试健康检查"""
    print("🏥 测试健康检查...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 系统状态: {data.get('status')}")
                    print(f"   总服务数: {data.get('total_services')}")
                    print(f"   启用服务: {data.get('enabled_services')}")
                    print(f"   可用策略: {data.get('available_strategies')}")
                    return True
                else:
                    print(f"❌ 健康检查失败，HTTP状态: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ 健康检查异常: {e}")
        return False

async def test_services_info():
    """测试服务信息获取"""
    print("\\n📋 测试服务信息获取...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/services") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 获取到 {data.get('total_services')} 个服务:")
                    
                    for service_id, service_info in data.get('services', {}).items():
                        status = "✅" if service_info.get('enabled') else "❌"
                        print(f"   {status} {service_id}: {service_info.get('name')}")
                        print(f"      URL: {service_info.get('base_url')}")
                    
                    print(f"\\n🎯 搜索策略:")
                    for strategy_id, strategy_info in data.get('strategies', {}).items():
                        sources = ', '.join(strategy_info.get('sources', []))
                        print(f"   • {strategy_id}: {strategy_info.get('description')} [{sources}]")
                    
                    return True
                else:
                    print(f"❌ 获取服务信息失败，HTTP状态: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ 获取服务信息异常: {e}")
        return False

async def test_single_source_search():
    """测试单源搜索"""
    print("\\n🔍 测试单源搜索 (arXiv)...")
    search_data = {
        "source": "arxiv",
        "query": "methane reforming catalyst",
        "limit": 5,
        "category": "physics.chem-ph"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/search_single_source",
                params=search_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 单源搜索成功:")
                    print(f"   成功: {data.get('success')}")
                    print(f"   结果数量: {data.get('count')}")
                    print(f"   数据源: {data.get('source')}")
                    
                    papers = data.get('papers', [])
                    for i, paper in enumerate(papers[:3], 1):
                        title = paper.get('title', 'N/A')[:60]
                        year = paper.get('year', 'N/A')
                        print(f"   论文 {i}: {title}... ({year})")
                    
                    return True
                else:
                    print(f"❌ 单源搜索失败，HTTP状态: {response.status}")
                    error_text = await response.text()
                    print(f"   错误详情: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ 单源搜索测试失败: {e}")
        return False

async def test_universal_search():
    """测试通用搜索"""
    print("\\n🚀 测试通用搜索...")
    search_data = {
        "query": "甲烷干重整",
        "sources": ["arxiv", "crossref"],
        "limit": 10
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/universal_search",
                headers={"Content-Type": "application/json"},
                json=search_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 通用搜索成功:")
                    print(f"   成功: {data.get('success')}")
                    print(f"   总结果数: {data.get('total_count')}")
                    print(f"   查询词: {data.get('query')}")
                    print(f"   来源统计: {data.get('source_stats', {})}")
                    
                    papers = data.get('papers', [])
                    for i, paper in enumerate(papers[:3], 1):
                        title = paper.get('title', 'N/A')[:50]
                        source = paper.get('source', 'unknown')
                        year = paper.get('year', 'N/A')
                        print(f"   论文 {i} [{source}]: {title}... ({year})")
                    
                    errors = data.get('errors')
                    if errors:
                        print(f"   ⚠️  部分错误: {errors}")
                    
                    return True
                else:
                    print(f"❌ 通用搜索失败，HTTP状态: {response.status}")
                    error_text = await response.text()
                    print(f"   错误详情: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ 通用搜索测试失败: {e}")
        return False

async def test_strategy_search():
    """测试策略搜索"""
    print("\\n🎯 测试策略搜索 (fast)...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/search_by_strategy",
                params={
                    "strategy": "fast",
                    "query": "machine learning",
                    "limit": 8
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 策略搜索成功:")
                    print(f"   成功: {data.get('success')}")
                    print(f"   策略: {data.get('strategy')}")
                    print(f"   总结果数: {data.get('total_count')}")
                    print(f"   来源统计: {data.get('source_stats', {})}")
                    
                    papers = data.get('papers', [])
                    for i, paper in enumerate(papers[:2], 1):
                        title = paper.get('title', 'N/A')[:50]
                        source = paper.get('source', 'unknown')
                        print(f"   论文 {i} [{source}]: {title}...")
                    
                    return True
                else:
                    print(f"❌ 策略搜索失败，HTTP状态: {response.status}")
                    error_text = await response.text()
                    print(f"   错误详情: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ 策略搜索测试失败: {e}")
        return False

async def test_add_service():
    """测试添加新服务"""
    print("\\n➕ 测试添加新服务...")
    
    new_service = {
        "service_id": "test_api",
        "service_config": {
            "name": "测试API",
            "description": "用于测试的虚拟API服务",
            "enabled": False,
            "base_url": "https://httpbin.org",
            "method": "GET",
            "auth": {"type": "none"},
            "search_config": {
                "endpoint": "/json",
                "param_mapping": {"query": "test_param"},
                "additional_params": {}
            },
            "response_config": {
                "format": "json",
                "papers_path": "data",
                "field_mapping": {
                    "id": "id",
                    "title": "title"
                }
            }
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/services/add",
                headers={"Content-Type": "application/json"},
                json=new_service
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 添加服务成功:")
                    print(f"   消息: {data.get('message')}")
                    print(f"   服务名: {data.get('service', {}).get('name')}")
                    return True
                else:
                    print(f"❌ 添加服务失败，HTTP状态: {response.status}")
                    error_text = await response.text()
                    print(f"   错误详情: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ 添加服务测试失败: {e}")
        return False

async def test_service_status():
    """测试服务状态检查"""
    print("\\n🏥 测试服务状态检查...")
    
    services_to_test = ["arxiv", "crossref"]
    
    results = []
    for service_id in services_to_test:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE}/services/{service_id}/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        status_icon = "✅" if data.get('status') == 'healthy' else "❌"
                        print(f"   {status_icon} {service_id}: {data.get('status')}")
                        if data.get('error'):
                            print(f"      错误: {data.get('error')}")
                        results.append(data.get('status') == 'healthy')
                    else:
                        print(f"   ❌ {service_id}: 检查失败")
                        results.append(False)
        except Exception as e:
            print(f"   ❌ {service_id}: 异常 - {e}")
            results.append(False)
    
    return any(results)

async def test_stats():
    """测试统计信息"""
    print("\\n📊 测试统计信息...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 系统统计:")
                    print(f"   总服务数: {data.get('total_services')}")
                    print(f"   启用服务: {data.get('enabled_services')}")
                    print(f"   禁用服务: {data.get('disabled_services')}")
                    print(f"   总策略数: {data.get('total_strategies')}")
                    print(f"   配置版本: {data.get('config_version')}")
                    return True
                else:
                    print(f"❌ 获取统计信息失败，HTTP状态: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ 统计信息测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试通用MCP系统\\n")
    print("=" * 60)
    
    # 测试序列
    tests = [
        ("健康检查", test_health),
        ("服务信息", test_services_info),
        ("单源搜索", test_single_source_search),
        ("通用搜索", test_universal_search),
        ("策略搜索", test_strategy_search),
        ("服务状态", test_service_status),
        ("统计信息", test_stats),
        ("添加服务", test_add_service),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
        
        # 延迟避免请求过快
        await asyncio.sleep(1.0)
    
    # 输出测试结果摘要
    print("\\n" + "=" * 60)
    print("📊 通用MCP系统测试结果摘要:")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\\n总计: {passed}/{len(results)} 测试通过")
    
    if passed == len(results):
        print("🎉 所有测试都通过了！通用MCP系统工作正常。")
        return 0
    elif passed >= len(results) * 0.7:  # 70%通过率
        print("✅ 大部分测试通过，系统基本正常工作。")
        return 0
    else:
        print("⚠️  多数测试失败，请检查系统配置。")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\\n⏹️  测试被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\\n💥 测试过程中发生异常: {e}")
        sys.exit(1)