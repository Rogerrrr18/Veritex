#!/usr/bin/env python3
"""
测试聊天接口优化效果
包括闲聊回复质量、学术查询速度、Google Scholar功能等
"""
import asyncio
import aiohttp
import time
import json
from typing import Dict, List

class ChatAPITester:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.session = None
        
    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def chat_request(self, message: str, history: List = None) -> Dict:
        """发送聊天请求"""
        session = await self._get_session()
        
        payload = {
            "message": message,
            "history": history or [],
            "mode": "auto-search"
        }
        
        start_time = time.time()
        try:
            async with session.post(f"{self.base_url}/chat", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    elapsed = time.time() - start_time
                    result['_test_elapsed'] = elapsed
                    return result
                else:
                    print(f"❌ API错误: {response.status}")
                    return None
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None
    
    async def test_casual_chat(self):
        """测试闲聊优化效果"""
        print("📝 测试闲聊回复优化...")
        
        casual_queries = [
            "你好",
            "谢谢你的帮助",
            "今天天气怎么样？",
            "你是谁？",
            "这个系统怎么使用？"
        ]
        
        results = []
        for query in casual_queries:
            print(f"\n🔍 测试: {query}")
            start_time = time.time()
            
            result = await self.chat_request(query)
            if result:
                elapsed = result.get('_test_elapsed', 0)
                token_info = result.get('token_info', {})
                llm_calls = token_info.get('llm_calls', 0)
                is_fast_path = token_info.get('fast_path', False)
                
                print(f"   ⏱️  耗时: {elapsed:.3f}秒")
                print(f"   🤖 LLM调用: {llm_calls}次")
                print(f"   ⚡ 快速路径: {'是' if is_fast_path else '否'}")
                print(f"   💬 回复: {result.get('response', '')[:50]}...")
                
                results.append({
                    'query': query,
                    'elapsed': elapsed,
                    'llm_calls': llm_calls,
                    'fast_path': is_fast_path,
                    'response_length': len(result.get('response', ''))
                })
            else:
                print(f"   ❌ 请求失败")
        
        # 统计结果
        if results:
            avg_time = sum(r['elapsed'] for r in results) / len(results)
            fast_path_rate = sum(1 for r in results if r['fast_path']) / len(results)
            avg_llm_calls = sum(r['llm_calls'] for r in results) / len(results)
            
            print(f"\n📊 闲聊测试统计:")
            print(f"   平均响应时间: {avg_time:.3f}秒")
            print(f"   快速路径使用率: {fast_path_rate:.1%}")
            print(f"   平均LLM调用: {avg_llm_calls:.1f}次")
        
        return results
    
    async def test_academic_queries(self):
        """测试学术查询优化效果"""
        print("\n📚 测试学术查询优化...")
        
        academic_queries = [
            "机器学习在医疗诊断中的应用",
            "深度学习算法研究",
            "人工智能最新进展"
        ]
        
        results = []
        for query in academic_queries:
            print(f"\n🔍 测试: {query}")
            start_time = time.time()
            
            result = await self.chat_request(query)
            if result:
                elapsed = result.get('_test_elapsed', 0)
                token_info = result.get('token_info', {})
                search_results = result.get('search_results', [])
                is_academic = result.get('is_academic_query', False)
                
                print(f"   ⏱️  耗时: {elapsed:.3f}秒")
                print(f"   🎓 学术查询: {'是' if is_academic else '否'}")
                print(f"   📄 搜索结果: {len(search_results)}篇")
                print(f"   🤖 LLM调用: {token_info.get('llm_calls', 0)}次")
                
                results.append({
                    'query': query,
                    'elapsed': elapsed,
                    'is_academic': is_academic,
                    'result_count': len(search_results),
                    'llm_calls': token_info.get('llm_calls', 0)
                })
            else:
                print(f"   ❌ 请求失败")
        
        # 统计结果
        if results:
            avg_time = sum(r['elapsed'] for r in results) / len(results)
            academic_rate = sum(1 for r in results if r['is_academic']) / len(results)
            avg_results = sum(r['result_count'] for r in results) / len(results)
            
            print(f"\n📊 学术查询统计:")
            print(f"   平均响应时间: {avg_time:.3f}秒")
            print(f"   学术识别准确率: {academic_rate:.1%}")
            print(f"   平均搜索结果: {avg_results:.1f}篇")
        
        return results
    
    async def test_performance_api(self):
        """测试性能统计API"""
        print("\n📈 测试性能统计API...")
        
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/performance") as response:
                if response.status == 200:
                    perf_data = await response.json()
                    if perf_data.get('success'):
                        data = perf_data.get('data', {})
                        overall = data.get('overall', {})
                        
                        print(f"   总请求数: {overall.get('total_requests', 0)}")
                        print(f"   快速路径使用率: {overall.get('fast_path_rate', 0):.1%}")
                        print(f"   平均响应时间: {overall.get('avg_response_time', 0):.3f}秒")
                        print(f"   平均LLM调用: {overall.get('avg_llm_calls_per_request', 0):.1f}次")
                        
                        return data
                    else:
                        print(f"   ❌ API返回错误: {perf_data.get('error')}")
                else:
                    print(f"   ❌ HTTP错误: {response.status}")
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
        
        return None
    
    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()

async def main():
    """主测试函数"""
    print("🚀 开始聊天接口优化效果测试")
    print("=" * 60)
    
    tester = ChatAPITester()
    
    try:
        # 检查后端是否运行
        session = await tester._get_session()
        try:
            async with session.get(f"{tester.base_url}/health") as response:
                if response.status == 200:
                    print("✅ 后端服务正常运行")
                else:
                    print(f"❌ 后端服务状态异常: {response.status}")
                    return
        except:
            print("❌ 无法连接后端服务，请确保服务已启动")
            return
        
        # 测试1: 闲聊优化
        casual_results = await tester.test_casual_chat()
        
        # 测试2: 学术查询优化  
        academic_results = await tester.test_academic_queries()
        
        # 测试3: 性能统计API
        perf_data = await tester.test_performance_api()
        
        # 总结
        print("\n" + "=" * 60)
        print("📋 优化效果总结:")
        
        if casual_results:
            fast_chat_avg = sum(r['elapsed'] for r in casual_results if r['fast_path']) / max(1, sum(1 for r in casual_results if r['fast_path']))
            print(f"   🔥 闲聊平均响应时间: {fast_chat_avg:.3f}秒")
        
        if academic_results:
            academic_avg = sum(r['elapsed'] for r in academic_results) / len(academic_results)
            print(f"   📚 学术查询平均响应时间: {academic_avg:.3f}秒")
        
        if perf_data:
            overall = perf_data.get('overall', {})
            print(f"   ⚡ 整体快速路径使用率: {overall.get('fast_path_rate', 0):.1%}")
            print(f"   🤖 平均LLM调用次数: {overall.get('avg_llm_calls_per_request', 0):.1f}")
        
        # 评估优化效果
        if casual_results:
            fast_responses = [r for r in casual_results if r['elapsed'] < 5.0 and r['fast_path']]
            if len(fast_responses) >= len(casual_results) * 0.8:
                print("✅ 闲聊优化效果: 优秀")
            else:
                print("⚠️ 闲聊优化效果: 需要改进")
        
        if academic_results:
            reasonable_responses = [r for r in academic_results if r['elapsed'] < 30.0]
            if len(reasonable_responses) >= len(academic_results) * 0.8:
                print("✅ 学术查询优化效果: 良好")
            else:
                print("⚠️ 学术查询优化效果: 需要改进")
        
        print("\n🎉 优化测试完成!")
        
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main())