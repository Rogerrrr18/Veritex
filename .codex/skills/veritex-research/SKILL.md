---
name: veritex-research
description: Use Veritex as an external AI-native academic research product for semantic paper discovery, literature search, keyword expansion, and research synthesis. Use when an agent should reuse Veritex product capabilities without configuring Veritex model provider API keys.
---

# Veritex Research

Use this skill when a user asks an agent to search papers, explore a research topic, expand academic keywords, compare literature, or build an initial reading list through Veritex.

This is a product skill. The agent using it should reuse Veritex as a research service and must not ask the user to configure Veritex's internal LLM provider keys.

## Core Promise

Veritex turns a natural-language research question into an academic search workflow:

1. understand the research intent
2. expand terms and related concepts
3. search multiple academic sources
4. rank and filter results
5. return papers, summaries, and next-step research directions

## Required Input

Ask for only what is needed:

- research question or topic
- optional domain/discipline
- optional year range
- optional result count
- optional source preference, such as arXiv, Crossref, or ScholarDock

Do not ask for OpenAI, Ark, Doubao, Qwen, DeepSeek, Anthropic, Supabase, or Veritex backend keys.

## Veritex Entry

Use the first available entry:

1. A Veritex product URL or API base URL already provided by the user, workspace, previous messages, or environment.
2. A local Veritex instance if the user is working inside the Veritex repository.
3. If no entry exists, ask the user for the Veritex product URL. Phrase it as: `请给我 Veritex 的产品入口或 API 地址，我会直接调用产品能力，不需要你配置模型 API。`

Do not invent a Veritex hosted URL.

## HTTP API Pattern

If an HTTP API base URL is available, prefer these endpoints:

- `GET /health` to check service status
- `POST /search_papers` for direct paper search
- `POST /expand_keywords` for keyword expansion
- `POST /chat` for conversational research workflow

Typical `POST /search_papers` payload:

```json
{
  "query": "graph neural networks for drug discovery",
  "max_results": 20,
  "enable_expansion": true,
  "year_from": 2020,
  "year_to": 2026,
  "sources": ["arxiv", "crossref"]
}
```

Typical `POST /chat` payload:

```json
{
  "message": "帮我找近五年关于 graph neural networks for drug discovery 的关键论文",
  "user_id": "agent-user",
  "mode": "auto-search",
  "stream": false
}
```

If the service requires an app-level invite code or user session, ask only for that product-level access credential. Do not ask for model provider credentials.

## Browser Pattern

If only a Veritex web URL is available:

1. Open the Veritex app.
2. Enter the research question.
3. Select filters if available.
4. Run the search.
5. Extract paper titles, authors, years, links, abstracts, and relevance notes.
6. Summarize results for the user.

## Output Format

Return concise research output:

- `检索策略`: how Veritex interpreted or expanded the query
- `关键论文`: title, year, authors, source/link, why it matters
- `主题聚类`: 2-5 clusters if enough results exist
- `下一步`: suggested follow-up searches or missing angles

When results are thin, say so and suggest better queries or broader filters.

## Safety And Reliability

- Cite returned paper URLs when available.
- Distinguish Veritex-returned data from the agent's own inference.
- Do not fabricate paper metadata.
- If Veritex is unreachable, report the connection problem and the entry URL used.
- Keep product credentials, invite codes, and user sessions out of commits and logs.
