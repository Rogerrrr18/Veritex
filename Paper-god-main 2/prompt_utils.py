"""
简单的Prompt工具函数
替代复杂的prompt_manager，仅提供基本的文件读取和格式化功能
"""
import os
from typing import Dict, Any

# Prompt文件目录
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

def load_prompt_template(filename: str) -> str:
    """加载prompt模板文件"""
    file_path = os.path.join(PROMPT_DIR, filename)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"⚠️ Prompt文件未找到: {file_path}")
        return f"系统提示文件缺失，请分析用户查询：{{user_query}}"
    except Exception as e:
        print(f"❌ 加载prompt文件失败: {e}")
        return f"请分析用户查询：{{user_query}}"

def format_prompt(template: str, **kwargs) -> str:
    """格式化prompt模板"""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        print(f"⚠️ Prompt格式化缺少参数: {e}")
        # 为缺少的参数提供默认值
        if 'mode' not in kwargs:
            kwargs['mode'] = 'auto-search'
        if 'user_query' not in kwargs:
            kwargs['user_query'] = '未提供查询内容'
        return template.format(**kwargs)

def get_chat_conversation_prompt(user_query: str, **kwargs) -> str:
    """获取闲聊对话prompt"""
    template = load_prompt_template("chat_conversation_prompt.txt")
    return format_prompt(template, user_query=user_query, **kwargs)

def get_literature_search_prompt(user_query: str, **kwargs) -> str:
    """获取文献搜索prompt - 统一使用双语模板"""
    template = load_prompt_template("literature_search_prompt.txt")
    return format_prompt(template, user_query=user_query, **kwargs)


def get_academic_discussion_prompt(user_query: str, **kwargs) -> str:
    """获取学术探讨prompt - 统一使用双语模板"""
    template = load_prompt_template("academic_discussion_prompt.txt")
    return format_prompt(template, user_query=user_query, **kwargs)

def get_multi_turn_conversation_prompt(user_query: str, **kwargs) -> str:
    """获取多轮对话prompt"""
    template = load_prompt_template("multi_turn_conversation_prompt.txt")
    return format_prompt(template, user_query=user_query, **kwargs)

def get_prompt_by_intent(intent: str, user_query: str, **kwargs) -> str:
    """根据意图获取对应的prompt"""
    intent_mapping = {
        "闲聊": get_chat_conversation_prompt,
        "chat_conversation": get_chat_conversation_prompt,
        "查文献": get_literature_search_prompt,
        "literature_search": get_literature_search_prompt,
        "学术探讨": get_academic_discussion_prompt,
        "academic_discussion": get_academic_discussion_prompt
    }
    
    prompt_func = intent_mapping.get(intent, get_chat_conversation_prompt)
    return prompt_func(user_query, **kwargs)

if __name__ == "__main__":
    # 测试prompt工具函数
    print("🔍 测试简化的prompt工具函数...")
    
    test_query = "机器学习在医疗诊断中的应用"
    
    # 测试三种意图的prompt
    intents = ["闲聊", "查文献", "学术探讨"]
    
    for intent in intents:
        print(f"\n📝 意图: {intent}")
        prompt = get_prompt_by_intent(intent, test_query, mode="auto-search")
        print(f"📏 Prompt长度: {len(prompt)}字符")
        print(f"🎯 Prompt预览: {prompt[:100]}...")
    
    print("\n✅ 测试完成")