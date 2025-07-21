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
# openpyxl import removed - no longer generating Excel reports
import sys

# ================ 配置 ================
DEFAULT_MAX_RESULTS = 200
DEFAULT_OUTPUT_FILE = "literature.csv"
REQUEST_DELAY = (1, 3)

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

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "papers")

# Excel generation removed - no longer creating test files
print("Current GROQ_MODEL:", os.getenv("GROQ_MODEL"))
print(f"当前 Python 路径: {sys.executable}")

class GroqKeywordExpander:
    def __init__(self):
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

    async def expand_keywords(self, keywords: str) -> List[str]:
        """智能关键词扩展：中文转英文，英文高质量专业术语扩展"""
        try:
            # 检测是否为中文关键词
            is_chinese_input = self._is_chinese(keywords)
            
            if is_chinese_input:
                # 中文关键词：翻译为英文同义词
                prompt = f"""
你是专业的学术翻译专家。请将以下中文关键词转换为2-3个最相关的英文同义词：

中文关键词: {keywords}

要求：
1. 提供与原词意思最接近的英文同义词
2. 包括直接同义词和相关概念
3. 优先选择学术文献中常用的表达
4. 仅返回英文词汇，用逗号分隔，不要包含任何解释或说明
5. 不要包含"related terms"、"synonyms"等描述性词汇
6. 格式：term1, term2, term3

英文同义词："""
            else:
                # 英文关键词：专业领域识别 + 术语简写扩展
                prompt = f"""
你是专业的学术术语扩展专家。请为以下关键词生成2-3个相关术语：

关键词: {keywords}

要求：
1. 识别该关键词的专业领域（计算机科学、生物学、医学、化学、物理学等）
2. 如果是简写/缩写，提供完整术语
3. 如果是完整术语，提供相关简写
4. 提供同领域的重要相关概念
5. 仅返回英文术语，用逗号分隔
6. 不要包含任何解释、说明或描述性词汇
7. 不要包含"Based on"、"I've generated"等短语
8. 格式：term1, term2, term3

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

            # 对于中文输入，不包含原词；对于英文输入，可以包含原词
            if not is_chinese_input and keywords not in terms:
                terms.insert(0, keywords)

            # 限制返回数量：最多3个术语
            result = terms[:3]
            print(f"  扩展结果: {result}")
            print(f"  验证详情: 原始返回 {len(raw_terms.split(','))} 个术语，验证通过 {len(result)} 个")
            return result

        except Exception as e:
            print(f"关键词扩展失败 - 原词: {keywords}, 错误: {str(e)}")
            return [keywords] if not self._is_chinese(keywords) else []


class QueryBuilder:
    def __init__(self, keywords: List[str]):
        # 清洗关键词：移除特殊字符，限制长度
        self.keywords = [
            term.replace('"', '').replace("'", "").strip()
            for term in keywords
            if 3 <= len(term.strip()) <= 50
        ]

    def build_query(self) -> str:
        """简化查询构建：只用OR连接所有关键词"""
        if not self.keywords:
            raise ValueError("无有效关键词")

        # 对包含空格的关键词加引号
        quoted_terms = [
            f'"{term}"' if ' ' in term else term
            for term in self.keywords
        ]

        return " OR ".join(quoted_terms)


class LiteratureCollector:
    def __init__(self):
        self.results = []
        self.seen_urls = set()
        self.supabase: Client = None
        if SUPABASE_URL and SUPABASE_KEY:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    async def collect(self, query: str, max_results: int, output_filename: Optional[str] = None, year_low: Optional[int] = None, year_high: Optional[int] = None):
        print(f"\n开始检索: {query}, 年份范围: {year_low}-{year_high}, 最大结果: {max_results}")
        self.results = [] # Ensure results are reset for each call
        self.seen_urls = set() # Ensure seen_urls are reset
        retrieved_count = 0
        try:
            print(f"调用 scholarly.search_pubs with query: '{query}', year_low: {year_low}, year_high: {year_high}")
            search_results_iterator = scholarly.search_pubs(query, year_low=year_low, year_high=year_high)
            for i in range(max_results * 2):
                try:
                    result = next(search_results_iterator)
                    retrieved_count += 1
                    if result:
                        print(f"  scholarly 返回结果 {retrieved_count}: {result.get('bib', {}).get('title', '无标题')[:50]}...")
                    else:
                        print(f"  scholarly 返回了一个空结果 {retrieved_count}")
                        continue
                    bib = result.get('bib', {})
                    title = bib.get('title', '')
                    if not title:
                        print("  结果无标题，跳过.")
                        continue
                    url = result.get('pub_url', '')
                    if not url:
                        print(f"  结果 '{title[:30]}...' 无URL，跳过.")
                        continue
                    if url in self.seen_urls:
                        print(f"  结果 '{title[:30]}...' URL重复，跳过.")
                        continue
                    current_year_str = str(bib.get('pub_year', ''))
                    paper_data = {
                        "title": title,
                        "authors": "; ".join(bib.get('author', [])),
                        "year": current_year_str,
                        "abstract": bib.get('abstract', '')[:300] + "..." if bib.get('abstract') else '',
                        "url": url
                    }
                    self.results.append(paper_data)
                    self.seen_urls.add(url)
                    print(f"  已添加: '{title[:30]}...'. 当前结果数: {len(self.results)}/{max_results}")
                    if len(self.results) >= max_results:
                        print(f"已达到最大结果数 {max_results}")
                        break
                    await asyncio.sleep(random.uniform(*REQUEST_DELAY))
                except StopIteration:
                    print("scholarly.search_pubs 已无更多结果.")
                    break
                except Exception as e:
                    print(f"\n从scholarly获取单个结果时出错: {str(e)}")
                    continue
            print(f"scholarly 检索循环结束. 共尝试获取 {retrieved_count} 条, 实际添加到self.results的有 {len(self.results)} 条.")
            # 不再保存xlsx
        except Exception as e:
            print(f"\n致命错误: {str(e)}")


async def main_workflow():
    print("\n=== 智能文献检索系统 ===")

    try:
        keywords = input("请输入研究关键词（英文）: ").strip()
        if not keywords:
            raise ValueError("必须输入关键词")

        max_results = input(f"最大结果数 [{DEFAULT_MAX_RESULTS}]: ").strip()
        max_results = int(max_results) if max_results.isdigit() else DEFAULT_MAX_RESULTS

        output_file = input(f"输出文件名 [{DEFAULT_OUTPUT_FILE}]: ").strip()
        output_file = output_file or DEFAULT_OUTPUT_FILE

        print("\n🔄 正在扩展关键词...")
        expander = GroqKeywordExpander()
        expanded_terms = await expander.expand_keywords(keywords)
        print(f"🔍 扩展后的关键词: {', '.join(expanded_terms)}")

        query_engine = QueryBuilder(expanded_terms)
        search_query = query_engine.build_query()
        print(f"\n⚙️ 生成的搜索式: {search_query}")

        collector = LiteratureCollector()
        await collector.collect(search_query, max_results, None)

    except Exception as e:
        print(f"\n❌ 系统错误: {str(e)}")
    finally:
        print("\n程序执行结束")


if __name__ == "__main__":
    asyncio.run(main_workflow())