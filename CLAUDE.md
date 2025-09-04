# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

这是一个AI驱动的学术文献搜索系统，支持全学科文献检索。采用FastAPI后端 + React前端架构，集成LLM智能对话、关键词扩展和多源搜索引擎，专为Docker云端部署优化。

**最新架构优化**:
- ✅ 移除本地SQLite缓存，专为Docker部署优化
- ✅ 简化为双层架构：内存缓存 + Supabase云端存储
- ✅ ScholarDock爬虫替代scholarly，获得70%搜索配额
- ✅ LangGraph智能工作流，支持学术对话和文献推荐
- ✅ 多LLM适配器架构，支持OpenAI/Claude/DeepSeek/Qwen/Doubao

## 系统架构

### Backend核心模块

#### 🎯 API层 (`backend.py`)
- FastAPI REST API服务器
- 智能对话端点：`/chat`（推荐）
- 传统搜索端点：`/search_papers` 
- 性能监控端点：`/performance`

#### 🧠 智能工作流层 (`langchain_workflows/`)
- **`paper_search_workflow.py`**: LangGraph智能搜索工作流
- **`state_schemas.py`**: 状态管理和数据结构
- **自动路由**: 学术查询 vs 闲聊判断
- **多轮对话**: 上下文保持和对话管理

#### 🔍 搜索引擎层
- **`multi_source_engine.py`**: 多源搜索引擎协调器
- **`scholar_dock_spider.py`**: ScholarDock高效爬虫
- **`scholar_mirror_api.py`**: 学术镜像API适配
- **智能配额分配**: ScholarDock 70% + 其他源 30%

#### 🤖 LLM接口层
- **`llm_interface.py`**: 统一LLM接口管理器
- **`adapters/`**: 多模型适配器目录
  - `openai_adapter.py`: GPT系列
  - `claude_adapter.py`: Claude系列
  - `deepseek_adapter.py`: DeepSeek系列
  - `qwen_adapter.py`: 通义千问系列
  - `doubao_adapter.py`: 豆包系列
- **`model_config.py`**: 模型配置管理
- **`llm_intent_classifier.py`**: 意图分类器

#### 💾 数据存储层
- **`hybrid_conversation_manager.py`**: 双层缓存架构管理器
  - 内存缓存（第一层）: 快速访问
  - Supabase云端存储（第二层）: 持久化和RLS安全
  - JSON备用（第三层）: 向后兼容
- **`models/conversation.py`**: 对话数据模型
- **用户数据隔离**: 基于RLS的多租户架构

#### 📊 监控分析层
- **`performance_monitor.py`**: 性能监控和统计
- **`prompt_utils.py`**: Prompt模板管理

### Frontend架构 (React + TypeScript)

- **Vite-based** 构建系统
- **React Router** 路由管理
- **Supabase集成** 用户数据管理
- **组件化设计**: 搜索界面 + 结果展示 + Excel导出

### 数据流架构

#### 智能搜索工作流
```
用户输入 → 意图分类 → 路由决策 → 执行搜索 → 结果处理 → 响应返回
    ↓         ↓         ↓         ↓         ↓         ↓
  闲聊检测   学科识别   工作流选择  多源搜索   去重排序   流式输出
```


## 核心功能模块

### 🎯 意图分类系统
- **快速预筛选**: 避免不必要的LLM调用
- **学科自动识别**: 10+学科领域支持
- **缓存机制**: 提升分类性能

### 🔍 多源搜索引擎
- **ScholarDock爬虫**: 主力搜索源，CAPTCHA自动处理
- **arXiv集成**: 预印本文献支持
- **智能去重**: 基于DOI和标题相似度

### 💬 对话管理系统
- **多轮上下文**: 支持连续学术讨论
- **用户数据隔离**: 基于用户ID的安全存储
- **历史记录**: 搜索和聊天历史完整保存
- **设置同步**: 用户偏好跨设备同步

### 📊 性能监控
- **实时统计**: API响应时间、搜索成功率
- **LLM使用跟踪**: Token消耗和模型切换
- **错误告警**: 异常情况自动记录
- **用户行为分析**: 操作埋点和使用模式分析

## 开发指导原则

### 代码规范
- **响应式设计**: 前端必须支持移动端
- **中文注释**: 所有代码注释使用中文
- **模块化架构**: 单一职责，高内聚低耦合
- **错误处理**: 完善的异常捕获和降级策略

### 性能优化
- **异步并发**: 多源搜索并行执行
- **智能缓存**: 三层缓存架构最大化命中率
- **连接池**: 数据库和HTTP连接复用
- **流式响应**: 大数据量分批传输

### 安全考量
- **API密钥管理**: 环境变量隔离敏感信息
- **用户数据隔离**: RLS策略确保数据安全
- **输入验证**: 防止注入攻击和恶意输入
- **访问控制**: 基于内测码的用户准入

## 最新开发状态

### ✅ 已完成功能
- 多LLM适配器架构实现
- ScholarDock爬虫集成优化  
- Docker部署架构简化
- 用户数据管理系统完善
- LangGraph智能工作流集成

### 🚧 开发中功能
- 搜索结果质量优化
- 用户界面响应式改进
- 性能监控仪表板

### 📋 待优化事项
- 移动端用户体验优化
- 搜索算法精度提升
- 多语言国际化支持

---

## 重要提醒

- **数据存储**: 完全基于Supabase，无本地文件依赖
- **模型支持**: 多LLM供应商，自动故障转移
- **部署方式**: Docker优先，支持云原生架构  
- **用户隔离**: 严格的多租户数据安全
- **性能优先**: 缓存和并发优化，毫秒级响应

每次代码修改后，请更新此文档中的相关模块描述，并建议创建新的Git分支进行版本管理。