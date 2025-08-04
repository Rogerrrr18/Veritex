# 🚀 通用MCP系统使用指南

## 📋 系统概述

全新的通用MCP架构实现了**零代码添加新服务**的目标，类似Claude的插件机制。

### ✨ 核心特性
- **零代码扩展**: 只需修改JSON配置即可添加新的学术搜索服务
- **统一数据格式**: 所有服务返回标准化的论文数据结构
- **并行多源搜索**: 同时查询2-3个数据源并自动合并结果
- **智能去重**: 基于标题相似度自动去除重复论文
- **预定义策略**: 快速、全面、学术三种搜索策略

## 🚀 快速启动

### 1. 启动服务
```bash
./start_backend.sh
```

### 2. 访问接口
- **服务地址**: http://127.0.0.1:8005
- **API文档**: http://127.0.0.1:8005/docs
- **健康检查**: http://127.0.0.1:8005/health

## 📡 主要API端点

### 通用搜索 (推荐)
```bash
curl -X POST http://127.0.0.1:8005/universal_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "methane dry reforming",
    "sources": ["arxiv", "crossref"],
    "limit": 20
  }'
```

### 策略搜索
```bash
curl -X POST "http://127.0.0.1:8005/search_by_strategy?strategy=comprehensive&query=machine learning&limit=15"
```

### 获取服务信息
```bash
curl http://127.0.0.1:8005/services
```

## 🎯 搜索策略

| 策略 | 数据源 | 用途 |
|------|--------|------|
| **fast** | arXiv | 快速搜索，适合预印本 |
| **comprehensive** | arXiv + CrossRef + PubMed | 全面搜索，覆盖多个领域 |
| **academic** | Semantic Scholar + CrossRef | 学术搜索，高质量期刊 |

## 📚 支持的数据源

- **arXiv**: ✅ 预印本论文库
- **CrossRef**: ✅ 学术文献数据库  
- **PubMed**: ✅ 生物医学文献
- **Semantic Scholar**: ⚠️ 需要API密钥，目前禁用

## ➕ 添加新数据源

只需要添加JSON配置，无需编程：

```bash
curl -X POST http://127.0.0.1:8005/services/add \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "ieee",
    "service_config": {
      "name": "IEEE Xplore",
      "enabled": true,
      "base_url": "https://ieeexploreapi.ieee.org",
      "search_config": {
        "endpoint": "/api/v1/search/articles",
        "param_mapping": {"query": "querytext", "limit": "max_records"}
      },
      "response_config": {
        "format": "json",
        "papers_path": "articles",
        "field_mapping": {
          "id": "doi",
          "title": "title",
          "abstract": "abstract"
        }
      }
    }
  }'
```

## 📊 返回数据格式

```json
{
  "success": true,
  "papers": [
    {
      "id": "论文唯一标识",
      "title": "论文标题",
      "abstract": "论文摘要",
      "authors": [{"name": "作者名"}],
      "year": 2023,
      "venue": "期刊名",
      "url": "论文链接",
      "source": "数据来源"
    }
  ],
  "total_count": 10,
  "source_stats": {"arxiv": 5, "crossref": 5}
}
```

## 🔧 配置文件

主配置文件: `universal_mcp_config.json`

- 修改服务配置
- 添加新的搜索策略
- 调整去重和排序参数

## 🎉 使用示例

### 搜索甲烷干重整论文
```bash
curl -X POST http://127.0.0.1:8005/universal_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "methane dry reforming catalyst",
    "sources": ["arxiv", "crossref"],
    "limit": 20,
    "category": "physics.chem-ph"
  }'
```

### 多领域综合搜索
```bash
curl -X POST "http://127.0.0.1:8005/search_by_strategy?strategy=comprehensive&query=artificial intelligence&limit=25"
```

---

🎯 **现在你可以像Claude一样简单地管理MCP服务了！**