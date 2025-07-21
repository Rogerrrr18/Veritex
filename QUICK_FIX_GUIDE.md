# 快速修复指南

## 🔧 立即修复LLM模型配置

### 1. 更新Groq模型名称

当前Groq支持的模型（2024年最新）：
- `llama-3.1-8b-instant` (推荐)
- `llama-3.1-70b-versatile`
- `gemma2-9b-it`

### 2. 批量更新模型配置

需要更新的文件：
- `enhanced_keyword_expander.py`
- `query_intent_analyzer.py` 
- `structured_data_extractor.py`
- `elicit_research_engine.py`

### 3. 修复命令

运行以下命令一次性修复所有模型配置：

```bash
# 更新为推荐的llama模型
find . -name "*.py" -exec sed -i '' 's/mixtral-8x7b-32768/llama-3.1-8b-instant/g' {} \;

# 或者更新为gemma模型（当前.env中的配置）
find . -name "*.py" -exec sed -i '' 's/mixtral-8x7b-32768/gemma2-9b-it/g' {} \;
```

## 🚀 启动测试服务器

### 1. 启动后端API服务器
```bash
python -m uvicorn backend:app --reload --port 8000
```

### 2. 访问API文档
```bash
open http://localhost:8000/docs
```

### 3. 测试新端点
```bash
# 快速搜索测试
curl -X POST "http://localhost:8000/quick_search" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "max_papers": 10, "user_id": "test_user"}'

# 查询分析测试  
curl -X POST "http://localhost:8000/analyze_query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is deep learning?", "user_id": "test_user"}'
```

## 📋 验证清单

- [ ] 更新所有文件中的模型名称
- [ ] 确认Groq API密钥有效
- [ ] 启动后端服务器无错误
- [ ] 访问 /docs 页面显示新端点
- [ ] 测试至少一个新API端点
- [ ] 前端可以调用新的API

## 🎯 下一步计划

1. **立即**: 修复LLM模型配置
2. **今天**: 完成端到端测试  
3. **本周**: 前端集成新功能
4. **下周**: 部署和用户测试

修复完成后，你的系统将具备完整的Elicit风格学术研究功能！