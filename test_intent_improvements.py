#!/usr/bin/env python3
"""
意图分类改进效果测试
验证边缘案例和关键优化点的分类准确性
"""
import asyncio
import time
from typing import List, Tuple
from llm_intent_classifier import get_intent_classifier

def create_test_cases() -> List[Tuple[str, str, str]]:
    """创建测试用例集：(查询, 期望意图, 测试描述)"""
    return [
        # 核心问题案例 - 学术探讨被误分类为查文献
        (
            "我想了解关于Ni催化剂在费托合成中的研究，想知道为什么Ni金属更有优势？",
            "学术探讨",
            "核心问题：研究+疑问句式，应识别为学术探讨"
        ),
        (
            "我想了解机器学习的研究进展，为什么深度学习这么火？",
            "学术探讨", 
            "类似问题：了解研究+为什么，应识别为学术探讨"
        ),
        (
            "想知道为什么量子计算比传统计算有优势？",
            "学术探讨",
            "学术疑问：想知道为什么，明确的探讨意图"
        ),
        
        # 明确的查文献案例
        (
            "帮我找一些关于催化剂的最新论文",
            "查文献",
            "明确搜索：帮我找+论文"
        ),
        (
            "我需要搜索机器学习方面的文献资料",
            "查文献",
            "明确搜索：需要搜索+文献"
        ),
        (
            "请检索深度学习的相关研究",
            "查文献",
            "明确搜索：请检索+研究"
        ),
        
        # 学术探讨案例
        (
            "深度学习的原理是什么？",
            "学术探讨",
            "学术疑问：原理是什么"
        ),
        (
            "如何看待人工智能的发展前景？",
            "学术探讨",
            "学术讨论：如何看待"
        ),
        (
            "量子纠缠的机制是什么？",
            "学术探讨",
            "学术疑问：机制是什么"
        ),
        (
            "催化剂有什么优势和特点？",
            "学术探讨",
            "学术疑问：有什么优势"
        ),
        
        # 闲聊案例
        (
            "你好，今天天气怎么样？",
            "闲聊",
            "日常对话：问候+天气"
        ),
        (
            "谢谢你的帮助",
            "闲聊",
            "日常对话：感谢"
        ),
        (
            "这个系统怎么使用？",
            "闲聊",
            "系统使用咨询"
        ),
        
        # 边缘案例
        (
            "了解一下人工智能",
            "学术探讨",
            "边缘案例：了解+学术术语，无明确搜索意图"
        ),
        (
            "我想了解机器学习算法的优缺点",
            "学术探讨",
            "边缘案例：想了解+优缺点，探讨性质"
        ),
        (
            "研究表明深度学习很有效，你怎么看？",
            "学术探讨",
            "边缘案例：研究+你怎么看，明确探讨"
        ),
        (
            "我需要了解量子计算的基本原理",
            "学术探讨",
            "边缘案例：需要了解+原理，倾向探讨"
        ),
        
        # 混合意图案例
        (
            "想了解催化剂研究，能帮我找些论文吗？",
            "查文献",
            "混合意图：先探讨后明确要求找论文"
        ),
        (
            "我对机器学习很感兴趣，想找相关资料",
            "查文献",
            "混合意图：兴趣+想找资料"
        )
    ]

async def test_classification_accuracy():
    """测试分类准确性"""
    print("🚀 开始意图分类改进效果测试\n")
    
    # 获取分类器
    classifier = get_intent_classifier()
    
    # 获取测试用例
    test_cases = create_test_cases()
    
    # 测试结果统计
    correct_count = 0
    total_count = len(test_cases)
    failed_cases = []
    
    print(f"📝 测试用例总数: {total_count}\n")
    print("=" * 80)
    
    for i, (query, expected_intent, description) in enumerate(test_cases, 1):
        print(f"\n🔍 测试 {i}/{total_count}: {description}")
        print(f"查询: {query}")
        print(f"期望: {expected_intent}")
        
        start_time = time.time()
        try:
            result = await classifier.classify_intent(query)
            elapsed = time.time() - start_time
            
            # 判断是否正确
            is_correct = result.intent == expected_intent
            if is_correct:
                correct_count += 1
                status = "✅"
            else:
                status = "❌"
                failed_cases.append((query, expected_intent, result.intent, description))
            
            print(f"结果: {result.intent} (置信度: {result.confidence:.3f})")
            print(f"方法: {result.method}")
            print(f"推理: {result.reasoning}")
            print(f"状态: {status} | 耗时: {elapsed:.3f}s")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            failed_cases.append((query, expected_intent, "ERROR", description))
        
        print("-" * 80)
    
    # 统计结果
    accuracy = correct_count / total_count
    print(f"\n📊 测试结果统计:")
    print(f"总测试数: {total_count}")
    print(f"正确数量: {correct_count}")
    print(f"错误数量: {len(failed_cases)}")
    print(f"准确率: {accuracy:.1%}")
    
    # 显示失败案例
    if failed_cases:
        print(f"\n❌ 失败案例详情:")
        for i, (query, expected, actual, desc) in enumerate(failed_cases, 1):
            print(f"{i}. {desc}")
            print(f"   查询: {query}")
            print(f"   期望: {expected} | 实际: {actual}")
    
    # 评估改进效果
    print(f"\n🎯 改进效果评估:")
    if accuracy >= 0.9:
        print("✅ 优秀 - 准确率达到90%以上")
    elif accuracy >= 0.8:
        print("🟨 良好 - 准确率达到80%以上，仍有提升空间")
    else:
        print("🔴 需要进一步优化 - 准确率低于80%")
    
    return accuracy, failed_cases

async def test_specific_improvements():
    """测试特定改进点"""
    print(f"\n🔧 测试特定改进点\n")
    
    classifier = get_intent_classifier()
    
    # 重点测试的改进案例
    improvement_cases = [
        (
            "我想了解关于Ni催化剂在费托合成中的研究，想知道为什么Ni金属更有优势？",
            "学术探讨",
            "核心改进：修复研究+疑问被误分类为查文献的问题"
        ),
        (
            "想知道为什么机器学习这么火？",
            "学术探讨", 
            "疑问句式识别：想知道为什么"
        ),
        (
            "了解一下深度学习的特点",
            "学术探讨",
            "弱搜索词处理：了解+学术特点"
        ),
        (
            "研究表明量子计算有巨大潜力，你觉得呢？",
            "学术探讨",
            "研究语境判断：研究+探讨句式"
        )
    ]
    
    print("重点测试改进效果:")
    print("=" * 60)
    
    improvement_success = 0
    for i, (query, expected, improvement_desc) in enumerate(improvement_cases, 1):
        print(f"\n🎯 改进点 {i}: {improvement_desc}")
        print(f"查询: {query}")
        
        result = await classifier.classify_intent(query)
        is_correct = result.intent == expected
        
        if is_correct:
            improvement_success += 1
            status = "✅ 改进成功"
        else:
            status = "❌ 仍需优化"
        
        print(f"期望: {expected}")
        print(f"结果: {result.intent} (置信度: {result.confidence:.3f})")
        print(f"推理: {result.reasoning}")
        print(f"状态: {status}")
    
    improvement_rate = improvement_success / len(improvement_cases)
    print(f"\n📈 改进成功率: {improvement_rate:.1%} ({improvement_success}/{len(improvement_cases)})")
    
    return improvement_rate

async def main():
    """主测试函数"""
    print("🔥 意图分类系统优化验证测试")
    print("=" * 80)
    
    start_time = time.time()
    
    # 测试1: 整体分类准确性
    accuracy, failed_cases = await test_classification_accuracy()
    
    # 测试2: 特定改进点
    improvement_rate = await test_specific_improvements()
    
    total_time = time.time() - start_time
    
    # 最终评估
    print(f"\n" + "=" * 80)
    print(f"🎉 测试总结:")
    print(f"总耗时: {total_time:.2f}秒")
    print(f"整体准确率: {accuracy:.1%}")
    print(f"改进成功率: {improvement_rate:.1%}")
    
    if accuracy >= 0.85 and improvement_rate >= 0.75:
        print("✅ 优化效果显著，可以部署到生产环境")
    elif accuracy >= 0.8:
        print("🟨 优化有一定效果，建议进一步调整")
    else:
        print("🔴 优化效果不理想，需要重新调整策略")
    
    print(f"\n🚀 测试完成！")

if __name__ == "__main__":
    asyncio.run(main())