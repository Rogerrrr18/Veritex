from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from main import PaperGodSearchEngine
from multi_source_engine import Paper

app = FastAPI(
    title="Paper God API",
    description="学术文献智能搜索系统 - 多源融合版本",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

search_engine = None

def get_search_engine():
    global search_engine
    if search_engine is None:
        search_engine = PaperGodSearchEngine()
        logger.info("搜索引擎初始化成功")
    return search_engine

class SearchRequest(BaseModel):
    query: str
    max_results: int = 20
    enable_expansion: bool = True

class ExpandKeywordsRequest(BaseModel):
    keywords: str
    max_keywords: int = 5

def format_paper_for_api(paper: Paper) -> Dict[str, Any]:
    return {
        "title": paper.title or "",
        "authors": paper.authors or [],
        "abstract": paper.abstract or "",
        "year": paper.year,
        "journal": paper.journal or "",
        "url": paper.url or "",
        "doi": paper.doi,
        "citations": paper.citations or 0,
        "source": paper.source,
        "relevance_score": paper.relevance_score or 0.0
    }

@app.post("/expand_keywords")
async def expand_keywords_api(req: ExpandKeywordsRequest):
    try:
        logger.info(f"关键词扩展请求: {req.keywords}")
        engine = get_search_engine()
        
        # 调用关键词扩展功能
        expansion_result = await engine.keyword_expander.detect_and_expand(
            req.keywords, 
            max_keywords=req.max_keywords
        )
        
        return {
            "success": True,
            "data": {
                "original_query": expansion_result.original_query,
                "expanded_keywords": expansion_result.expanded_keywords,
                "detected_discipline": expansion_result.detected_discipline,
                "discipline_chinese": expansion_result.discipline_chinese,
                "confidence": expansion_result.confidence,
                "expansion_strategy": expansion_result.expansion_strategy,
                "quality_score": expansion_result.quality_score,
                "processing_time": expansion_result.processing_time
            }
        }
    except Exception as e:
        logger.error(f"关键词扩展失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {
                "original_query": req.keywords,
                "expanded_keywords": [req.keywords],
                "detected_discipline": "unknown",
                "discipline_chinese": "未知",
                "confidence": 0.0,
                "expansion_strategy": "fallback",
                "quality_score": 0.0,
                "processing_time": 0.0
            }
        }

@app.post("/search_papers")
async def search_papers_api(req: SearchRequest):
    try:
        logger.info(f"搜索请求: {req.query}")
        engine = get_search_engine()
        result = await engine.search(req.query, req.max_results, req.enable_expansion)
        
        formatted_papers = [format_paper_for_api(paper) for paper in result['papers']]
        
        return {
            "success": True,
            "data": {
                "papers": formatted_papers,
                "total_found": len(formatted_papers),
                "query_info": result.get('query_info', {}),
                "performance": result.get('performance', {})
            }
        }
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {"papers": [], "total_found": 0}
        }

@app.get("/health")
async def health_check():
    try:
        engine = get_search_engine()
        return {
            "status": "healthy",
            "version": "2.0.0",
            "data_sources": ["semantic_scholar", "arxiv", "paperscraper"]
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/")
async def root():
    return {
        "message": "Paper God API - 学术文献智能搜索系统",
        "version": "2.0.0",
        "endpoints": {
            "/expand_keywords": "关键词扩展", 
            "/search_papers": "论文搜索", 
            "/health": "健康检查"
        }
    }

@app.on_event("shutdown")
async def shutdown_event():
    global search_engine
    if search_engine:
        await search_engine.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)