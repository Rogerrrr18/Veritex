# Paper Finder 智能文献检索系统

## 功能简介
- 关键词同义词扩展（大模型）
- 学术论文批量爬取（Google Scholar）
- 结果存储（CSV/Supabase，后续集成）
- 前后端分离，支持Web交互

## 环境配置

### 1. 创建 .env 文件
在项目根目录下创建 `.env` 文件，内容如下：
```
# Groq API 配置
GROQ_API_KEY=你的groq api key
GROQ_MODEL=mixtral-8x7b-32768

# Supabase 配置
SUPABASE_URL=你的supabase url
SUPABASE_KEY=你的supabase key
SUPABASE_TABLE=papers
```

### 2. 获取 API 密钥
- **Groq API Key**: 访问 [Groq Console](https://console.groq.com/) 获取
- **Supabase**: 访问 [Supabase](https://supabase.com/) 创建项目并获取密钥

## 后端（FastAPI）

### 依赖安装
```bash
pip install -r requirements.txt
```

### 启动后端服务
```bash
python -m uvicorn backend:app --reload
```

### 验证后端
- 访问 http://127.0.0.1:8000/docs 查看 API 文档
- 检查控制台输出，确认环境变量加载成功

## 前端

### 安装依赖
```bash
cd frontend
npm install
```

### 启动前端服务
```bash
npm run dev
```

### 访问应用
- 前端地址：http://localhost:5173/
- 确保后端服务同时运行

## 使用流程
1. 在前端输入英文关键词
2. 点击"关键词扩展"获取相关术语
3. 设置检索参数（数量、年份范围）
4. 点击"开始检索论文"
5. 查看检索结果

## 常见问题

### Python 版本兼容性
- 支持 Python 3.7+
- 如遇到 `asyncio.to_thread` 错误，已修复为兼容版本

### API 配置问题
- 确保 `.env` 文件存在且配置正确
- 检查 Groq API 密钥是否有效
- 确认模型名称正确（推荐使用 `mixtral-8x7b-32768`）

### 文件下载问题
- 已移除Excel报告生成功能
- 检索结果直接在前端显示

## 目录结构
- main.py：核心爬虫与扩展逻辑
- backend.py：FastAPI后端接口
- requirements.txt：后端依赖
- frontend/：React前端项目
- README.md：项目说明 