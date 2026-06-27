# Travelara

**Adaptive constraint-aware travel planning API.**  
HDBSCAN spatial clustering + MMR anchor selection + diversity-aware greedy expansion.  
LLM is used only for intent extraction — all planning logic is deterministic.

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY     → https://aistudio.google.com/app/apikey
#   GEOAPIFY_API_KEY   → https://www.geoapify.com/ (free tier: 3000 req/day)
#   FOURSQUARE_API_KEY → https://developer.foursquare.com/ (free tier available)

# 3. Configure geocoding data in config.py
#    Download cities500.txt from https://download.geonames.org/export/dump/cities500.zip
#    Download IN.txt from https://download.geonames.org/export/dump/IN.zip
#
#    latlon_path    = r"path/to/cities500.txt"   # international destinations
#    in_latlon_path = r"path/to/IN.txt"          # domestic (India) destinations

# 4. Run the API
uvicorn main:app --reload --port 8000

# 5. Open the frontend
start index.html   # or open index.html in your browser
```

Interactive docs: http://localhost:8000/docs

---

## API Endpoints

### `POST /plan/`
Full pipeline: natural language query → structured intent → POI retrieval → scored, clustered itinerary.

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
    "intent": { "destination": "Tokyo", "days": 5, "stay_location": "Shinjuku", ... },
    "days": [
      {
        "day": 1,
        "date": "2026-09-12",
        "theme": "Museums & exploration",
        "total_walking_km": 3.2,
        "total_cost_usd": 0.0,
        "stops": [
          {
            "poi": { "name": "Tokyo National Museum", "category": "museums", ... },
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
    "anchors": [ ... ]
  }
}
```

---

### `GET /`
Health check — returns service name, version, and status.

### `GET /health`
Returns which API keys are configured.

```json
{
  "status": "ok",
  "apis_configured": {
    "gemini": true,
    "geoapify": true,
    "foursquare": true
  }
}
```

---

## Architecture

```
User Query (natural language)
    ↓
[Gemini 2.5 Flash Lite] ── extracts ──→ StructuredIntent
    │                                    (destination, days, preferences,
    │                                     constraints, budget, stay_location)
    ↓
[Geoapify + Foursquare] ── concurrent fetch ──→ Candidate POIs
    │                    fuzzy geocode via GeoNames
    │                    deduplicate by name
    ↓
[Filter / Utility Scoring]
    │  name_score · source_score · tag_score
    │  external_link_score · wiki_score
    │  TF-IDF semantic score vs. user profile
    │  raw_score = weighted sum → sigmoid → overall_score
    ↓
[HDBSCAN] ── spatial clustering ──→ cluster_map (poi_id → cluster_id)
    │  noise points reassigned to nearest cluster
    ↓
[Cluster Scoring + Percentile Pruning]
    │  survival_score = f(sum, max, p90, density, Shannon diversity)
    │  bottom percentile pruned; top-N POI clusters always protected
    ↓
[Wikidata Enrichment] ── async batch fetch ──→ en_name · description · img_url
    │  QID-bearing POIs only; Wikipedia summary preferred,
    │  Wikidata description as fallback
    ↓
[BGE-M3 Semantic Scoring]
    │  SentenceTransformer embeds user profile + enriched POI documents
    │  cosine similarity → anchor_score.semantic_score
    ↓
[Anchor Scoring]
    │  representative_score  – proximity to cluster centroid
    │  expansion_score       – utility-weighted neighborhood reach
    │  connectivity_score    – high-utility neighbors within 400m
    │  importance_score      – provider popularity signal
    │  overall_anchor        = weighted combination
    ↓
[Diversity-Aware Greedy Expansion]
    │  top `days` clusters selected by survival_score
    │  highest overall_anchor POI becomes day anchor
    │  slots filled greedily; _candidate_score penalises same-category repeats
    │  cross-cluster expansion if day is under quota
    ↓
[Itinerary Assembly]
    │  sequential arrival/departure times from 09:00
    │  travel time estimated from distance delta
    │  walking km accumulated per day
    ↓
Itinerary (DayPlan[] · ItineraryScore · ItineraryMetadata · anchors[])
```

---

## Key Design Decisions

- **LLM scope is extraction only** — Gemini is never the planner; all ranking and selection is deterministic
- **Two-stage semantic scoring** — TF-IDF at filter time (fast, no GPU), BGE-M3 post-enrichment (richer, on enriched text)
- **HDBSCAN clustering** — density-aware, no fixed cluster count, noise reassignment prevents orphaned POIs
- **Shannon diversity term** in cluster survival scoring — prevents large single-category clusters from crowding out mixed ones
- **Diversity-aware greedy fill** — re-scores candidates after each pick so category penalty reflects current selection, not a static sort
- **GeoNames geocoding** — offline fuzzy lat/lon resolution, no geocoding API call needed; separate file for domestic (India) destinations

---

## Project Structure

```
travelara/
├── app/
│   ├── config.py                        # Settings, env vars, data paths
│   ├── schemas.py                       # All Pydantic models
│   ├── extractor.py                     # Gemini NL → StructuredIntent
│   ├── providers/
│   │   ├── provider_class.py            # BaseProvider ABC + category mapping
│   │   ├── provider.py                  # GeoNames geocoding + retrieval orchestrator
│   │   ├── geoapify_provider.py         # Geoapify places fetch + normalize
│   │   └── foursquare_provider.py       # Foursquare places fetch + normalize
│   ├── clustering/
│   │   ├── filter.py                    # TF-IDF utility scoring (Filter class)
│   │   ├── cluster.py                   # HDBSCAN clustering + cluster scoring + pruning
│   │   └── score.py                     # BGE-M3 semantic + anchor scoring + greedy expansion
│   └── details/
│       └── wikidata.py                  # Async Wikidata + Wikipedia enrichment
├── main.py                              # FastAPI app + CORS + pipeline entrypoint
├── index.html                           # Frontend (Waypoint UI)
├── data/
│   ├── latlon/                          # GeoNames data (cities500.txt, IN.txt)
│   └── providers_taxamony/              # Category → provider ID mappings
│       ├── foursquare_categories.json
│       └── geoapify_categories.json
├── requirements.txt
└── .env
```