"""
Paper God - 学术文献智能搜索系统
重构版本：集成MCP (Model Context Protocol) 多源搜索能力
保留核心的Groq关键词扩展功能
"""

from scholarly import scholarly
import pandas as pd
import time
import random
import os
import asyncio
from groq import Groq
from typing import List, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import sys

# ================ 配置 ================
DEFAULT_MAX_RESULTS = 50  # 提高默认搜索数量
REQUEST_DELAY = (0.5, 1.5)  # 降低延迟以提高效率

load_dotenv()

# 检查 .env 文件是否存在
if not os.path.exists(".env"):
    print("警告: .env 文件不存在，请创建 .env 文件并配置以下变量：")
    print("- GROQ_API_KEY: 你的 Groq API 密钥")
    print("- GROQ_MODEL: 模型名称 (如 mixtral-8x7b-32768)")
    print("- SUPABASE_URL: 你的 Supabase URL")
    print("- SUPABASE_KEY: 你的 Supabase 密钥")
    print("- SUPABASE_TABLE: 数据表名 (默认 papers)")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("请在.env文件或环境变量中配置GROQ_API_KEY")

GROQ_MODEL = os.getenv("GROQ_MODEL")
if not GROQ_MODEL:
    print("警告: 未配置 GROQ_MODEL，使用默认模型 mixtral-8x7b-32768")
    GROQ_MODEL = "mixtral-8x7b-32768"

print(f"当前配置 - 模型: {GROQ_MODEL}, API密钥: {'已配置' if GROQ_API_KEY else '未配置'}")
print(f"当前 Python 路径: {sys.executable}")

class GroqKeywordExpander:
    """
    Groq关键词扩展器 - Paper God的核心组件
    支持中英文关键词的智能扩展
    """
    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("Groq API密钥未配置")
        self.client = Groq(api_key=GROQ_API_KEY)

    def _is_chinese(self, text: str) -> bool:
        """检测文本是否包含中文字符"""
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    
    def _validate_term(self, term: str) -> bool:
        """验证术语是否有效"""
        if not term or len(term) < 2:
            return False
        
        # 确保是英文术语
        if self._is_chinese(term):
            return False
            
        # 限制词组长度（1-5个词）
        words = term.split()
        if len(words) > 5:
            return False
            
        # 过滤掉包含提示词或描述性词汇的术语
        term_lower = term.lower()
        invalid_patterns = [
            'based on', 'i\'ve generated', 'following', 'synonyms', 
            'related terms', 'similar concepts', 'the keyword', 'keywords',
            'requirements', 'format', 'steps', 'analysis', 'identification'
        ]
        
        for pattern in invalid_patterns:
            if pattern in term_lower:
                return False
                
        # 过滤掉以引号开头的术语
        if term.startswith('"') or term.startswith("'"):
            return False
            
        # 基本验证：术语应该有意义
        return len(term.strip()) >= 2

    async def expand_keywords(self, keywords: str, max_terms: int = 5) -> List[str]:
        """智能关键词扩展：中文转英文，英文高质量专业术语扩展"""
        try:
            # 检测是否为中文关键词
            is_chinese_input = self._is_chinese(keywords)
            
            if is_chinese_input:
                # 中文关键词：翻译为英文同义词
                prompt = f"""
你是专业的学术翻译专家。请将以下中文关键词转换为{max_terms-1}个最相关的英文同义词：

中文关键词: {keywords}

要求：
1. 提供与原词意思最接近的英文同义词
2. 包括直接同义词和相关概念
3. 优先选择学术文献中常用的表达
4. 仅返回英文词汇，用逗号分隔，不要包含任何解释或说明
5. 格式：term1, term2, term3

英文同义词："""
            else:
                # 英文关键词：专业领域识别 + 术语简写扩展
                prompt = f"""
你是专业的学术术语扩展专家。请为以下关键词生成{max_terms-1}个相关术语：

关键词: {keywords}

要求：
1. 识别该关键词的专业领域（计算机科学、生物学、医学、化学、物理学等）
2. 如果是简写/缩写，提供完整术语
3. 如果是完整术语，提供相关简写
4. 提供同领域的重要相关概念
5. 仅返回英文术语，用逗号分隔
6. 格式：term1, term2, term3

专业术语扩展："""

            print(f"关键词扩展 - 原词: {keywords} ({'中文' if is_chinese_input else '英文'})")
            
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # 适中的随机性
                max_tokens=80     # 限制token数量
            )

            raw_terms = response.choices[0].message.content
            if not raw_terms:
                return [keywords] if not is_chinese_input else []

            # 清洗和验证结果
            terms = []
            for term in raw_terms.split(","):
                clean_term = term.strip().strip('"').strip("'").strip()
                if self._validate_term(clean_term):
                    terms.append(clean_term)

            # 对于英文输入，保留原词；对于中文输入，不包含原词
            if not is_chinese_input and keywords not in terms:
                terms.insert(0, keywords)

            # 限制返回数量
            result = terms[:max_terms]
            print(f"  扩展结果: {result}")
            return result

        except Exception as e:
            print(f"关键词扩展失败 - 原词: {keywords}, 错误: {str(e)}")
            return [keywords] if not self._is_chinese(keywords) else []


class SimpleLiteratureCollector:
    """
    简化版文献收集器 - 作为MCP搜索的后备方案
    仅保留核心的scholarly搜索功能
    """
    def __init__(self):
        self.results = []
        self.seen_urls = set()
    
    async def collect_fallback(self, query: str, max_results: int = 20, 
                              year_low: Optional[int] = None, 
                              year_high: Optional[int] = None) -> List[Dict]:
        """后备搜索方法 - 当MCP不可用时使用"""
        print(f"\n📚 使用后备搜索: {query}")
        self.results = []
        self.seen_urls = set()
        
        try:
            search_results_iterator = scholarly.search_pubs(
                query, year_low=year_low, year_high=year_high
            )
            
            retrieved_count = 0
            for i in range(max_results * 2):  # 搜索更多以过滤无效结果
                try:
                    result = next(search_results_iterator)
                    retrieved_count += 1
                    
                    if not result:
                        continue
                        
                    bib = result.get('bib', {})
                    title = bib.get('title', '')
                    if not title:
                        continue
                        
                    url = result.get('pub_url', '')
                    if not url or url in self.seen_urls:
                        continue
                    
                    paper_data = {
                        "title": title,
                        "authors": "; ".join(bib.get('author', [])),
                        "year": str(bib.get('pub_year', '')),
                        "abstract": (bib.get('abstract', '')[:300] + "...") if bib.get('abstract') else '',
                        "url": url
                    }
                    
                    self.results.append(paper_data)
                    self.seen_urls.add(url)
                    
                    print(f"  📄 添加: '{title[:50]}...'. 当前: {len(self.results)}/{max_results}")
                    
                    if len(self.results) >= max_results:
                        break
                        
                    await asyncio.sleep(random.uniform(*REQUEST_DELAY))
                    
                except StopIteration:
                    print("搜索完成 - 无更多结果")
                    break
                except Exception as e:
                    print(f"处理单条结果错误: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"搜索失败: {str(e)}")
        
        print(f"🏁 后备搜索完成，获得 {len(self.results)} 篇论文")
        return self.results


# ================ 简化的命令行工具 ================

async def simple_search_workflow(query: str, max_results: int = 20):
    """简化的搜索工作流 - 用于测试和演示"""
    print("\n=== Paper God 简化搜索演示 ===")
    print(f"查询: {query}")
    print(f"最大结果数: {max_results}")
    
    try:
        # 1. 关键词扩展
        if GROQ_API_KEY:
            print("\n🔄 正在扩展关键词...")
            expander = GroqKeywordExpander()
            expanded_terms = await expander.expand_keywords(query, max_terms=5)
            print(f"🔍 扩展后的关键词: {', '.join(expanded_terms)}")
        else:
            print("⚠️ Groq API密钥未配置，跳过关键词扩展")
            expanded_terms = [query]
        
        # 2. 文献搜索
        print("\n📚 开始文献搜索...")
        collector = SimpleLiteratureCollector()
        results = await collector.collect_fallback(" ".join(expanded_terms), max_results)
        
        # 3. 输出结果
        print(f"\n📊 搜索完成！共找到 {len(results)} 篇论文")
        
        for i, paper in enumerate(results[:5], 1):  # 显示前5篇
            print(f"\n{i}. {paper['title']}")
            print(f"   作者: {paper['authors']}")
            print(f"   年份: {paper['year']}")
            if paper['abstract']:
                print(f"   摘要: {paper['abstract'][:100]}...")
        
        if len(results) > 5:
            print(f"\n... 还有 {len(results) - 5} 篇论文")
        
        return results
        
    except Exception as e:
        print(f"\n❌ 搜索失败: {str(e)}")
        return []


if __name__ == "__main__":
    # 简单的命令行测试界面
    import sys
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        max_results = 10
    else:
        query = input("请输入搜索关键词: ").strip()
        if not query:
            print("未输入关键词，退出")
            sys.exit(1)
        
        try:
            max_results = int(input(f"最大结果数 [{DEFAULT_MAX_RESULTS}]: ").strip() or DEFAULT_MAX_RESULTS)
        except ValueError:
            max_results = DEFAULT_MAX_RESULTS
    
    # 运行搜索
    asyncio.run(simple_search_workflow(query, max_results))