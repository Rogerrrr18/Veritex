#!/usr/bin/env python3
"""
超时优化测试脚本
验证前端和后端的超时设置是否正确生效
"""
import requests
import time
import json

def test_frontend_timeout():
    """测试前端超时配置"""
    print("🔍 测试前端超时配置...")
    
    # 读取前端配置
    try:
        with open('frontend/src/config.ts', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'REQUEST_TIMEOUT: 120000' in content:
                print("✅ 前端超时已设置为120秒（2分钟）")
                return True
            else:
                print("❌ 前端超时配置未正确设置")
                return False
    except Exception as e:
        print(f"❌ 读取前端配置失败: {e}")
        return False

def test_backend_timeout():
    """测试后端超时配置"""
    print("🔍 测试后端响应能力...")
    
    try:
        # 测试简单查询
        start_time = time.time()
        response = requests.post(
            'http://localhost:8000/search_papers',
            json={'query': '甲烷干重整', 'max_results': 5},
            timeout=30  # 本地测试用30秒超时
        )
        duration = time.time() - start_time
        
        print(f"✅ 搜索请求完成，用时: {duration:.2f}秒")
        
        if response.status_code == 200:
            result = response.json()
            paper_count = len(result.get('papers', []))
            print(f"✅ 搜索成功，找到 {paper_count} 篇论文")
            return True
        else:
            print(f"❌ 搜索失败，状态码: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时（30秒内未响应）")
        return False
    except Exception as e:
        print(f"❌ 搜索请求失败: {e}")
        return False

def test_model_config():
    """测试模型配置"""
    print("🔍 测试模型超时配置...")
    
    try:
        # 导入并检查配置
        import sys
        sys.path.append('.')
        from model_config import get_active_model_config
        
        config = get_active_model_config()
        print(f"✅ 当前模型超时设置: {config.timeout}秒")
        print(f"✅ 当前模型Token限制: {config.max_tokens}")
        
        if config.timeout >= 60:
            print("✅ 模型超时配置合理（≥60秒）")
            return True
        else:
            print("⚠️ 模型超时可能过短，建议≥60秒")
            return False
            
    except Exception as e:
        print(f"❌ 检查模型配置失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始超时优化验证测试...\n")
    
    results = {}
    
    # 测试各个组件
    results['frontend'] = test_frontend_timeout()
    print()
    
    results['backend'] = test_backend_timeout()
    print()
    
    results['model'] = test_model_config()
    print()
    
    # 总结结果
    print("📊 测试结果总结:")
    for component, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  - {component.title()}: {status}")
    
    all_passed = all(results.values())
    print(f"\n🎯 总体结果: {'✅ 所有测试通过' if all_passed else '❌ 部分测试失败'}")
    
    if all_passed:
        print("🎉 超时优化成功！现在可以处理更长的请求了。")
    else:
        print("⚠️ 请检查失败的配置项")

if __name__ == "__main__":
    main()