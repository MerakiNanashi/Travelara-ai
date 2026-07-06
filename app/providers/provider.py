from __future__ import annotations

from app.schemas import StructuredIntent
from app.config import latlon_path, in_latlon_path
from app.providers.foursquare_provider import FoursquareProvider
from app.providers.geoapify_provider import GeoapifyProvider
from app.providers.internals import retrieve_latlon
from app.utils.snapshot import debugger
from app.adapters import intent_adapter

PROVIDERS = {
    "GA": GeoapifyProvider(),
    "FS": FoursquareProvider(),
}


async def run_retrieval(
    source: str,
    intent: StructuredIntent,
    debug: bool = False,
):
    # Read(Intent)
    must_visit = intent_adapter.must_visit_names(intent)
    is_international = intent_adapter.is_international(intent)
    destination = intent_adapter.destination(intent)
    prefs = intent.preferences
    walking_limit = int(intent_adapter.walking_limit_km(intent))
    must_avoid = set(intent_adapter.avoid_categories(intent))

    lat, lon = retrieve_latlon(
        destination,
        latlon_path if is_international else in_latlon_path,
    )

    debugger.report("retrieval_start", {
        "provider": source,
        "destination": destination,
        "coordinates": (lat, lon),
        "preferences": [p.model_dump() for p in prefs],
    })

    radius_m = int(walking_limit or 10) * 1500

    try:
        pois = await PROVIDERS[source].retrieve(
            lat=lat,
            lon=lon,
            prefs=prefs,
            radius_m=radius_m,
            debug=debug,
        )

    except Exception as e:
        debugger.report("retrieval_error", {
            "provider": source,
            "error": str(e),
        })
        pois = []

    must_names = {m.lower() for m in must_visit}

    must_pois = [
        poi
        for poi in pois
        if any(name in poi.normalized_name for name in must_names)
    ]

    rest = [poi for poi in pois if poi not in must_pois]

    debugger.report("must_visit_filter", {
        "targets": must_visit,
        "matched": len(must_pois),
    })

    avoid_categories = {
        category.lower()
        for category in must_avoid
    }

    before = len(rest)

    rest = [
        poi
        for poi in rest
        # Direct Call - POI.Category
        if poi.category.lower() not in avoid_categories
    ]

    final_pois = must_pois + rest

    counts: dict[str, int] = {}
    for poi in final_pois:
        # Direct Call - POI.Category
        counts[poi.category] = counts.get(poi.category, 0) + 1

    debugger.report("retrieval_result", {
        "provider": source,
        "input": len(pois),
        "output": len(final_pois),
        "must_visit": len(must_pois),
        "avoid_removed": before - len(rest),
        "category_counts": counts,
    })

    return final_pois, lat, lon