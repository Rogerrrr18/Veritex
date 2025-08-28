# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered academic literature search system that supports all academic disciplines. It consists of a FastAPI backend and React frontend with intelligent keyword expansion using LLM and optimized multi-source search engine.

**最新优化 (2025-01-18)**:
- ✅ 完全移除scholarly库，使用ScholarDock高效爬虫替代
- ✅ 修复搜索篇数分配逻辑：ScholarDock主力搜索获得70%配额
- ✅ 优化复杂查询处理，ScholarDock智能简化布尔查询
- ✅ 集成LangGraph智能工作流，支持学术对话和文献推荐
- ✅ 添加性能监控和统计分析

## Architecture

### Backend (FastAPI)
- **backend.py**: FastAPI REST API with intelligent chat and search endpoints
- **multi_source_engine.py**: 优化的多源搜索引擎，支持智能配额分配
- **langchain_workflows/**: LangGraph智能工作流，支持学术对话和文献推荐
- **llm_interface.py**: 统一LLM接口，支持OpenAI/Anthropic/Groq多模型
- **performance_monitor.py**: 性能监控和统计分析

**Key Features**:
  - 智能配额分配：ScholarDock获得70%配额，确保搜索结果数量
  - 优化的爬虫技术：基于ScholarDock项目，支持复杂查询和CAPTCHA处理
  - Multi-discipline keyword expansion using LLM (10+ disciplines)
  - 快速意图预筛选：避免不必要的LLM调用
  - LangGraph智能工作流：自动判断学术查询vs闲聊
  - 预扩展关键词复用：减少重复LLM分析

### Frontend (React + TypeScript)
- **Vite-based** React application with TypeScript
- **React Router** for navigation between search interface and report view
- **Key Components**:
  - Main search interface with intelligent keyword expansion
  - Editable keyword tags with dynamic validation
  - Report viewer with expandable abstracts and Excel export
- **Dependencies**: react-router-dom

### Data Flow

**优化后的搜索流程**:
1. User input → Frontend sends to `/chat` (智能对话) or `/search_papers`
2. 快速意图预筛选：明显闲聊直接LLM回复，学术查询进入搜索流程
3. LLM智能分析：学科检测 + 关键词扩展
4. 智能配额分配：ScholarDock主力搜索70%，其他数据源30%
5. 多源并行搜索：ScholarDock + Semantic Scholar + arXiv
6. 智能去重和相关性排序
7. Results returned with performance metrics

**配额分配示例**:
- 30篇搜索 = ScholarDock 21篇 + semantic_scholar 5篇 + arxiv 5篇
- 50篇搜索 = ScholarDock 35篇 + 其他源各7篇

## Development Commands

### Backend Setup & Run
```bash
# Install dependencies (最新版本)
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env添加LLM API密钥

# Start backend server (auto-reload enabled)
python -m uvicorn backend:app --reload

# 测试搜索配额分配
python test_search_quota.py

# 测试大量搜索
python test_large_search.py

# API documentation
open http://127.0.0.1:8000/docs
```

### Frontend Setup & Run
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint

# Preview production build
npm run preview
```
## Development Guidelines

### 开发指导原则
- 前端页面修改必须考虑移动端兼容性，采用响应式设计
- 代码上下文控制:500行以下提供完整代码文件，超过500行提供关键函数代码
- 避免迭代式代码，一次性提供完整修改代码
- 简化代码，仅修复关键问题
- 代码注释全部使用中文
- 每次修改完代码，必须列出修改代码的文件列表（标出：已有/新增），对应代码函数
- 并引导我将项目push到github分支上（可以新创建）

### 性能优化原则
- ScholarDock作为主力搜索源，获得70%搜索配额
- 优化的HTML解析和CAPTCHA处理，基于ScholarDock技术
- 智能查询简化，支持复杂布尔逻辑
- 预扩展关键词复用，减少重复LLM调用
- 快速意图预筛选，提升响应速度

## Testing & Debugging

### 搜索测试
```bash
# 测试搜索配额分配
python test_search_quota.py

# 测试大量搜索（50篇）
python test_large_search.py

# 模拟API调用测试
python test_api_search.py
```

### 性能监控
- Backend logs显示配额分配和搜索进度
- `/performance` 端点查看性能统计
- Frontend console显示API请求/响应详情
- 使用 `/docs` 进行交互式API测试

### 关键指标
- ScholarDock搜索成功率
- 平均响应时间
- 搜索结果数量达成率
- LLM调用次数和token消耗

## Important Notes

### 搜索引擎优化
- 智能配额分配：ScholarDock 70% + 其他源 30%
- 优化的HTML解析：直接爬取Google Scholar，支持CAPTCHA处理
- 基于ScholarDock项目成功经验，高效稳定
- 支持中英文关键词输入和智能扩展

### 数据源配置
- Google Scholar (ScholarDock爬虫) - 主力搜索源
- Semantic Scholar - 高质量学术数据
- arXiv - 预印本文献
- 可选：PubMed, Crossref

### LLM集成
- 支持多LLM模型：OpenAI/Anthropic/Groq
- 学科检测：10+学科领域自动识别
- 智能工作流：LangGraph实现学术对话
- 性能优化：快速意图预筛选 + 关键词复用

### API接口演进
- `/chat` - 推荐的智能对话接口
- `/search_papers` - 传统搜索接口（支持预扩展关键词优化）
- `/expand_keywords` - 独立关键词扩展
- `/performance` - 性能统计监控

## 修改代码文件列表

### 最近优化 (2025-01-18)
**已修改文件**:
- ✅ `multi_source_engine.py` - 修复搜索配额分配逻辑（第1117-1121行）
- ✅ `requirements.txt` - 更新依赖到最新版本
- ✅ `README.md` - 全面更新项目文档和特性说明
- ✅ `CLAUDE.md` - 更新开发指南和架构说明

**新增文件**:
- ✅ `test_search_quota.py` - 搜索配额分配测试
- ✅ `test_large_search.py` - 大量搜索测试
- ✅ `test_api_search.py` - API调用测试

**删除文件**:
- ✅ `multi_source_engine_original.py` - 删除未使用的旧版文件

### 核心函数修改
- `search_parallel_with_filters()` - 优化配额分配策略
- `ScholarlyAPI.search()` - 简化scholarly调用逻辑

