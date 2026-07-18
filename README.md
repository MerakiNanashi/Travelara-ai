# Travelara

**Adaptive constraint-aware travel planning pipeline.**
Typed, immutable stage chain — intent extraction → retrieval → scoring/clustering/pruning → enrichment → semantic re-ranking → candidate pool building → itinerary assembly.
LLM is used only for intent extraction; all planning, ranking, and selection logic downstream is deterministic.

---

## Setup

```bash
# 1. Install dependencies (uv-managed project)
uv sync

# 2. Configure API keys
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY     → https://aistudio.google.com/app/apikey
#   GEOAPIFY_API_KEY   → https://www.geoapify.com/ (free tier: 3000 req/day)
#   FOURSQUARE_API_KEY → https://developer.foursquare.com/ (free tier available)

# 3. Configure geocoding data
#    Download cities500.txt and IN.txt from https://download.geonames.org/export/dump/
#    Place them under data/latlon/

# 4. Run the API
uvicorn main:app --reload --port 8000

# 5. Open the frontend
start index.html   # or open index.html in your browser
```

Interactive docs: http://localhost:8000/docs

---

## Pipeline Architecture

The pipeline is a chain of typed `Stage` objects, each consuming and returning an immutable `PlanningState`. Each stage reports timing/counts to a per-run `Debugger` instance at its boundary via `@stage`.

```
PlanningRequest (raw NL query)
    │
    ▼
[1] ExtractorStage ── intent_extraction ─────────────────────────────
    │  Gemini (active: gemini-3.1-flash-lite, fallback: gemini-2.5-flash-lite)
    │  raw NL query → StructuredIntent (destination, days, budget,
    │  stay_location, preferences, constraints)
    │  handles clarification turns via ConversationContext
    ▼  state.intent
[2] RetrievalStage ── retrieval ──────────────────────────────────────
    │  Geoapify + Foursquare providers, fetched concurrently
    │  GeoNames-based fuzzy lat/lon resolution
    │  deduplicate() collapses provider overlap → discarded_dups tracked
    ▼  state.raw_pois
[3] PruningStage ── scoring · clustering · pruning ───────────────────
    │  Filter        : TF-IDF utility scoring (name/source/tag/semantic/
    │                  wiki/link weighted sum → sigmoid → overall)
    │  Clustering     : HDBSCAN spatial clustering → cluster_map
    │  Pruning        : per-cluster survival_score (sum/max/p90/diversity)
    │                  bottom percentile pruned, top-N protected
    ▼  state.scored_pois, state.clustered_pois, state.selected_pois
[4] EnrichmentStage ── enrichment ─────────────────────────────────────
    │  async Wikidata/Wikipedia batch fetch (rate-limited, retried)
    │  QID-bearing POIs only → en_name, description, img_url
    ▼  state.enriched_pois
[5] RerankerStage ── reranker ──────────────────────────────────────────
    │  SemanticScorer : BGE-M3 embeddings, cosine sim vs. user profile
    │                   → anchor.semantic
    │  AnchorScorer   : representative / expansion / connectivity /
    │                   importance → anchor.overall, cluster_map_idtop
    ▼  state.ranked_pois
[6] BuildStage ── builder ──────────────────────────────────────────────
    │  CandidatePoolBuilder: per-day candidate pool expansion
    │  target_per_day, expansion_radius_m, diversity_weight,
    │  distance_decay_m from config
    ▼  state.artifacts.candidate_selection, state.candidate_pois
[7] PlanStage ── planner ────────────────────────────────────────────────
    │  candidate_pool_to_itinerary(): schedule feasibility under time
    │  windows, sequential arrival/departure times, travel time estimate
    ▼
Itinerary (DayPlan[] · ItineraryScore · ItineraryMetadata · anchors[])
```

Each stage is orchestrated by `src/orchestrator.py`, which threads a single `PlanningState` through the chain, with `PipelineMetadata` tracking `current_stage` / `completed_stages` / `failed_stages` for resumability.

---

## Typed State Model

`POI` objects move through a strict progression, enforced by adapters rather than ad-hoc field access:

```
POI → ScoredPOI → ClusteredPOI → AnchorPOI → PlannedPOI
```

- **Immutability**: state transitions use `model_copy(update=...)`, never in-place mutation, so no stage can silently corrupt a shared object mid-pipeline.
- **Adapters** (`src/shared/adapters/`) are the sole layer permitted to reach into nested schema internals (`UtilityScore`, `AnchorScore`, `ClusterScore`) — stages never touch these fields directly.
- **`PlanningState`** (`src/shared/schemas/state.py`) is the single mutable-in-name-only object threaded through the pipeline, holding per-stage POI lists (`raw_pois`, `scored_pois`, `clustered_pois`, `selected_pois`, `enriched_pois`, `ranked_pois`, `candidate_pois`), `PipelineArtifacts` (cluster maps, selected clusters, candidate selection), and `PipelineMetadata`.
- **Per-run `Debugger`** — no global singleton; each pipeline run gets its own instance, reporting `StageReport`s at stage boundaries only.
- **Externalized config** — `_ClusteringConfig`, `_FilterConfig`, `_PruningConfig`, `_WikipediaConfig`, `_ExtractorConfig` in `config_schema.py`, loaded per-stage from `config.yaml` (no hardcoded magic numbers in stage logic).

---

## Key Design Decisions

- **LLM scope is extraction only** — Gemini is never the planner; all ranking, clustering, and selection downstream is deterministic and inspectable.
- **Two-stage semantic scoring** — TF-IDF at filter time (cheap, no GPU, runs before enrichment), BGE-M3 post-enrichment (richer signal, runs on enriched text). These are tracked as separate fields (`utility.semantic` vs. `anchor.semantic`) to avoid the score-collision bug where one silently overwrote the other.
- **Cascade ranking under sequential enrichment cost** — since POIs aren't fully attributed until after an expensive enrichment call, ranking proceeds cheap-signal → geo-cluster → tentative route on unenriched estimates → targeted enrichment → verify/repair, rather than assuming full attribution up front (the standard TOPTW assumption, which doesn't hold here).
- **HDBSCAN clustering** — density-aware, no fixed cluster count, avoids orphaned POIs.
- **Shannon diversity term** in cluster survival scoring — prevents large single-category clusters from crowding out mixed ones.
- **Typed stage chain + immutable `model_copy` updates** — replaces the earlier mutable shared `POI` object pattern that let fields accumulate without stage-level enforcement.
- **Adapter-layer discipline** — prevents the parallel schema drift and silent Pydantic field-name mismatches (e.g. `name_score`/`raw_score` vs. `name`/`raw`) that previously went undetected.

---

## Project Structure

```
travelara-cd-v2/
├── data/
│   ├── latlon/                          # GeoNames data (cities500.txt, IN.txt)
│   ├── prompt_version/                  # versioned extractor prompts
│   └── providers_taxamony/              # category → provider ID mappings
├── src/
│   ├── builder/
│   │   └── builder.py                   # CandidatePoolBuilder (stage 6)
│   ├── enrichment/
│   │   └── description.py               # Wikidata/Wikipedia async enrichment
│   ├── extractor/
│   │   ├── extractor_class.py           # Gemini NL → StructuredIntent
│   │   ├── internals.py
│   │   └── prompt.py
│   ├── planner/
│   │   └── plan.py                      # candidate_pool_to_itinerary
│   ├── pruning/
│   │   ├── cluster.py                   # HDBSCAN clustering
│   │   ├── filter.py                    # TF-IDF utility scoring
│   │   └── prune.py                     # percentile pruning + survival score
│   ├── reranker/
│   │   ├── anchor.py                    # AnchorScorer
│   │   └── semantic.py                  # BGE-M3 SemanticScorer
│   ├── retrieval/
│   │   ├── externals.py
│   │   ├── foursquare_provider.py
│   │   ├── geoapify_provider.py
│   │   ├── internals.py
│   │   └── provider_class.py            # BaseProvider ABC
│   ├── shared/
│   │   ├── adapters/                    # exclusive access layer to schema internals
│   │   │   ├── intent_adapter.py
│   │   │   └── poi_adapter.py
│   │   ├── config/
│   │   │   ├── config.py
│   │   │   └── config.yaml
│   │   ├── connections/                 # GeminiClient / WikidataClient protocols
│   │   │   ├── gemini.py
│   │   │   ├── wikidata.py
│   │   │   └── wikipedia.py
│   │   ├── schemas/                     # all Pydantic models
│   │   │   ├── candidate.py             # POI, Cluster, WikiEnrichment
│   │   │   ├── config_schema.py         # per-stage dataclass configs
│   │   │   ├── debugger.py              # StageReport
│   │   │   ├── enums.py                 # Stage, BudgetLevel, PreferenceCategory, ...
│   │   │   ├── intent.py                # StructuredIntent, Preference, Constraints
│   │   │   ├── itinerary.py             # Itinerary, DayPlan, ItineraryStop
│   │   │   ├── request.py               # PlanningRequest
│   │   │   ├── response.py              # PlanResponse
│   │   │   ├── scores.py                # UtilityScore, AnchorScore, ClusterScore
│   │   │   ├── stage.py                 # StageContext, ClusterSelectionResult
│   │   │   └── state.py                 # PlanningState, PipelineArtifacts/Metadata
│   │   └── utils/
│   │       ├── calcs.py
│   │       ├── display.py
│   │       ├── errors.py
│   │       ├── intialize.py
│   │       ├── runresumer.py
│   │       ├── save.py
│   │       └── snapshot.py
│   ├── stages/                          # one file per pipeline stage
│   │   ├── BaseStage.py
│   │   ├── ExtractorStage.py            # [1] intent_extraction
│   │   ├── RetrievalStage.py            # [2] retrieval
│   │   ├── PruningStage.py              # [3] scoring/clustering/pruning
│   │   ├── EnrichmentStage.py           # [4] enrichment
│   │   ├── RerankerStage.py             # [5] reranker
│   │   ├── BuildStage.py                # [6] candidate pool build
│   │   └── PlanStage.py                 # [7] itinerary planning
│   └── orchestrator.py                  # threads PlanningState through the stage chain
├── tests/
│   ├── cluster_tests/
│   ├── retreival_tests/
│   ├── config.py
│   ├── extractor_test.py
│   └── schema_test.py
├── index.html                           # frontend (Waypoint UI)
├── main.py                              # FastAPI app entrypoint
├── ISSUES.md
├── Notes.md
├── pyproject.toml
└── uv.lock
```

---

## API Endpoints

### `POST /plan/`
Full pipeline: natural language query → structured intent → scored, clustered, enriched, ranked itinerary.

```bash
curl -X POST http://localhost:8000/plan/ \
  -H "Content-Type: application/json" \
  -d '{"query": "5-day Tokyo trip, love museums and food, moderate budget, staying near Shinjuku"}'
```

**Response:**
```json
{
  "success": true,
  "itinerary": {
    "intent": { "destination": { "value": "Tokyo" }, "days": { "value": 5 }, "...": "..." },
    "days": [
      {
        "day": 1,
        "date": "2026-09-12",
        "theme": "Museums & exploration",
        "total_walking_km": 3.2,
        "total_cost_usd": 0.0,
        "stops": [
          {
            "poi": { "name": "Tokyo National Museum", "category": "museums", "...": "..." },
            "arrival_time": "09:00",
            "departure_time": "10:30",
            "travel_time_to_next_minutes": 12,
            "travel_mode": "walking"
          }
        ]
      }
    ],
    "score": {
      "total": 0.855,
      "preference_alignment": 0.626,
      "spatial_efficiency": 0.82,
      "temporal_feasibility": 1.0,
      "diversity": 0.75
    },
    "metadata": {
      "total_pois_retrieved": 25,
      "clusters_found": 5,
      "anchors_selected": 5
    },
    "anchors": [ "..." ]
  }
}
```

### `GET /`
Health check — service name, version, status.

### `GET /health`
Returns which API keys are configured (`gemini`, `geoapify`, `foursquare`).