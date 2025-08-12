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
import openpyxl
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

REPORTS_DIR = "generated_reports"

os.makedirs(REPORTS_DIR, exist_ok=True)
print(f"目录 {REPORTS_DIR} 已创建或存在。")

#print(f"openpyxl 版本: {openpyxl.__version__}")

df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
df.to_excel("test.xlsx", index=False, engine='openpyxl')
#print("测试文件 'test.xlsx' 生成成功。")
print("Current GROQ_MODEL:", os.getenv("GROQ_MODEL"))
print(f"当前 Python 路径: {sys.executable}")

class GroqKeywordExpander:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)

    async def expand_keywords(self, keywords: str) -> List[str]:
        """严格限制只返回关键词列表"""
        try:
            prompt = f"""
            作为化学专家，请为以下关键词生成5个最相关的英文搜索术语：
            - 原始关键词: {keywords}

            要求：
            1. 仅返回逗号分隔的英文术语
            2. 不要包含任何解释或说明
            3. 每个术语都必须是有效的学术搜索词
            4. 格式示例：term1,term2,term3

            请直接输出术语：
            """

            print(f"向 Groq API 发送请求，模型: {GROQ_MODEL}, 原始关键词: {keywords}")
            
            # 替换 asyncio.to_thread 为直接同步调用，兼容 Python 3.7+
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # 降低随机性
                max_tokens=100
            )

            # 严格清洗结果
            raw_terms = response.choices[0].message.content
            terms = [term.strip() for term in raw_terms.split(",")
                     if term.strip() and len(term.strip()) > 2]
            return list(set(terms))[:8]  # 限制返回数量

        except Exception as e:
            print(f"调用 Groq API 失败。模型: {GROQ_MODEL}, 原始关键词: {keywords}。错误详情: {str(e)}")
            print("请检查您的 GROQ_API_KEY 是否有效，以及 GROQ_MODEL 名称是否正确且在您的账户下可用。")
            return [keywords]


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
        os.makedirs(REPORTS_DIR, exist_ok=True)

    async def collect(self, query: str, max_results: int, output_filename: str, year_low: Optional[int] = None, year_high: Optional[int] = None):
        print(f"\n开始检索: {query}, 年份范围: {year_low}-{year_high}, 最大结果: {max_results}")
        self.results = [] # Ensure results are reset for each call
        self.seen_urls = set() # Ensure seen_urls are reset
        retrieved_count = 0
        try:
            # Pass year_low and year_high to scholarly's search_pubs
            print(f"调用 scholarly.search_pubs with query: '{query}', year_low: {year_low}, year_high: {year_high}")
            search_results_iterator = scholarly.search_pubs(query, year_low=year_low, year_high=year_high)
            
            for i in range(max_results * 2): # Try to fetch more to see if any results come through at all
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
                    # Optional: Explicit year check if scholarly's filter isn't trusted or for debugging
                    # if year_low and current_year_str and int(current_year_str) < year_low:
                    #     print(f"  Result '{title[:30]}...' year {current_year_str} < {year_low}, skipping.")
                    #     continue
                    # if year_high and current_year_str and int(current_year_str) > year_high:
                    #     print(f"  Result '{title[:30]}...' year {current_year_str} > {year_high}, skipping.")
                    #     continue

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
                        break # Break from the for loop

                    await asyncio.sleep(random.uniform(*REQUEST_DELAY))

                except StopIteration:
                    print("scholarly.search_pubs 已无更多结果.")
                    break # No more results from iterator
                except Exception as e:
                    print(f"\n从scholarly获取单个结果时出错: {str(e)}")
                    continue # Try to get next result
            
            print(f"scholarly 检索循环结束. 共尝试获取 {retrieved_count} 条, 实际添加到self.results的有 {len(self.results)} 条.")

            self._save_results(os.path.join(REPORTS_DIR, output_filename))
            print(f"\n成功保存 {len(self.results)} 篇文献到 {os.path.join(REPORTS_DIR, output_filename)}")

        except Exception as e:
            print(f"\n致命错误: {str(e)}")

    def _save_results(self, full_path_to_file: str):
        print(f"调用 _save_results. 当前 self.results 中有 {len(self.results)} 条文献.")
        
        # 检查 self.results 内容
        if not self.results:
            print("警告: self.results 为空. 检查爬虫逻辑是否未返回数据.")
            # 生成一个空的 DataFrame 以避免错误
            df = pd.DataFrame(columns=['title', 'authors', 'year', 'abstract', 'url'])
        else:
            print("self.results 内容示例:", self.results[:1])  # 打印第一条数据
        df = pd.DataFrame(self.results)
        
        print(f"转换到DataFrame后有 {len(df)} 行. 列名: {df.columns.tolist()}")
        
        # 检查 DataFrame 是否为空
        if df.empty:
            print("警告: DataFrame 为空. 可能数据格式不正确.")
        
        # 移除包含 'patent' 的标题
        df_before_patent_filter = len(df)
        df = df[~df['title'].str.contains('patent', case=False, na=False)]
        print(f"移除'patent'标题后剩余 {len(df)} 行 (之前 {df_before_patent_filter} 行).")
        
        # 移除重复 URL
        df_before_duplicate_filter = len(df)
        df = df.drop_duplicates(subset=['url'], keep='first')
        print(f"移除重复URL后剩余 {len(df)} 行 (之前 {df_before_duplicate_filter} 行).")

        # 最终检查 DataFrame 是否为空
        if df.empty:
            print("警告: 过滤后 DataFrame 为空. 将生成空文件.")
        
        try:
            print(f"尝试将 {len(df)} 行数据保存到XLSX文件: {full_path_to_file}")
            df.to_excel(full_path_to_file, index=False, engine='openpyxl')
            print(f"成功将 {len(df)} 行数据保存到XLSX.")
            
            # 验证文件是否生成
            if os.path.exists(full_path_to_file):
                print(f"文件已生成: {full_path_to_file}")
                # 读取文件内容验证
                test_df = pd.read_excel(full_path_to_file, engine='openpyxl')
                print(f"文件内容验证: {len(test_df)} 行数据.")
            else:
                print(f"错误: 文件未生成: {full_path_to_file}")
        except Exception as e:
            print(f"保存XLSX文件失败: {full_path_to_file}, 错误: {e}")
            raise  # 重新抛出异常以便调用方处理


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
        await collector.collect(search_query, max_results, output_file)

    except Exception as e:
        print(f"\n❌ 系统错误: {str(e)}")
    finally:
        print("\n程序执行结束")


if __name__ == "__main__":
    asyncio.run(main_workflow())