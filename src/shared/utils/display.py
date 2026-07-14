from app.schemas import AnchorPOI
# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _display_name(poi: AnchorPOI) -> str:
    """Return the English Wikidata label when available, else the provider name."""
    if poi.wiki_enrichment:
        en = poi.wiki_enrichment.en_name
        if en and en.strip():
            return en.strip()
    return poi.name


def print_itinerary(candidate_pool: list[dict]) -> None:
    total_pois = sum(len(day["pois"]) for day in candidate_pool)
    print(f"\n{'═' * 60}")
    print(f"  ITINERARY  —  {len(candidate_pool)} days  |  {total_pois} places")
    print(f"{'═' * 60}")

    for i, day in enumerate(candidate_pool, 1):
        anchor     = day["anchor"]
        cluster    = day["cluster"]
        pois       = day["pois"]
        score      = cluster["survival_score"]
        anchor_name = _display_name(anchor)

        print(f"\n  Day {i}  ┃  anchor: {anchor_name}  (cluster {cluster['cluster_id']}, score {score:.3f})")
        print(f"  {'─' * 56}")

        for j, poi in enumerate(pois):
            marker   = "★" if poi.id == anchor.id else " "
            name     = _display_name(poi)
            category = poi.category
            rating   = f"  ★{poi.rating:.1f}" if poi.rating else ""
            anchor_score = f"  anchor={poi.planning.utility.overall:.3f}"
            utility  = f"  utility={poi.planning.utility.raw:.2f}" if poi.planning.utility.raw is not None else ""

            print(f"  {marker} {j+1:>2}. {name:<36} [{category}]{rating}{anchor_score}{utility}")

            if poi.wiki_enrichment and poi.wiki_enrichment.description:
                desc = poi.wiki_enrichment.description
                # Truncate long descriptions to one line
                if len(desc) > 90:
                    desc = desc[:87] + "..."
                print(f"       {desc}")

    print(f"\n{'═' * 60}\n")

