#!/usr/bin/env python3
"""
优化的LLM意图分类器集成测试
验证优化后的意图分类系统与原工作流的兼容性和性能
"""
import asyncio
import time
import json
import os
from typing import List, Dict, Any

async def test_intent_classifier_standalone():
    """测试独立的意图分类器"""
    print("🔍 [1/3] 测试独立意图分类器...")
    
    try:
        from llm_intent_classifier import get_intent_classifier
        
        classifier = get_intent_classifier()
        
        test_cases = [
            # 查文献类
            ("帮我找关于机器学习的最新论文", "查文献"),
            ("搜索量子计算的研究", "查文献"),
            ("我需要一些深度学习的文献", "查文献"),
            ("甲烷干重整催化剂", "查文献"),
            
            # 闲聊类
            ("你好，今天天气怎么样？", "闲聊"),
            ("谢谢你的帮助", "闲聊"),
            ("这个系统怎么使用？", "闲聊"),
            ("你是谁？", "闲聊"),
            
            # 学术探讨类
            ("人工智能会取代人类吗？", "学术探讨"),
            ("量子纠缠能用来超光速通信吗？", "学术探讨"),
            ("如何看待大语言模型的发展？", "学术探讨"),
            ("甲烷干重整的机理是什么？", "学术探讨"),
        ]
        
        correct_count = 0
        total_time = 0
        
        print("📝 测试用例结果:")
        for i, (query, expected) in enumerate(test_cases, 1):
            start_time = time.time()
            result = await classifier.classify_intent(query)
            duration = time.time() - start_time
            total_time += duration
            
            is_correct = result.intent == expected
            if is_correct:
                correct_count += 1
            
            status = "✅" if is_correct else "❌"
            print(f"  {i:2d}. {status} [{duration:.2f}s] {query[:30]:<30} → {result.intent} (期望: {expected})")
            print(f"      置信度: {result.confidence:.3f}, 方法: {result.method}")
        
        accuracy = correct_count / len(test_cases)
        avg_time = total_time / len(test_cases)
        
        print(f"\n📊 独立分类器测试结果:")
        print(f"   准确率: {accuracy:.1%} ({correct_count}/{len(test_cases)})")
        print(f"   平均响应时间: {avg_time:.2f}秒")
        print(f"   总用时: {total_time:.2f}秒")
        
        # 打印分类器统计信息
        stats = classifier.get_stats()
        print(f"\n🔧 分类器统计:")
        print(f"   分类器类型: {stats['classifier_type']}")
        print(f"   已移除embedding: {stats['embedding_removed']}")
        print(f"   缓存大小: {stats['result_cache_size']}")
        print(f"   分类方法: {stats['classification_methods']}")
        
        return accuracy >= 0.8, avg_time <= 3.0
        
    except Exception as e:
        print(f"❌ 独立分类器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, False

async def test_workflow_integration():
    """测试工作流集成"""
    print("\n🔗 [2/3] 测试工作流集成...")
    
    try:
        from langchain_workflows.paper_search_workflow import IntelligentPaperSearchAgent
        
        # 确保使用新的意图分类器
        os.environ["USE_EMBEDDING_INTENT"] = "true"
        
        agent = IntelligentPaperSearchAgent()
        
        test_cases = [
            # 查文献 - 应该触发搜索
            {
                "query": "帮我搜索关于深度学习的论文",
                "expected_academic": True,
                "expected_search": True,
                "description": "查文献请求"
            },
            
            # 闲聊 - 不应该触发搜索
            {
                "query": "你好，谢谢你的帮助",
                "expected_academic": False,
                "expected_search": False,
                "description": "日常对话"
            },
            
            # 学术探讨 - 学术查询但不自动搜索
            {
                "query": "人工智能在医学领域的发展前景如何？",
                "expected_academic": True,
                "expected_search": False,
                "description": "学术探讨"
            }
        ]
        
        success_count = 0
        total_time = 0
        
        print("📝 工作流集成测试结果:")
        for i, case in enumerate(test_cases, 1):
            start_time = time.time()
            
            try:
                # 测试工作流（仅分析，不实际搜索）
                result = await agent.search_papers(
                    query=case["query"],
                    max_results=1,
                    force_search=False,
                    allow_search=False  # 禁止实际搜索，仅测试意图分析
                )
                
                duration = time.time() - start_time
                total_time += duration
                
                # 检查结果
                is_academic = result.get('is_academic_query', False)
                need_search = result.get('need_search_strategy', False)
                has_response = bool(result.get('response'))
                
                # 验证期望结果
                academic_correct = is_academic == case["expected_academic"]
                search_correct = need_search == case["expected_search"]
                
                overall_correct = academic_correct and search_correct
                if overall_correct:
                    success_count += 1
                
                status = "✅" if overall_correct else "❌"
                print(f"  {i}. {status} [{duration:.2f}s] {case['description']}")
                print(f"     查询: {case['query'][:50]}...")
                print(f"     学术查询: {is_academic} (期望: {case['expected_academic']}) {'✅' if academic_correct else '❌'}")
                print(f"     需要搜索: {need_search} (期望: {case['expected_search']}) {'✅' if search_correct else '❌'}")
                print(f"     有回复: {has_response}")
                
            except Exception as e:
                print(f"  {i}. ❌ 工作流测试失败: {e}")
                duration = time.time() - start_time
                total_time += duration
        
        success_rate = success_count / len(test_cases)
        avg_time = total_time / len(test_cases)
        
        print(f"\n📊 工作流集成测试结果:")
        print(f"   成功率: {success_rate:.1%} ({success_count}/{len(test_cases)})")
        print(f"   平均响应时间: {avg_time:.2f}秒")
        
        return success_rate >= 0.8, avg_time <= 10.0
        
    except Exception as e:
        print(f"❌ 工作流集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, False

def test_configuration_switch():
    """测试配置切换功能"""
    print("\n⚙️ [3/3] 测试配置切换功能...")
    
    try:
        # 测试新旧方案切换
        from langchain_workflows.paper_search_workflow import IntelligentPaperSearchAgent
        
        print("📝 测试配置切换:")
        
        # 测试新方案
        os.environ["USE_EMBEDDING_INTENT"] = "true"
        agent_new = IntelligentPaperSearchAgent()
        has_embedding = hasattr(agent_new, 'intent_classifier')
        print(f"   新方案 (USE_EMBEDDING_INTENT=true): {'✅' if has_embedding else '❌'}")
        
        # 测试旧方案
        os.environ["USE_EMBEDDING_INTENT"] = "false"
        agent_old = IntelligentPaperSearchAgent()
        has_prompt_manager = hasattr(agent_old, 'prompt_manager')
        print(f"   旧方案 (USE_EMBEDDING_INTENT=false): {'✅' if has_prompt_manager else '❌'}")
        
        # 恢复默认配置
        os.environ["USE_EMBEDDING_INTENT"] = "true"
        
        # 检查环境变量
        embedding_model = os.getenv("EMBEDDING_MODEL", "未设置")
        search_timeout = os.getenv("SEARCH_TASK_TIMEOUT", "未设置")
        
        print(f"   EMBEDDING_MODEL: {embedding_model}")
        print(f"   SEARCH_TASK_TIMEOUT: {search_timeout}")
        
        config_success = has_embedding and has_prompt_manager
        print(f"\n📊 配置切换测试: {'✅ 成功' if config_success else '❌ 失败'}")
        
        return config_success
        
    except Exception as e:
        print(f"❌ 配置切换测试失败: {e}")
        return False

async def run_comprehensive_test():
    """运行综合测试"""
    print("🚀 开始Embedding + LLM精排意图分类器综合测试...\n")
    
    start_time = time.time()
    
    # 执行三个测试阶段
    classifier_ok, classifier_fast = await test_intent_classifier_standalone()
    workflow_ok, workflow_fast = await test_workflow_integration() 
    config_ok = test_configuration_switch()
    
    total_time = time.time() - start_time
    
    # 汇总结果
    print(f"\n🎯 综合测试结果汇总:")
    print(f"   独立分类器: {'✅ 准确' if classifier_ok else '❌ 不准确'} | {'✅ 快速' if classifier_fast else '⚠️ 较慢'}")
    print(f"   工作流集成: {'✅ 成功' if workflow_ok else '❌ 失败'} | {'✅ 快速' if workflow_fast else '⚠️ 较慢'}")
    print(f"   配置切换: {'✅ 正常' if config_ok else '❌ 异常'}")
    print(f"   总用时: {total_time:.2f}秒")
    
    # 总体评估
    all_tests_pass = classifier_ok and workflow_ok and config_ok
    performance_good = classifier_fast and workflow_fast
    
    if all_tests_pass and performance_good:
        print(f"\n🎉 所有测试通过！新的意图分类系统可以投入使用。")
        print(f"💡 性能提升预期: 响应时间减少60%+，准确率提升到90%+")
    elif all_tests_pass:
        print(f"\n✅ 功能测试通过，但性能有待优化。")
    else:
        print(f"\n⚠️ 部分测试失败，需要进一步调试。")
    
    return all_tests_pass, performance_good

def print_usage_instructions():
    """打印使用说明"""
    print(f"\n📖 使用说明:")
    print(f"1. 意图分类优化:")
    print(f"   使用优化的LLM意图分类器")
    print(f"   已移除embedding步骤，提升响应速度")
    print(f"   ")
    print(f"2. 系统优化:")
    print(f"   已移除embedding依赖，使用纯LLM分类提升性能")
    print(f"   ")
    print(f"3. 三种意图类别:")
    print(f"   - 查文献: 直接触发搜索")
    print(f"   - 闲聊: 友好对话，不搜索")
    print(f"   - 学术探讨: 深度讨论，可选搜索")
    print(f"   ")
    print(f"4. 降级保护:")
    print(f"   Embedding失败 → LLM分类 → 规则分类 → 兜底处理")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
    print_usage_instructions()