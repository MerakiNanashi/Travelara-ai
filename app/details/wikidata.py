import asyncio
from urllib.parse import quote

from app.schemas import POI

import httpx

WIKIDATA_API = "https://www.wikidata.org/w/api.php"

HEADERS = {
    "User-Agent": "Travelara/0.1 (your@email.com)",
    "Accept": "application/json",
}


async def enrich_selected_pois(selected_pois: list[POI]):

    qid_to_pois = {}

    for poi in selected_pois:
        qid = (poi.wiki_and_media or {}).get("wikidata")

        if qid:
            qid_to_pois.setdefault(qid, []).append(poi)

    if not qid_to_pois:
        return

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=30,
        follow_redirects=True,
    ) as client:

        qids = list(qid_to_pois.keys())

        #
        # STEP 1
        # Batch fetch Wikidata
        #

        qid_to_page = {}
        qid_to_description = {}
        qid_to_label = {}

        for i in range(0, len(qids), 50):

            batch = qids[i:i + 50]

            r = await client.get(
                WIKIDATA_API,
                params={
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(batch),
                    "props": "labels|descriptions|sitelinks",
                    "languages": "en",
                    "maxlag": 5,
                },
            )

            r.raise_for_status()

            entities = r.json()["entities"]

            for qid, entity in entities.items():

                #
                # Label
                #

                label = (
                    entity.get("labels", {})
                    .get("en", {})
                    .get("value")
                )

                if label:
                    qid_to_label[qid] = label

                #
                # Description
                #

                description = (
                    entity.get("descriptions", {})
                    .get("en", {})
                    .get("value")
                )

                if description:
                    qid_to_description[qid] = description

                #
                # Wikipedia page
                #

                sitelinks = entity.get("sitelinks", {})

                title = None
                lang = None

                # Prefer English
                if "enwiki" in sitelinks:
                    lang = "en"
                    title = sitelinks["enwiki"]["title"]

                # Otherwise use first available Wikipedia
                else:
                    for site, info in sitelinks.items():
                        if site.endswith("wiki"):
                            lang = site[:-4]  # jawiki -> ja
                            title = info["title"]
                            break

                if title:
                    qid_to_page[qid] = (lang, title)

        #
        # STEP 2
        # Fetch Wikipedia summaries
        #

        sem = asyncio.Semaphore(5)

        async def fetch_summary(qid: str, lang: str, title: str):

            async with sem:

                url = (
                    f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                    + quote(title)
                )

                r = await client.get(url)

                if r.status_code != 200:
                    return qid, None, None

                data = r.json()

                image_url = (
                    data.get("thumbnail", {}).get("source")
                    or data.get("originalimage", {}).get("source")
                )

                summary = (
                    data.get("extract")
                    or data.get("description")
                    or data.get("title")
                )

                return qid, summary, image_url

        tasks = [
            fetch_summary(qid, lang, title)
            for qid, (lang, title) in qid_to_page.items()
        ]

        summaries = await asyncio.gather(*tasks)

        summary_map = {
            qid: (summary, img)
            for qid, summary, img in summaries
            if summary
        }

        #
        # STEP 3
        # Populate POIs
        #

        for qid, pois in qid_to_pois.items():

            summary, img = summary_map.get(qid, (None, None))

            #
            # Fallback 1: Wikidata description
            #

            if not summary:
                summary = qid_to_description.get(qid)

            #
            # Fallback 2: Deterministic description from POI metadata
            #

            if not summary:

                poi = pois[0]

                label = qid_to_label.get(qid) or poi.name

                category = getattr(poi, "category", None)

                city = None
                country = None

                if getattr(poi, "address", None):
                    city = getattr(poi.address, "city", None)
                    country = getattr(poi.address, "country", None)

                parts = [label]

                if category:
                    parts.append(f"is a {category.lower()}")

                location = ", ".join(
                    x for x in [city, country] if x
                )

                if location:
                    parts.append(f"located in {location}")

                summary = " ".join(parts)

            #
            # Final fallback
            #

            if not summary:
                summary = pois[0].name

            en_name = qid_to_label.get(qid)

            for poi in pois:
                poi.wiki_enrichment = {
                    "en_name": en_name,
                    "description": summary,
                    "img_url": img,
                }