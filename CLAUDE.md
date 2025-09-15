# CLAUDE.md

Veritex betaV3项目指南 - AI驱动的学术文献检索系统

## 项目概述

Veritex betaV3是一个现代化的AI驱动学术文献搜索系统，采用FastAPI后端 + React前端架构，集成多LLM智能对话、关键词扩展和多源搜索引擎，专为Docker云端部署优化。

**核心特性**:
- 🔍 多源文献搜索：ScholarDock + arXiv + 学术镜像
- 🤖 智能对话系统：基于LangGraph的工作流
- 💾 混合存储架构：内存缓存 + Supabase云端
- 🌐 多LLM支持：OpenAI/Claude/DeepSeek/Qwen/Doubao
- 🐳 容器化部署：Docker生产环境优化

## 系统架构

### 后端架构 (Python/FastAPI)

#### 🎯 API服务层
- **`backend.py`** - FastAPI主服务器
  - `/chat` - 智能对话端点 (主要)
  - `/search_papers` - 传统搜索接口
  - `/performance` - 性能监控

#### 🧠 智能工作流层
- **`langchain_workflows/`** - LangGraph智能工作流
  - `paper_search_workflow.py` - 核心搜索工作流
  - `state_schemas.py` - 状态管理
  - `visualize_workflow.py` - 工作流可视化

#### 🔍 搜索引擎层
- **`multi_source_engine.py`** - 多源搜索协调器
- **`scholar_dock_spider.py`** - ScholarDock爬虫（主力）
- **`scholar_mirror_api.py`** - 学术镜像API

#### 🤖 LLM接口层
- **`llm_interface.py`** - 统一LLM管理器
- **`adapters/`** - 多模型适配器
  - `openai_adapter.py` - GPT系列
  - `claude_adapter.py` - Claude系列 
  - `deepseek_adapter.py` - DeepSeek系列
  - `qwen_adapter.py` - 通义千问
  - `doubao_adapter.py` - 豆包
- **`model_config.py`** - 模型配置管理

#### 💾 数据存储层
- **`conversation_manager.py`** - 混合缓存架构
  - 内存缓存（一级）- 快速访问
  - Supabase云端（二级）- 持久化存储
- **`supabase_sync.py`** - Supabase同步管理
- **`models/conversation.py`** - 数据模型定义

#### 📊 监控分析层
- **`performance_monitor.py`** - 性能监控
- **`prompt_utils.py`** - Prompt模板管理
- **`prompts/`** - 提示词模板库

### 前端架构 (React + TypeScript)

#### 🎨 技术栈
- **React 19** + TypeScript 5.8
- **Vite 6** 构建系统
- **Supabase** 用户认证和数据
- **React Router** 路由管理
- **React Markdown** 内容渲染

#### 📁 目录结构
```
frontend/src/
├── App.tsx                 # 主应用组件
├── ChatInterface.tsx       # 聊天界面核心组件
├── components/            # 可复用组件
├── contexts/              # React上下文
├── hooks/                 # 自定义Hook
├── utils/                 # 工具函数
├── supabaseClient.ts      # Supabase客户端
├── auth.ts               # 认证逻辑
└── config.ts             # 配置管理
```

### 容器化部署

#### 🐳 Docker配置
- **`Dockerfile.backend`** - 后端容器镜像
  - Python 3.11-slim基础镜像
  - 国内镜像源优化
  - 多进程uvicorn配置
  - 健康检查集成

- **`frontend/Dockerfile`** - 前端容器镜像
  - 多阶段构建（Node构建 + Nginx服务）
  - 静态资源优化
  - Nginx配置定制

## 核心功能特性

### 🎯 智能搜索工作流
```
用户输入 → 意图分类 → 路由决策 → 多源搜索 → 结果融合 → 智能回复
```

### 🔍 多源搜索引擎
- **ScholarDock**: 主力搜索源，自动处理验证码
- **arXiv**: 预印本文献集成
- **学术镜像**: 备用搜索源
- **智能去重**: 基于DOI和语义相似度

### 💬 对话管理系统
- **多轮上下文**: 支持连续学术讨论
- **用户隔离**: 基于Supabase RLS的数据安全
- **历史同步**: 跨设备对话记录同步
- **设置持久化**: 用户偏好云端存储

### 🤖 多LLM支持
- **统一接口**: 抽象适配器模式
- **自动故障转移**: 模型不可用时智能切换
- **配额管理**: 智能负载均衡
- **性能监控**: Token使用统计

## 开发指导

### 🎨 代码规范
- 使用中文注释和文档
- 遵循TypeScript严格模式
- 组件化和模块化设计
- 错误处理和降级策略

### 🚀 性能优化
- 异步并发搜索
- 三级缓存架构
- 连接池复用
- 流式响应处理

### 🔒 安全考量
- 环境变量管理敏感信息
- Supabase RLS数据隔离
- 输入验证和清理
- API访问控制

## 依赖管理

### 后端核心依赖
```txt
fastapi>=0.110.0          # Web框架
uvicorn[standard]>=0.27.0 # ASGI服务器
langgraph>=0.2.0          # AI工作流
aiohttp>=3.9.5            # 异步HTTP
supabase>=2.3.0           # 云端数据库
selenium>=4.17.2          # Web爬虫
```

### 前端核心依赖
```json
{
  "react": "^19.1.0",
  "@supabase/supabase-js": "^2.55.0",
  "react-router-dom": "^6.30.1",
  "react-markdown": "^10.1.0"
}
```

## 部署和运维

### 🐳 Docker部署
```bash
# 后端构建和运行
docker build -f Dockerfile.backend -t veritex-backend .
docker run -p 8000:8000 veritex-backend

# 前端构建和运行
cd frontend
docker build -t veritex-frontend .
docker run -p 80:80 veritex-frontend
```

### 🔧 环境配置
- `.env` - 生产环境变量
- `.env.template` - 配置模板
- 参考`DEPLOY.md`获取详细部署指南

### 📊 监控和日志
- 性能指标通过`/performance`端点获取
- 错误日志自动记录到Supabase
- Docker健康检查集成

## 开发状态

### ✅ 已完成
- 多LLM适配器架构
- ScholarDock爬虫集成
- Supabase云端存储
- Docker容器化部署
- LangGraph智能工作流

### 🚧 进行中
- 搜索结果质量优化
- 用户体验改进
- 性能监控仪表板

### 📋 待优化
- 移动端响应式设计
- 国际化多语言支持
- 更多搜索源集成

---

## 重要提醒

1. **数据存储**: 完全基于Supabase云端，无本地数据库依赖
2. **模型切换**: 支持多LLM供应商，自动故障转移
3. **容器优先**: Docker优化部署，支持云原生架构
4. **用户隔离**: 严格的多租户数据安全策略
5. **性能监控**: 实时监控和自动告警系统

每次重要更新后请同步更新此文档，建议使用Git分支管理不同版本。