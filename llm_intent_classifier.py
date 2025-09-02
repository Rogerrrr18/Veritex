"""
优化的LLM意图分类器
去除embedding步骤，直接使用LLM + 规则降级的两阶段方案
提升响应速度，简化系统架构
"""
import os
import json
import asyncio
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from functools import lru_cache

import llm_interface

@dataclass
class IntentResult:
    """意图识别结果"""
    intent: str  # "查文献", "闲聊", "学术探讨"
    confidence: float  # 置信度 0-1
    method: str  # "llm", "rule"
    response: Optional[str] = None  # LLM生成的回复（如适用）
    reasoning: Optional[str] = None  # 分类原因

class LLMIntentClassifier:
    """优化的LLM意图分类器 - 高效两阶段分类"""
    
    def __init__(self):
        # 配置参数
        self.cache_size = 1000
        
        # 缓存
        self.result_cache = {}
        
        # LLM接口
        self.llm = None
        
        # 初始化消息已通过工作流日志显示
        
    async def _llm_classify(self, query: str) -> IntentResult:
        """LLM智能分类"""
        try:
            if not self.llm:
                self.llm = await llm_interface.get_universal_llm()
            
            # 构建优化的分类prompt
            prompt = self._build_classification_prompt(query)
            
            # 调用LLM
            response = await self.llm.simple_chat(prompt)
            return self._parse_llm_response(response, query)
            
        except Exception as e:
            print(f"LLM分类失败: {e}")
            # 降级到规则分类
            return self._rule_classify(query)
    
    def _build_classification_prompt(self, query: str) -> str:
        """构建优化的LLM分类prompt"""
        prompt = f"""你是一个专业的意图分类专家。请准确判断用户查询的意图类别。

三个意图类别定义：

1. **查文献**：用户明确要求搜索、查找、检索学术论文或文献
   - 特征：包含"找"、"搜索"、"检索"、"查找"、"文献"、"论文"、"paper"、"研究"等词
   - 示例：
     * "帮我找关于量子计算的最新论文"
     * "搜索机器学习算法文献" 
     * "我想查询关于智能体开发相关的研究"
     * "甲烷干重整催化剂研究"

2. **闲聊**：日常对话、问候、感谢、系统使用咨询等非学术内容
   - 特征：情感表达、礼貌用语、系统操作问题
   - 示例：
     * "你好，谢谢你的帮助"
     * "这个系统怎么使用？"
     * "今天天气真好啊"

3. **学术探讨**：对学术问题的讨论、提问、观点交流，但不要求搜索文献
   - 特征：以疑问句形式探讨学术概念、理论、现象，不包含搜索意图
   - 示例：
     * "量子纠缠能不能用来超光速通信？"
     * "人工智能会取代人类吗？"
     * "甲烷干重整的机理是什么？"

⚠️ 重要判断标准：
- 如果查询中包含明确的搜索意图词汇（找、搜索、检索、查询、研究等），优先归类为"查文献"
- 只有当查询是纯粹的学术讨论或疑问，且没有搜索意图时，才归类为"学术探讨"
- "研究"相关的查询通常是要搜索文献的需求

用户查询："{query}"

请按以下JSON格式回复：
```json
{{
  "intent": "查文献|闲聊|学术探讨",
  "confidence": 0.95,
  "reasoning": "详细的分类原因说明"
}}
```"""
        
        return prompt
    
    def _parse_llm_response(self, response: str, query: str) -> IntentResult:
        """解析LLM分类响应"""
        try:
            # 提取JSON
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group(1))
                
                return IntentResult(
                    intent=result_data.get("intent", "闲聊"),
                    confidence=result_data.get("confidence", 0.8),
                    method="llm",
                    reasoning=result_data.get("reasoning", "LLM智能分类"),
                    response=response if result_data.get("intent") == "闲聊" else None
                )
            else:
                print("LLM响应格式解析失败，使用规则降级方案")
                return self._rule_classify(query)
                
        except Exception as e:
            print(f"LLM响应解析失败: {e}")
            return self._rule_classify(query)
    
    def _rule_classify(self, query: str) -> IntentResult:
        """规则降级分类方案（优化版本）"""
        query_lower = query.lower()
        query_clean = query.strip()
        
        # 强搜索关键词（明确的搜索意图）
        strong_search_keywords = [
            # 直接搜索词汇
            "找", "搜索", "检索", "查找", "查询", "寻找", "搜", "查",
            # 英文搜索词汇
            "find", "search", "lookup", "retrieve",
            # 中文文献词汇
            "文献", "论文", "paper", "文章", "资料", "材料",
            # 明确搜索句式
            "帮我找", "请检索", "我想找", "我要找", "需要一些",
            "查一下", "搜一下", "找一下", "获取"
        ]
        
        # 弱搜索关键词（可能是搜索意图，但也可能是讨论意图）
        weak_search_keywords = [
            "了解", "看看", "我需要", "学习", "研究", "探索", "掌握",
            "知道", "明白", "理解", "认识", "熟悉", "接触", "涉及",
            "深入", "更多", "详细", "具体", "全面", "系统性"
        ]
        
        # 学术术语（当与其他线索结合时有助于分类）
        academic_terms = [
            # 基础科学技术词汇
            "催化剂", "算法", "技术", "方法", "模型", "系统", "理论", "框架", "架构",
            "协议", "标准", "规范", "原理", "机制", "机理", "工艺", "流程", "过程",
            
            # AI/ML核心术语
            "机器学习", "深度学习", "人工智能", "AI", "ML", "DL", "神经网络", "智能体",
            "自然语言处理", "NLP", "计算机视觉", "CV", "数据挖掘", "大数据", "数据科学",
            "强化学习", "监督学习", "无监督学习", "迁移学习", "联邦学习", "元学习",
            
            # 具体模型和技术
            "BERT", "GPT", "Transformer", "CNN", "RNN", "LSTM", "GAN", "VAE",
            "ResNet", "YOLO", "SVM", "决策树", "随机森林", "梯度提升", "聚类",
            "回归", "分类", "预测", "优化", "特征工程", "特征选择", "降维",
            
            # 量子和前沿技术
            "量子计算", "量子机器学习", "量子算法", "区块链", "边缘计算", "云计算",
            "物联网", "5G", "6G", "AR", "VR", "元宇宙", "数字孪生",
            
            # 化学化工术语
            "催化", "重整", "费托合成", "甲烷", "氢能", "碳捕获", "材料科学",
            "纳米材料", "聚合物", "分子", "离子", "电子", "反应", "合成",
            "分离", "提纯", "结晶", "蒸馏", "萃取", "吸附", "膜分离",
            
            # 生物医学术语
            "生物技术", "基因工程", "蛋白质", "酶", "细胞", "分子生物学",
            "生物信息学", "药物发现", "临床试验", "精准医学", "免疫", "疫苗",
            
            # 物理和材料科学
            "量子物理", "凝聚态物理", "光学", "激光", "超导", "半导体",
            "纳米科技", "石墨烯", "碳纳米管", "新能源", "太阳能", "电池",
            
            # 工程和应用领域
            "软件工程", "系统工程", "控制工程", "信号处理", "通信", "网络",
            "安全", "加密", "隐私保护", "分布式系统", "微服务", "容器化",
            
            # 数学和统计
            "数学建模", "统计分析", "概率论", "线性代数", "微积分", "优化理论",
            "图论", "拓扑", "几何", "数值分析", "随机过程", "时间序列",
            
            # 跨学科和新兴领域
            "复杂系统", "网络科学", "计算社会学", "数字人文", "科学计算",
            "仿真", "建模", "可视化", "交互设计", "用户体验", "人机交互"
        ]
        
        # 闲聊关键词（扩展版本）
        chat_keywords = [
            # 问候语
            "你好", "hello", "hi", "嗨", "哈喽", "早上好", "下午好", "晚上好", "晚安",
            # 感谢语
            "谢谢", "感谢", "thanks", "thank you", "多谢",
            # 告别语
            "再见", "拜拜", "bye", "goodbye", "88",
            # 系统使用
            "怎么用", "怎么使用", "如何使用", "使用方法", "操作指南", "帮助",
            "功能", "界面", "系统", "你是谁", "你能做什么", "什么功能", "介绍一下",
            # 日常话题
            "天气", "心情", "今天", "明天", "周末", "假期", "电影", "音乐",
            "吃饭", "睡觉", "工作", "累", "忙", "无聊", "开心", "难过",
            # 常见口语表达
            "哦", "嗯", "是的", "好的", "ok", "好吧", "算了", "没事",
            "恶化", "糟糕"  # 针对用户的具体例子
        ]
        
        # 系统使用相关的特殊模式
        system_usage_patterns = [
            "系统怎么", "怎么使用", "如何使用", "使用方法", 
            "操作指南", "功能介绍", "怎么用"
        ]
        
        # 学术探讨特征词汇
        question_words = [
            # 基础疑问词
            "什么", "如何", "为什么", "怎样", "哪些", "哪个", "谁", "何时", "何处",
            "能否", "是否", "会不会", "能不能", "可以吗", "行吗", "对吗",
            "是不是", "会", "能", "可能", "应该", "需要",
            
            # 英文疑问词
            "what", "how", "why", "when", "where", "who", "which",
            "can", "will", "could", "would", "should", "may", "might",
            
            # 观点询问词
            "看待", "认为", "觉得", "评价", "观点", "意见", "建议",
            "看法", "态度", "立场", "观念", "理解", "见解", "想法",
            
            # 比较和选择词
            "比较", "对比", "区别", "差异", "相似", "不同", "选择",
            "更好", "更优", "最佳", "推荐", "建议用", "适合"
        ]
        
        academic_concepts = [
            # 核心学术概念
            "机理", "原理", "理论", "概念", "假设", "定理", "定律", "公式",
            "现象", "规律", "模式", "范式", "框架", "体系", "结构",
            
            # 问题和挑战
            "问题", "挑战", "难题", "瓶颈", "困难", "障碍", "限制", "约束",
            "矛盾", "冲突", "争议", "分歧", "悖论", "缺陷", "不足",
            
            # 发展和趋势
            "发展", "演进", "进展", "进步", "趋势", "方向", "前景", "未来",
            "潜力", "可能性", "机会", "空间", "余地", "成长性",
            
            # 创新和突破
            "创新", "突破", "改进", "优化", "提升", "革新", "变革", "转型",
            "升级", "迭代", "演化", "进化", "革命性", "颠覆性",
            
            # 应用和实践
            "应用", "实践", "实施", "部署", "落地", "商业化", "产业化",
            "场景", "用例", "案例", "实例", "经验", "教训",
            
            # 影响和意义
            "影响", "作用", "效果", "效应", "后果", "结果", "意义", "价值",
            "重要性", "必要性", "关键性", "核心", "本质", "实质",
            
            # 特性和属性
            "特点", "特性", "特征", "属性", "性质", "品质", "性能", "指标",
            "参数", "变量", "因素", "要素", "条件", "环境",
            
            # 比较和评价
            "优势", "劣势", "优点", "缺点", "优缺点", "利弊", "pros and cons",
            "强项", "弱点", "亮点", "痛点", "短板", "瓶颈",
            
            # 方法和策略
            "方法", "方式", "途径", "策略", "方案", "措施", "手段", "技巧",
            "技术路线", "实现路径", "解决方案", "应对策略", "改进措施",
            
            # 机制和过程
            "机制", "过程", "流程", "步骤", "阶段", "环节", "程序", "工序",
            "动态", "变化", "转换", "转化", "反应", "响应", "反馈",
            
            # 标准和规范
            "标准", "规范", "准则", "原则", "guidelines", "best practices",
            "基准", "指标体系", "评价体系", "度量标准"
        ]
        
        # 学术探讨的典型句式
        discussion_patterns = [
            # 探索性询问
            "想知道", "想了解", "想学习", "想研究", "想探索", "想掌握",
            "希望了解", "需要了解", "可以介绍", "能否解释",
            
            # 深度询问
            "深入了解", "详细了解", "全面了解", "系统了解", "更多了解",
            "进一步了解", "具体了解", "深度学习", "系统学习",
            
            # 原理机制询问
            "原理是什么", "机制是什么", "工作原理", "运行机制", "作用机理",
            "实现原理", "基本原理", "核心机制", "底层机制",
            
            # 特征属性询问
            "有什么特点", "有什么优势", "有什么特征", "有什么属性",
            "具有哪些", "包含哪些", "涉及哪些", "体现在",
            
            # 评价性询问
            "如何看待", "如何评价", "如何理解", "如何认识", "如何分析",
            "怎样理解", "怎样看", "怎样认为", "观点是",
            
            # 比较性询问
            "区别是什么", "差异在哪", "相比之下", "对比", "比较",
            "哪个更好", "哪种更", "优势在于", "不同之处",
            
            # 应用性询问
            "应用场景", "使用场合", "适用于", "可以用于", "如何应用",
            "实际应用", "具体应用", "应用前景", "发展前景",
            
            # 发展性询问
            "发展趋势", "未来发展", "技术发展", "演进过程", "发展历程",
            "最新进展", "研究现状", "技术现状", "当前状态"
        ]
        
        # 计算匹配得分
        strong_search_score = sum(1 for kw in strong_search_keywords if kw in query_lower)
        weak_search_score = sum(1 for kw in weak_search_keywords if kw in query_lower)
        chat_score = sum(1 for kw in chat_keywords if kw in query_lower)
        
        # 特殊模式检测
        has_system_usage = any(pattern in query_lower for pattern in system_usage_patterns)
        
        # 学术探讨检测
        has_question = any(qw in query_lower for qw in question_words)
        has_academic_concept = any(ac in query_lower for ac in academic_concepts)
        has_discussion_pattern = any(dp in query_lower for dp in discussion_patterns)
        is_question_form = query_clean.endswith('？') or query_clean.endswith('?')
        
        # 学术术语检测（扩展版）
        has_academic_term = any(term in query_lower for term in academic_terms + [
            "机器学习", "深度学习", "人工智能", "量子", "神经网络", "算法",
            "催化", "重整", "材料", "化学", "物理", "生物", "医学", "智能体",
            "费托", "合成", "反应", "分子", "离子", "电子"
        ])
        
        # 明确的搜索意图检测
        explicit_search_intent = strong_search_score > 0
        
        # 混合意图检测（新增）
        has_mixed_intent = any(pattern in query_lower for pattern in [
            "帮我找", "能帮我找", "可以帮我找", "帮忙找", "找些", "找一些"
        ])
        
        # 研究学习相关的语境判断（扩展版）
        research_learning_indicators = [
            "研究", "学习", "探索", "探讨", "分析", "调研", "调查",
            "study", "research", "explore", "investigate", "analyze"
        ]
        has_research_context = any(indicator in query_lower for indicator in research_learning_indicators)
        
        # 深度学术探讨的组合判断
        is_research_discussion = has_research_context and (
            has_question or has_discussion_pattern or has_academic_concept
        )
        
        # 新增："了解+学术术语"的特殊识别
        has_academic_learning_intent = (
            ("了解" in query_lower or "学习" in query_lower or "探索" in query_lower) and 
            has_academic_term and 
            not explicit_search_intent
        )
        
        # 分类逻辑（重新优化，解决所有识别问题）
        
        # 最高优先级：系统使用咨询
        if has_system_usage:
            return IntentResult(
                intent="闲聊",
                confidence=0.95,
                method="rule",
                reasoning="系统使用咨询，属于非学术对话"
            )
        
        # 高优先级：混合意图（先探讨后明确要求搜索）
        elif has_mixed_intent or (weak_search_score > 0 and strong_search_score > 0):
            return IntentResult(
                intent="查文献",
                confidence=0.9,
                method="rule",
                reasoning="检测到混合意图，但最终倾向于搜索文献"
            )
        
        # 中高优先级：明确搜索意图
        elif strong_search_score >= 2 or explicit_search_intent:
            return IntentResult(
                intent="查文献",
                confidence=min(0.85 + strong_search_score * 0.05, 0.95),
                method="rule",
                reasoning=f"明确搜索意图，匹配{strong_search_score}个强搜索关键词"
            )
        elif has_academic_term and explicit_search_intent:
            return IntentResult(
                intent="查文献",
                confidence=0.85,
                method="rule",
                reasoning="包含学术术语且有明确搜索意图"
            )
        
        # 高优先级：学术探讨
        elif has_academic_learning_intent:
            return IntentResult(
                intent="学术探讨",
                confidence=0.9,
                method="rule",
                reasoning="检测到'了解/学习/探索+学术术语'模式，倾向学术探讨"
            )
        elif has_discussion_pattern or (is_research_discussion and not explicit_search_intent):
            return IntentResult(
                intent="学术探讨",
                confidence=0.9,
                method="rule",
                reasoning="明确的学术探讨句式，无明确搜索意图"
            )
        elif (has_question or is_question_form) and (has_academic_concept or has_academic_term) and not explicit_search_intent and not has_system_usage:
            return IntentResult(
                intent="学术探讨",
                confidence=0.85,
                method="rule", 
                reasoning="学术疑问形式，无明确搜索意图"
            )
        
        # 低优先级：闲聊
        elif chat_score > 0:
            base_confidence = 0.85 if chat_score >= 2 else 0.8
            return IntentResult(
                intent="闲聊", 
                confidence=min(base_confidence + chat_score * 0.05, 0.95),
                method="rule",
                reasoning=f"日常对话，匹配{chat_score}个对话关键词"
            )
        elif has_academic_term and not explicit_search_intent:
            return IntentResult(
                intent="学术探讨",
                confidence=0.75,
                method="rule",
                reasoning="包含学术概念但无明确搜索意图"
            )
        elif weak_search_score > 0 and has_academic_term:
            return IntentResult(
                intent="学术探讨",
                confidence=0.8,  # 提升置信度
                method="rule",
                reasoning="弱搜索意图结合学术术语，倾向于学术探讨"
            )
        else:
            return IntentResult(
                intent="闲聊",
                confidence=0.6,
                method="rule",
                reasoning="未明确匹配，默认对话模式"
            )
    
    async def classify_intent(self, query: str) -> IntentResult:
        """优化的分类接口：规则优先 + LLM降级，大幅减少LLM调用"""
            # 开始意图分析（简化日志）
        
        # 检查结果缓存
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.result_cache:
            cached_result = self.result_cache[cache_key]
            print(f"命中缓存: {cached_result.intent} ({cached_result.confidence:.3f})")
            return cached_result
        
        # 🚀 优化策略：规则分类优先，仅模糊情况使用LLM
        rule_result = self._rule_classify(query)
        
        # 如果规则分类置信度高（>=0.8），直接返回，避免LLM调用
        if rule_result.confidence >= 0.8:
            print(f"规则分类高置信度命中: {rule_result.intent} ({rule_result.confidence:.3f})")
            
            # 缓存规则结果
            if len(self.result_cache) >= self.cache_size:
                keys_to_remove = list(self.result_cache.keys())[:self.cache_size//2]
                for key in keys_to_remove:
                    del self.result_cache[key]
            self.result_cache[cache_key] = rule_result
            
            return rule_result
        
        # 仅对低置信度情况使用LLM进行精确分类
        print(f"规则分类置信度较低({rule_result.confidence:.3f})，使用LLM精确分类")
        llm_result = await self._llm_classify(query)
        
        # 选择更可信的结果
        if llm_result.confidence > rule_result.confidence:
            final_result = llm_result
        else:
            final_result = rule_result
            print("LLM分类置信度不高，保持规则分类结果")
        
        # 缓存最终结果
        if len(self.result_cache) >= self.cache_size:
            keys_to_remove = list(self.result_cache.keys())[:self.cache_size//2]
            for key in keys_to_remove:
                del self.result_cache[key]
        
        self.result_cache[cache_key] = final_result
        
        print(f"最终分类结果: {final_result.intent} (置信度: {final_result.confidence:.3f}, 方法: {final_result.method})")
        return final_result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取分类器统计信息"""
        return {
            "classifier_type": "llm_optimized",
            "embedding_removed": True,
            "result_cache_size": len(self.result_cache),
            "cache_size_limit": self.cache_size,
            "classification_methods": ["llm", "rule"]
        }

# 全局实例
_intent_classifier = None

def get_intent_classifier() -> LLMIntentClassifier:
    """获取全局意图分类器实例"""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = LLMIntentClassifier()
    return _intent_classifier

# 测试功能
async def test_intent_classifier():
    """测试优化的意图分类器"""
    print("测试优化的LLM意图分类器")
    
    classifier = get_intent_classifier()
    
    test_queries = [
        "我想查询关于智能体开发相关的研究",  # 应该是查文献
        "帮我找关于机器学习的最新论文",      # 应该是查文献
        "你好，今天天气怎么样？",           # 应该是闲聊
        "量子计算能解决什么问题？",         # 应该是学术探讨
        "甲烷干重整催化剂研究",             # 应该是查文献（研究意图）
        "谢谢你的帮助",                    # 应该是闲聊
        "人工智能会取代人类吗？",           # 应该是学术探讨
        "搜索深度学习算法",                # 应该是查文献
        "这个系统怎么使用？"               # 应该是闲聊
    ]
    
    for query in test_queries:
        result = await classifier.classify_intent(query)
        print(f"查询: {query}")
        print(f"   分类: {result.intent} (置信度: {result.confidence:.3f})")
        print(f"   方法: {result.method}, 原因: {result.reasoning}")
        print()
    
    # 打印统计信息
    stats = classifier.get_stats()
    print("分类器统计:", json.dumps(stats, indent=2, ensure_ascii=False))
    
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(test_intent_classifier())