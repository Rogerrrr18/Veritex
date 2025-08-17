#!/usr/bin/env python3
"""
测试修复后的auto-search模式关键词扩展功能
"""

import asyncio
import json
import aiohttp
import time

async def test_auto_search_workflow():
    """测试auto-search模式的完整工作流"""
    print("🚀 测试修复后的auto-search模式\n")
    
    # 测试查询
    test_queries = [
        "光热甲烷干重整催化剂研究进展",
        "深度学习在医学图像分析中的应用",
        "机器学习算法优化"
    ]
    
    base_url = "http://127.0.0.1:8000"
    
    async with aiohttp.ClientSession() as session:
        for i, query in enumerate(test_queries, 1):
            print(f"📋 测试查询 {i}: {query}")
            
            # 构建请求数据
            request_data = {
                "message": query,
                "mode": "auto-search",  # 明确指定auto-search模式
                "max_results": 5
            }
            
            try:
                start_time = time.time()
                
                # 发送请求
                async with session.post(
                    f"{base_url}/chat",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        elapsed_time = time.time() - start_time
                        
                        print(f"✅ 请求成功 (耗时: {elapsed_time:.2f}s)")
                        
                        # 检查关键字段
                        analysis_result = result.get("analysis_result", {})
                        search_results = result.get("search_results", [])
                        search_keywords = result.get("search_keywords", [])
                        
                        print(f"📊 结果统计:")
                        print(f"   - 关键词扩展: {'✅ 成功' if analysis_result else '❌ 失败'}")
                        print(f"   - 搜索结果: {len(search_results)} 篇论文")
                        print(f"   - 搜索关键词: {len(search_keywords)} 个")
                        
                        # 检查关键词扩展质量
                        if analysis_result:
                            hierarchical = analysis_result.get("hierarchical_keywords", {})
                            exact_terms = hierarchical.get("exact_terms", {}).get("terms", [])
                            core_synonyms = hierarchical.get("core_synonyms", {}).get("terms", [])
                            related_terms = hierarchical.get("related_terms", {}).get("terms", [])
                            
                            total_keywords = len(exact_terms) + len(core_synonyms) + len(related_terms)
                            print(f"   - 关键词层次:")
                            print(f"     * 精确术语: {len(exact_terms)} 个")
                            print(f"     * 核心同义词: {len(core_synonyms)} 个") 
                            print(f"     * 相关术语: {len(related_terms)} 个")
                            print(f"     * 总计: {total_keywords} 个")
                            
                            # 检查是否使用了literature_search_prompt.txt的结构
                            expected_keys = ["original_query", "translated_query", "core_concepts", "domain"]
                            missing_keys = [key for key in expected_keys if key not in analysis_result]
                            if missing_keys:
                                print(f"⚠️ 缺少预期字段: {missing_keys}")
                            else:
                                print("✅ 关键词扩展结构完整")
                        
                        # 显示前2篇论文
                        if search_results:
                            print(f"📚 前2篇论文:")
                            for j, paper in enumerate(search_results[:2], 1):
                                title = paper.get("title", "无标题")[:60]
                                source = paper.get("source", "未知")
                                print(f"   {j}. {title}... (来源: {source})")
                        
                    else:
                        print(f"❌ 请求失败，状态码: {response.status}")
                        error_text = await response.text()
                        print(f"   错误信息: {error_text[:200]}")
                        
            except Exception as e:
                print(f"❌ 请求异常: {e}")
            
            print("-" * 80)
            
            # 短暂延迟避免过于频繁的请求
            if i < len(test_queries):
                await asyncio.sleep(2)
    
    print("\n🎯 测试完成!")

async def test_keyword_expansion_only():
    """单独测试关键词扩展（不执行搜索）"""
    print("\n🔬 测试关键词扩展功能（chat&plan模式）")
    
    query = "深度学习在自然语言处理中的应用"
    
    request_data = {
        "message": query,
        "mode": "chat&plan"  # 只做关键词扩展，不搜索
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "http://127.0.0.1:8000/chat",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    analysis_result = result.get("analysis_result", {})
                    
                    if analysis_result:
                        print("✅ 关键词扩展成功")
                        print(f"📋 原始查询: {analysis_result.get('original_query', '')}")
                        print(f"🌍 翻译查询: {analysis_result.get('translated_query', '')}")
                        print(f"🏷️ 学科领域: {analysis_result.get('domain', '')}")
                        
                        # 显示分层关键词
                        hierarchical = analysis_result.get("hierarchical_keywords", {})
                        for level, data in hierarchical.items():
                            terms = data.get("terms", [])
                            weight = data.get("weight", 0)
                            print(f"📌 {level} (权重{weight}): {terms}")
                    else:
                        print("❌ 关键词扩展失败")
                        
                else:
                    print(f"❌ 请求失败，状态码: {response.status}")
                    
        except Exception as e:
            print(f"❌ 请求异常: {e}")

async def main():
    """主测试函数"""
    print("🧪 开始测试修复后的auto-search模式功能")
    print("="*80)
    
    # 测试1: 完整的auto-search工作流
    await test_auto_search_workflow()
    
    # 测试2: 单独的关键词扩展
    await test_keyword_expansion_only()
    
    print("\n🎉 所有测试完成!")

if __name__ == "__main__":
    asyncio.run(main())