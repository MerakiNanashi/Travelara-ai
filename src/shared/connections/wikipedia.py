from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from aiolimiter import AsyncLimiter

from src.shared.schemas import _WikipediaConfig


async def wikisummary(
    title: str,
    *,
    config: _WikipediaConfig,
    client: httpx.AsyncClient,
    limiter: AsyncLimiter,
    semaphore: asyncio.Semaphore,
    lang: str | None = None,
) -> tuple[str | None, str | None]:

    lang = lang or config.language

    async with semaphore:
        async with limiter:

            url = (
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                + quote(title)
            )

            response = await client.get(url)

            if response.status_code != 200:
                return None, None

            data = response.json()

            summary = (
                data.get("extract")
                or data.get("description")
                or data.get("title")
            )

            image = (
                data.get("thumbnail", {}).get("source")
                or data.get("originalimage", {}).get("source")
            )

            return summary, image


async def batch_wikisummary(
    pages: dict[str, tuple[str, str]],
    *,
    config: _WikipediaConfig,
) -> dict[str, tuple[str | None, str |None]]:

    limiter = AsyncLimiter(*config.rate_limit)
    semaphore = asyncio.Semaphore(config.concurrency)

    headers = {
        "User-Agent": config.user_agent,
        "Accept": config.accept,
    }

    async with httpx.AsyncClient(
        headers=headers,
        timeout=config.timeout,
        follow_redirects=config.follow_redirects,
    ) as client:

        async def worker(
            qid: str,
            lang: str,
            title: str,
        ):
            summary, image = await wikisummary(
                title,
                lang=lang,
                config=config,
                client=client,
                limiter=limiter,
                semaphore=semaphore,
            )

            return qid, summary, image

        tasks = [
            worker(qid, lang, title)
            for qid, (lang, title) in pages.items()
        ]

        results = await asyncio.gather(*tasks)

    return {
        qid: (summary, image)
        for qid, summary, image in results
    }