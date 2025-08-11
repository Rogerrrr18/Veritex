#!/usr/bin/env python3
"""
快速搜索测试 - 临时禁用有问题的数据源
"""

import os
import asyncio
import sys

# 临时禁用有问题的数据源
os.environ["GOOGLE_SCHOLAR_ENABLED"] = "false"
os.environ["CROSSREF_ENABLED"] = "false"

sys.path.append('/Users/rogeryang/Desktop/Paper-god-beta2')

async def quick_search_test():
    """快速搜索测试 - 只使用稳定的数据源"""
    try:
        print("🚀 快速搜索测试 - 只使用稳定数据源")
        print("-" * 50)
        
        from multi_source_engine import MultiSourceEngine
        engine = MultiSourceEngine(enable_mcp=False)
        print("✅ 搜索引擎实例化成功")
        
        # 设置较短的超时
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError('搜索超时')
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10秒超时
        
        try:
            print("🔍 开始搜索: 光热甲烷干重整")
            papers = await engine.search_parallel("solar thermal methane dry reforming", 5)
            print(f"📚 搜索完成，找到 {len(papers)} 篇论文")
            
            # 显示前3篇论文
            for i, paper in enumerate(papers[:3], 1):
                title = getattr(paper, 'title', '无标题')
                source = getattr(paper, 'source', '未知')
                print(f"{i}. {title[:60]}... (来源: {source})")
                
            return True
            
        except TimeoutError:
            print("⏰ 搜索超时 - 网络连接可能有问题")
            return False
        finally:
            signal.alarm(0)
            await engine.close()
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_workflow_integration():
    """测试工作流集成"""
    try:
        print("\n🤖 测试智能工作流集成")
        print("-" * 50)
        
        from langchain_workflows.paper_search_workflow import chat_with_search_strategy
        
        # 使用较短超时
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError('工作流超时')
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(15)  # 15秒超时
        
        try:
            result = await chat_with_search_strategy("光热甲烷干重整")
            
            print(f"✅ 工作流完成: success={result.get('success')}")
            print(f"🎯 是否学术查询: {result.get('is_academic_query')}")
            
            if result.get('search_results'):
                print(f"📚 找到论文: {len(result['search_results'])} 篇")
                # 显示第一篇论文标题
                if result['search_results']:
                    first_paper = result['search_results'][0]
                    title = first_paper.get('title', '无标题')
                    print(f"   示例: {title[:60]}...")
            else:
                print("📚 未找到论文")
                
            if result.get('error_message'):
                print(f"❌ 错误: {result['error_message']}")
                
            response = result.get('response', '')
            if response:
                print(f"💬 回复预览: {response[:200]}...")
                
            return result.get('success', False)
            
        except TimeoutError:
            print("⏰ 工作流超时")
            return False
        finally:
            signal.alarm(0)
            
    except Exception as e:
        print(f"❌ 工作流测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Paper God 快速搜索功能测试")
    print("=" * 60)
    
    # 测试1: 直接搜索引擎
    search_success = asyncio.run(quick_search_test())
    
    # 测试2: 工作流集成
    workflow_success = asyncio.run(test_workflow_integration())
    
    print("\n" + "=" * 60)
    print("📊 测试结果总结:")
    print(f"   直接搜索引擎: {'✅ 成功' if search_success else '❌ 失败'}")
    print(f"   智能工作流: {'✅ 成功' if workflow_success else '❌ 失败'}")
    
    if search_success and workflow_success:
        print("🎉 搜索功能已修复！")
    else:
        print("⚠️  部分功能仍有问题，需要进一步调试")