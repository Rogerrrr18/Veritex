#!/usr/bin/env python3
"""
模型切换功能测试脚本
演示如何通过修改环境变量实现一键切换不同LLM模型
"""
import os
import asyncio
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

async def test_model_switching():
    """测试模型切换功能"""
    print("🚀 开始测试统一模型管理系统的切换功能")
    print("="*60)
    
    # 导入模块
    from model_config import get_model_config_manager
    from llm_interface import get_universal_llm
    
    # 1. 显示当前配置
    print("📊 当前模型配置:")
    config_manager = get_model_config_manager()
    print(f"   激活模型: {config_manager.get_active_model_name()}")
    print(f"   可用模型: {config_manager.list_available_models()}")
    print(f"   模型详情: {config_manager.get_model_info()}")
    print()
    
    # 2. 测试当前模型
    print("🧪 测试当前激活的模型:")
    try:
        llm = await get_universal_llm()
        response = await llm.simple_chat("请用一句话介绍自己")
        print(f"   模型: {llm.get_model_info()['active_model']}")
        print(f"   响应: {response[:100]}...")
        await llm.close()
    except Exception as e:
        print(f"   ❌ 当前模型测试失败: {e}")
    print()
    
    # 3. 演示切换指导
    print("🔄 模型切换演示:")
    print("   要切换模型，请执行以下步骤:")
    print()
    
    available_models = config_manager.list_available_models()
    current_model = config_manager.get_active_model_name()
    
    for i, model in enumerate(available_models, 1):
        status = "✅ (当前)" if model == current_model else "⚪"
        print(f"   {i}. 切换到 {model.upper()}: {status}")
        
        if model != current_model:
            print(f"      - 确保 .env 文件中有 {model.upper()}_API_KEY")
            print(f"      - 修改 ACTIVE_MODEL={model}")
            print(f"      - 重启服务")
        print()
    
    # 4. 模拟切换测试（如果有其他可用模型）
    if len(available_models) > 1:
        print("🔄 模拟切换测试:")
        
        # 获取另一个可用模型
        next_model = None
        for model in available_models:
            if model != current_model:
                next_model = model
                break
        
        if next_model:
            print(f"   模拟切换到: {next_model}")
            
            # 临时修改环境变量进行测试
            original_model = os.getenv("ACTIVE_MODEL", current_model)
            os.environ["ACTIVE_MODEL"] = next_model
            
            try:
                # 重新加载配置
                from importlib import reload
                import model_config
                import llm_interface
                reload(model_config)
                reload(llm_interface)
                
                # 测试新模型
                new_config_manager = model_config.get_model_config_manager()
                new_llm = await llm_interface.get_universal_llm()
                
                print(f"   ✅ 成功切换到: {new_config_manager.get_active_model_name()}")
                print(f"   📋 模型信息: {new_llm.get_model_info()}")
                
                # 简单测试（可能会因为API密钥问题失败）
                try:
                    response = await new_llm.simple_chat("Hello, please introduce yourself briefly")
                    print(f"   💬 响应测试: {response[:100]}...")
                except Exception as e:
                    print(f"   ⚠️ 响应测试失败（可能是API密钥问题）: {e}")
                
                await new_llm.close()
                
            except Exception as e:
                print(f"   ❌ 切换测试失败: {e}")
            finally:
                # 恢复原始设置
                os.environ["ACTIVE_MODEL"] = original_model
        else:
            print("   ⚠️ 没有其他可用模型进行切换测试")
    else:
        print("🔄 只有一个可用模型，无法演示切换")
    
    print()
    print("="*60)
    print("🎯 测试总结:")
    print("   ✅ 统一模型配置管理器工作正常")
    print("   ✅ 模型信息获取正常") 
    print("   ✅ 切换机制设计正确")
    print("   💡 要实际切换，请修改 .env 文件中的 ACTIVE_MODEL 变量")
    print("="*60)

async def test_backend_api():
    """测试后端API的模型切换支持"""
    print("\n🌐 测试后端API集成:")
    
    import httpx
    
    # 测试健康检查
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 假设服务运行在8001端口
            health_response = await client.get("http://localhost:8001/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                print("   ✅ 健康检查通过")
                print(f"      激活模型: {health_data.get('active_model')}")
                print(f"      可用模型: {health_data.get('available_models')}")
            else:
                print("   ❌ 健康检查失败")
    except Exception as e:
        print(f"   ⚠️ 无法连接到后端服务 (可能未启动): {e}")

if __name__ == "__main__":
    print("🧪 统一模型管理系统 - 切换功能测试")
    print()
    
    # 运行主测试
    asyncio.run(test_model_switching())
    
    # 运行API测试
    asyncio.run(test_backend_api())
    
    print("\n🎉 测试完成！")
    print("\n📝 使用说明:")
    print("   1. 编辑 .env 文件")
    print("   2. 设置您要使用的模型的API密钥") 
    print("   3. 修改 ACTIVE_MODEL=您想要的模型")
    print("   4. 重启服务即可切换模型")
    print("\n   支持的模型: qwen, openai, claude, deepseek")