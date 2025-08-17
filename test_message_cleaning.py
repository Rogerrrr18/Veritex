#!/usr/bin/env python3
"""
消息清洗功能测试
验证JSON剥离和中文用户友好展示效果
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(__file__))

from langchain_workflows.paper_search_workflow import IntelligentPaperSearchAgent

class MessageCleaningTester:
    def __init__(self):
        self.agent = IntelligentPaperSearchAgent()
    
    def test_json_stripping(self):
        """测试JSON剥离功能"""
        print("🧹 测试JSON剥离功能\n")
        
        # 测试用例：包含JSON的响应
        test_cases = [
            {
                "name": "学术讨论 - 完整JSON + 中文解释",
                "input": '''这是一个很有价值的学术问题。

```json
{
  "query_analysis": "analysis of catalysts",
  "core_concepts": ["催化剂", "费托合成", "镍金属"],
  "hierarchical_keywords": {
    "exact_terms": {"terms": ["Ni catalysts", "Fischer-Tropsch"], "weight": 1.0},
    "core_synonyms": {"terms": ["nickel catalysts", "F-T synthesis"], "weight": 0.9},
    "related_concepts": {"terms": ["heterogeneous catalysis", "synthesis gas"], "weight": 0.7}
  },
  "domain": "catalysis chemistry",
  "optimized_boolean_query": "Ni catalysts Fischer-Tropsch synthesis",
  "search_strategy": "precision_focused"
}
```

🎓 **专业解读**
镍催化剂在费托合成中具有独特的优势，主要体现在以下几个方面：

📊 **技术分析**
1. **活性选择性**: 镍具有良好的C-O键断裂能力
2. **成本效益**: 相比贵金属催化剂成本更低
3. **稳定性**: 在适当条件下表现出良好的稳定性

💡 **深入理解**
建议从分子层面理解镍的催化机理，这对于优化反应条件具有重要意义。''',
                "expected_contains": ["🎓", "专业解读", "技术分析", "深入理解"],
                "expected_not_contains": ['"query_analysis"', '"core_concepts"', '```json']
            },
            {
                "name": "普通对话 - 无JSON",
                "input": "你好！我是学术搜索助手，很高兴为您提供帮助。请问您有什么学术问题需要讨论吗？",
                "expected_contains": ["你好", "学术搜索助手", "帮助"],
                "expected_not_contains": ['"', '{', '}']
            },
            {
                "name": "混合内容 - JSON + 格式标记",
                "input": '''# 普通对话模式

```json
{"test": "data"}
```

这是一个测试回复，包含了一些```代码块```和其他格式。

🎓 **专业内容**
这里是学术讨论的核心内容。''',
                "expected_contains": ["🎓", "专业内容", "学术讨论"],
                "expected_not_contains": ["普通对话模式", "```json", "```代码块```", '"test"']
            }
        ]
        
        results = []
        for i, case in enumerate(test_cases, 1):
            print(f"📝 测试用例 {i}: {case['name']}")
            print(f"输入长度: {len(case['input'])} 字符")
            
            # 执行清洗
            cleaned = self.agent._final_clean_response(case['input'])
            
            print(f"输出长度: {len(cleaned)} 字符")
            print(f"清洗结果预览: {cleaned[:100]}...")
            
            # 验证结果
            success = True
            for expected in case['expected_contains']:
                if expected not in cleaned:
                    print(f"❌ 缺少期望内容: {expected}")
                    success = False
            
            for not_expected in case['expected_not_contains']:
                if not_expected in cleaned:
                    print(f"❌ 包含不期望内容: {not_expected}")
                    success = False
            
            if success:
                print("✅ 测试通过")
            else:
                print("❌ 测试失败")
            
            results.append({
                'name': case['name'],
                'success': success,
                'input_length': len(case['input']),
                'output_length': len(cleaned),
                'reduction_ratio': (len(case['input']) - len(cleaned)) / len(case['input'])
            })
            
            print("-" * 60)
        
        return results
    
    def test_chinese_readability(self):
        """测试中文可读性优化"""
        print("\n📖 测试中文可读性优化\n")
        
        test_cases = [
            {
                "name": "emoji间距优化",
                "input": "🎓专业解读📊现状分析🔍搜索策略💡学术指导",
                "expected": "🎓 专业解读📊 现状分析🔍 搜索策略💡 学术指导"
            },
            {
                "name": "段落分隔优化",
                "input": "第一段\n\n\n\n第二段\n\n\n\n\n第三段",
                "expected": "第一段\n\n第二段\n\n第三段"
            },
            {
                "name": "列表格式优化",
                "input": "内容如下：\n- 第一项\n* 第二项\n  - 第三项",
                "expected_contains": ["• 第一项", "• 第二项", "• 第三项"]
            }
        ]
        
        results = []
        for i, case in enumerate(test_cases, 1):
            print(f"📝 测试用例 {i}: {case['name']}")
            
            result = self.agent._enhance_chinese_readability(case['input'])
            print(f"输入: {case['input']}")
            print(f"输出: {result}")
            
            success = True
            if 'expected' in case:
                success = result == case['expected']
            elif 'expected_contains' in case:
                success = all(item in result for item in case['expected_contains'])
            
            print(f"结果: {'✅ 通过' if success else '❌ 失败'}")
            results.append({'name': case['name'], 'success': success})
            print("-" * 40)
        
        return results
    
    def test_quality_assurance(self):
        """测试质量保证功能"""
        print("\n🔍 测试质量保证功能\n")
        
        test_cases = [
            {
                "name": "内容过短 - 需要增强",
                "processed": "短",
                "original": "这是一个关于机器学习的学术讨论，包含了详细的分析内容。",
                "should_enhance": True
            },
            {
                "name": "内容充足 - 包含学术要素",
                "processed": "🎓 专业解读：这是一个很详细的学术分析，包含了深入的讨论内容和专业见解。",
                "original": "原始内容",
                "should_enhance": False
            },
            {
                "name": "内容一般 - 无学术标识",
                "processed": "这是一段普通的文本内容，没有特殊的学术标识符，但内容还算充实。",
                "original": "原始内容",
                "should_enhance": False
            }
        ]
        
        results = []
        for i, case in enumerate(test_cases, 1):
            print(f"📝 测试用例 {i}: {case['name']}")
            
            result = self.agent._ensure_response_quality(case['processed'], case['original'])
            
            enhanced = len(result) > len(case['processed']) + 10
            print(f"处理前: {len(case['processed'])} 字符")
            print(f"处理后: {len(result)} 字符")
            print(f"是否增强: {enhanced}")
            
            success = enhanced == case['should_enhance']
            print(f"结果: {'✅ 符合预期' if success else '❌ 不符合预期'}")
            
            results.append({'name': case['name'], 'success': success})
            print("-" * 40)
        
        return results
    
    async def test_end_to_end_academic_discussion(self):
        """端到端学术讨论测试"""
        print("\n🎓 端到端学术讨论测试\n")
        
        test_query = "我想了解关于Ni催化剂在费托合成中的研究，想知道为什么Ni金属更有优势？"
        
        try:
            print(f"📝 测试查询: {test_query}")
            
            # 执行完整的学术讨论流程
            result = await self.agent.search_papers(
                query=test_query,
                max_results=5,
                mode="chat&plan"
            )
            
            if result and 'response' in result:
                response = result['response']
                print(f"✅ 获得响应，长度: {len(response)} 字符")
                print(f"📝 响应预览: {response[:200]}...")
                
                # 检查是否成功剥离了JSON
                has_json = any(indicator in response for indicator in ['"query_analysis"', '"core_concepts"', '```json'])
                print(f"JSON剥离: {'❌ 仍包含JSON' if has_json else '✅ 已成功剥离'}")
                
                # 检查是否包含学术讨论要素
                has_academic_elements = any(element in response for element in ['🎓', '📊', '🔍', '💡'])
                print(f"学术要素: {'✅ 包含学术讨论要素' if has_academic_elements else '⚠️ 缺少学术要素'}")
                
                return {
                    'success': True,
                    'response_length': len(response),
                    'json_cleaned': not has_json,
                    'has_academic_elements': has_academic_elements
                }
            else:
                print("❌ 未获得有效响应")
                return {'success': False}
                
        except Exception as e:
            print(f"❌ 端到端测试失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始消息清洗功能全面测试")
        print("=" * 80)
        
        all_results = {}
        
        # 测试1：JSON剥离
        all_results['json_stripping'] = self.test_json_stripping()
        
        # 测试2：中文可读性
        all_results['chinese_readability'] = self.test_chinese_readability()
        
        # 测试3：质量保证
        all_results['quality_assurance'] = self.test_quality_assurance()
        
        return all_results

async def main():
    """主测试函数"""
    tester = MessageCleaningTester()
    
    # 运行基础测试
    basic_results = tester.run_all_tests()
    
    # 运行端到端测试
    print("\n" + "=" * 80)
    e2e_result = await tester.test_end_to_end_academic_discussion()
    
    # 生成测试报告
    print("\n" + "=" * 80)
    print("📊 测试结果汇总:")
    
    total_tests = 0
    passed_tests = 0
    
    for category, results in basic_results.items():
        category_passed = sum(1 for r in results if r['success'])
        category_total = len(results)
        total_tests += category_total
        passed_tests += category_passed
        
        print(f"  {category}: {category_passed}/{category_total} 通过")
    
    if e2e_result['success']:
        passed_tests += 1
    total_tests += 1
    print(f"  端到端测试: {'1/1 通过' if e2e_result['success'] else '0/1 失败'}")
    
    success_rate = passed_tests / total_tests
    print(f"\n整体通过率: {success_rate:.1%} ({passed_tests}/{total_tests})")
    
    if success_rate >= 0.8:
        print("✅ 消息清洗功能测试通过，可以部署使用")
    else:
        print("⚠️ 部分测试失败，需要进一步调试")
    
    print("\n🎉 测试完成！")

if __name__ == "__main__":
    asyncio.run(main())