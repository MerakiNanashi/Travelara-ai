from app.schemas import PlannedPOI


def display_name(poi: PlannedPOI) -> str:
    if poi.wiki_enrichment and poi.wiki_enrichment.get("en_name"):
        en = poi.wiki_enrichment["en_name"]
        if en.strip():
            return en.strip()
    return poi.name


def utility_raw(poi: PlannedPOI) -> float:
    return poi.utility.raw


def anchor_overall(poi: PlannedPOI) -> float:
    return poi.anchor.overall


def short_description(poi: PlannedPOI, max_len: int = 90) -> str | None:
    if not poi.wiki_enrichment:
        return None
    desc = poi.wiki_enrichment.get("description")
    if not desc:
        return None
    return desc if len(desc) <= max_len else desc[: max_len - 3] + "..."