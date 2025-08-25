#!/usr/bin/env python3
import asyncio
from scholar_mirror_api import ScholarMirrorAPI

async def test():
    api = ScholarMirrorAPI()
    results = await api.search('machine learning', 3)
    print(f'获得 {len(results)} 篇论文')
    if results:
        for paper in results:
            print(f'- {paper.title}')
    await api.close()

if __name__ == "__main__":
    asyncio.run(test())