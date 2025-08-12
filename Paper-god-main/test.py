import pandas as pd
import openpyxl

def test_excel():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    df.to_excel("test.xlsx", index=False, engine='openpyxl')
    print("测试文件生成成功")

if __name__ == "__main__":
    test_excel()  # 确保函数调用闭合