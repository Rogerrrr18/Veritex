---
name: veritex-model-api
description: Use when configuring, migrating, debugging, or validating Veritex LLM API access, especially OpenAI-compatible model endpoints, ACTIVE_MODEL selection, proxy removal, and safe .env handling.
---

# Veritex Model API

Use this skill when a Veritex agent needs to make the model API work end to end.

## Rules

- Always answer in Chinese when working in this repository.
- Never print or commit real API keys. Mask secrets when inspecting `.env`.
- Do not commit `.env`; use `.env.example` for documented configuration.
- Prefer OpenAI-compatible routing when `ARK_BASE_URL` or any model base URL ends with `/v1`.
- Do not use network proxies for LLM calls unless the user explicitly asks. Adapters should use `trust_env=False`.

## Workflow

1. Inspect configuration without exposing secrets:

```bash
sed -n '1,120p' .env | sed -E 's/(API_KEY=).*/\1***MASKED***/; s/(ANON_KEY=).*/\1***MASKED***/'
```

2. Confirm what the app will load:

```bash
python -c 'from model_config import get_model_config_manager; m=get_model_config_manager(); print(m.get_model_info())'
```

Expected for OpenAI-compatible endpoints:

- `active_model`: `openai`
- `base_url`: ends with `/v1`
- `available_models`: includes `openai`

3. If the provider is OpenAI-compatible but uses legacy `ARK_*` variables, map it as OpenAI:

```env
ACTIVE_MODEL=openai
ARK_API_KEY=your_key_here
ARK_BASE_URL=https://provider.example/v1/
ARK_MODEL_NAME=provider-model-name
ARK_TEMPERATURE=0.3
ARK_MAX_TOKENS=2000
```

4. Ensure `model_config.py` treats `/v1` `ARK_BASE_URL` values as OpenAI-compatible and does not also register them as `doubao`.

5. Ensure `adapters/openai_adapter.py`:

- strips trailing slash from `base_url`
- posts to `${base_url}/chat/completions`
- uses `trust_env=False`
- does not pass `proxy=...`
- has a real timeout fallback, e.g. `config.timeout or 120.0`

6. Validate with the project interface, not a standalone curl-only test:

```bash
python -c 'import asyncio; from llm_interface import get_universal_llm; ns={}; exec("async def main():\n    llm = await get_universal_llm()\n    print(llm.get_model_info())\n    r = await llm.chat_completion([{\"role\": \"user\", \"content\": \"只回复OK\"}], max_tokens=8)\n    print(\"RESULT:\", r)\n    await llm.close()", globals(), ns); asyncio.run(ns["main"]())'
```

Success condition: `RESULT: OK` or an equivalent short model reply.

7. If the command fails:

- `模型 'openai' 未配置`: `ACTIVE_MODEL` and key/base URL variables are inconsistent.
- `/api/v3/chat/completions` appears in logs: request is still going through the Ark/Doubao path.
- `socks5h` proxy errors: adapter still trusts environment proxies.
- `All connection attempts failed`: verify network access and base URL; if curl works but project fails, compare `httpx` adapter settings.

8. Restart backend after config/code changes:

```bash
bash run_dev.sh --port 8012
```

Use the same backend port in `frontend/.env`:

```env
VITE_BACKEND_URL=http://127.0.0.1:8012
```
