#!/usr/bin/env python3
"""
Qwen API诊断脚本
用于排查API调用失败的问题
"""
import os
import asyncio
import httpx
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

async def test_qwen_api():
    """测试Qwen API调用"""
    print("🔍 开始诊断Qwen API调用问题...")
    print("="*50)
    
    # 1. 检查环境变量
    api_key = os.getenv("QWEN_API_KEY")
    base_url = os.getenv("QWEN_BASE_URL")
    model_name = os.getenv("QWEN_MODEL_NAME")
    
    print("📋 环境变量检查:")
    print(f"   QWEN_API_KEY: {'✅ 已设置' if api_key else '❌ 未设置'}")
    print(f"   QWEN_BASE_URL: {base_url}")
    print(f"   QWEN_MODEL_NAME: {model_name}")
    
    if not api_key:
        print("❌ API密钥未设置，请检查.env文件")
        return
    
    if api_key.startswith("sk-") and len(api_key) > 30:
        print("   API密钥格式: ✅ 看起来正确")
    else:
        print("   API密钥格式: ⚠️ 格式可能有问题")
    
    print()
    
    # 2. 测试API连通性
    print("🌐 测试API连通性:")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 测试消息
    messages = [
        {"role": "user", "content": "你好"}
    ]
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 100
    }
    
    print(f"   请求URL: {base_url}/chat/completions")
    print(f"   请求模型: {model_name}")
    print(f"   请求头: Authorization: Bearer {api_key[:10]}...")
    print()
    
    # 3. 发送API请求
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            print("📤 发送API请求...")
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            print(f"   HTTP状态码: {response.status_code}")
            print(f"   响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print("   ✅ API调用成功!")
                print(f"   响应内容: {json.dumps(result, ensure_ascii=False, indent=2)}")
            else:
                print(f"   ❌ API调用失败: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   错误详情: {json.dumps(error_data, ensure_ascii=False, indent=2)}")
                except:
                    print(f"   响应内容: {response.text}")
                
                # 具体错误分析
                if response.status_code == 400:
                    print("\n🔧 400错误通常由以下原因造成:")
                    print("   1. 模型名称错误 - 检查QWEN_MODEL_NAME")
                    print("   2. 请求参数格式错误")
                    print("   3. max_tokens值过大")
                    print("   4. 消息格式不正确")
                elif response.status_code == 401:
                    print("\n🔧 401错误通常由以下原因造成:")
                    print("   1. API密钥错误或已过期")
                    print("   2. API密钥格式不正确")
                elif response.status_code == 403:
                    print("\n🔧 403错误通常由以下原因造成:")
                    print("   1. API密钥没有访问权限")
                    print("   2. 账户余额不足")
                elif response.status_code == 429:
                    print("\n🔧 429错误通常由以下原因造成:")
                    print("   1. API调用频率过高")
                    print("   2. 账户配额已用完")
                    
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        print(f"   异常类型: {type(e)}")
    
    print()
    
    # 4. 测试常见的Qwen模型名称
    print("🎯 测试常见的Qwen模型名称:")
    common_models = [
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
        "qwen-long",
        "qwen1.5-72b-chat",
        "qwen1.5-14b-chat",
        "qwen1.5-7b-chat"
    ]
    
    for model in common_models:
        try:
            test_payload = {
                "model": model,
                "messages": [{"role": "user", "content": "测试"}],
                "max_tokens": 50
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=test_payload
                )
                
                if response.status_code == 200:
                    print(f"   ✅ {model} - 可用")
                elif response.status_code == 400:
                    error_data = response.json()
                    if "model" in str(error_data).lower():
                        print(f"   ❌ {model} - 模型不存在")
                    else:
                        print(f"   ⚠️ {model} - 其他400错误")
                else:
                    print(f"   ⚠️ {model} - HTTP {response.status_code}")
                    
        except Exception as e:
            print(f"   ❌ {model} - 测试异常: {e}")
            
    print()
    
    # 5. 建议修复方案
    print("💡 建议修复方案:")
    print("   1. 确认API密钥正确 - 登录阿里云控制台检查")
    print("   2. 尝试使用 'qwen-turbo' 作为模型名称")
    print("   3. 降低 max_tokens 到 1500 以下")  
    print("   4. 确认账户有足够余额")
    print("   5. 检查网络连接和防火墙设置")

async def test_current_adapter():
    """测试当前的适配器"""
    print("\n🔧 测试当前Qwen适配器:")
    try:
        from adapters.qwen_adapter import QwenAdapter
        from model_config import get_model_config_manager
        
        config_manager = get_model_config_manager()
        if not config_manager.is_model_available("qwen"):
            print("   ❌ Qwen配置不可用")
            return
            
        config = config_manager._configs["qwen"]
        
        async with QwenAdapter(config) as adapter:
            print("   ✅ 适配器创建成功")
            
            response = await adapter.simple_chat("你好")
            if response and "抱歉" not in response:
                print(f"   ✅ 适配器测试成功: {response[:50]}...")
            else:
                print(f"   ⚠️ 适配器返回错误: {response}")
                
    except Exception as e:
        print(f"   ❌ 适配器测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_qwen_api())
    asyncio.run(test_current_adapter())