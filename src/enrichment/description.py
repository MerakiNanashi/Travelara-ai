from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.shared.schemas import POI, _WikipediaConfig, WikiEntity

from src.shared.connections.wikidata import batch_wikidata
from src.shared.connections.wikipedia import batch_wikisummary

class Enrichment:

    def __init__(
        self,
        pois: list[POI],
        *,
        wikidata_url: str,
        config: _WikipediaConfig,
    ):
        self.pois = pois
        self.wikidata_url = wikidata_url
        self.config = config

    async def enrich(self) -> list[POI]:

        poi_map = self._group_pois()

        if not poi_map:
            return self.pois

        entities = await batch_wikidata(
            qids=poi_map.keys(),
            api_url=self.wikidata_url,
            config=self.config,
        )

        parsed = self._parse_entities(entities)

        pages = {
            qid: (entity.lang, entity.title)
            for qid, entity in parsed.items()
            if entity.lang and entity.title
        }

        summaries = await batch_wikisummary(
            pages,
            config=self.config,
        )

        self._populate(
            poi_map=poi_map,
            entities=parsed,
            summaries=summaries,
        )

        return self.pois

    def _group_pois(self) -> dict[str, list[POI]]:

        grouped = defaultdict(list)

        for poi in self.pois:
            qid = (poi.wiki_and_media or {}).get("wikidata")
            if qid:
                grouped[qid].append(poi)

        return grouped

    def _parse_entities(
        self,
        entities: dict[str, dict],
    ) -> dict[str, WikiEntity]:

        preferred_site = f"{self.config.language}wiki"

        parsed: dict[str, WikiEntity] = {}

        for qid, entity in entities.items():

            labels = entity.get("labels", {})
            descriptions = entity.get("descriptions", {})
            sitelinks = entity.get("sitelinks", {})

            info = WikiEntity(
                label=labels.get(self.config.language, {}).get("value"),
                description=descriptions.get(
                    self.config.language, {}
                ).get("value"),
            )

            if preferred_site in sitelinks:

                info.lang = self.config.language
                info.title = sitelinks[preferred_site]["title"]

            else:

                for site, value in sitelinks.items():
                    if site.endswith("wiki"):
                        info.lang = site[:-4]
                        info.title = value["title"]
                        break

            parsed[qid] = info

        return parsed

    def _metadata_description(
        self,
        poi: POI,
        label: str | None,
    ) -> str:

        parts = [label or poi.name]

        if poi.category:
            parts.append(f"is a {poi.category.lower()}")

        if getattr(poi, "address", None):

            location = ", ".join(
                filter(
                    None,
                    [
                        getattr(poi.address, "city", None),
                        getattr(poi.address, "country", None),
                    ],
                )
            )

            if location:
                parts.append(f"located in {location}")

        return " ".join(parts)

    def _populate(
        self,
        *,
        poi_map: dict[str, list[POI]],
        entities: dict[str, WikiEntity],
        summaries: dict[str, tuple[str | None, str | None]],
    ) -> None:

        for qid, pois in poi_map.items():

            entity = entities.get(qid, WikiEntity())

            wiki_summary, image = summaries.get(
                qid,
                (None, None),
            )

            summary = (
                wiki_summary
                or entity.description
                or self._metadata_description(
                    pois[0],
                    entity.label,
                )
                or pois[0].name
            )

            enrichment = {
                "en_name": entity.label,
                "description": summary,
                "img_url": image,
            }

            for poi in pois:
                poi.wiki_enrichment = enrichment