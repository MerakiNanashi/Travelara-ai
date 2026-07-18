import httpx
from collections.abc import Iterable
from src.shared.schemas import _WikipediaConfig

async def batch_wikidata(*,
                          qids: Iterable[str],
                          api_url: str,
                          config: _WikipediaConfig,
                          ) -> dict[str, dict]:
    
    headers = {
    "User-Agent": config.user_agent,
    "Accept": config.accept
    }

    
    qids = list(qids)
    if not qids:
        return {}

    entities: dict[str, dict] = {}

    async with httpx.AsyncClient(
        headers=headers,
        timeout=config.timeout,
        follow_redirects=config.follow_redirects,
    ) as client:

        for i in range(0, len(qids), config.batch_size):
            batch = qids[i : i + config.batch_size]

            response = await client.get(
                api_url,
                params={
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(batch),
                    "props": "labels|descriptions|sitelinks",
                    "languages": config.language,
                    "maxlag": config.maxlag,
                },
            )
            response.raise_for_status()
            entities.update(
                response.json()["entities"])

    return entities
