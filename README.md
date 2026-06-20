# Travelara

**Adaptive constraint-aware travel planning API.**  
Hierarchical graph optimization + beam search + iterative refinement.  
LLM is used only for extraction — all planning logic is deterministic.

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY    → https://aistudio.google.com/app/apikey
#   GEOAPIFY_API_KEY  → https://www.geoapify.com/ (free tier: 3000 req/day)
#   FOURSQUARE_API_KEY→ https://developer.foursquare.com/ (free tier available)

# Edit latlon_path in config.py
# Download cities500.zip & IN.zip from https://download.geonames.org/export/dump/

# latlon_path = r"/cities500.txt" # Enter the path for cities500.txt
#in_latlon_path = r"/IN.txt" # Enter the path for IN.txt

# 3. Run

uvicorn main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

---

## API Endpoints

### `POST /plan/`
Full pipeline: NL query → structured intent → POI retrieval → optimized itinerary.

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
    "intent": { "destination": "Tokyo", "days": 5, ... },
    "days": [
      {
        "day": 1,
        "theme": "Museums & exploration",
        "stops": [
          {
            "poi": { "name": "Tokyo National Museum", ... },
            "arrival_time": "09:00",
            "departure_time": "11:00",
            "travel_time_to_next_minutes": 12
          }
        ],
        "total_walking_km": 3.2,
        "total_cost_usd": 45.0
      }
    ],
    "score": {
      "total": 0.72,
      "preference_alignment": 0.85,
      "spatial_efficiency": 0.78,
      "diversity": 0.60
    },
    "anchors": [ ... ]
  }
}
```

---

### `POST /plan/extract-intent`
Only run the Gemini extraction step. Useful for debugging / previewing parsed constraints.

```bash
curl -X POST http://localhost:8000/plan/extract-intent \
  -H "Content-Type: application/json" \
  -d '{"query": "3 days in Paris, art lover, tight budget, avoid crowds"}'
```

---

### `POST /plan/retrieve-pois`
Retrieve raw candidate POIs without planning. Useful for browsing what's available.

```bash
curl -X POST http://localhost:8000/plan/retrieve-pois \
  -H "Content-Type: application/json" \
  -d '{"query": "weekend in Kyoto, temples and food"}'
```

---

### `GET /health`
Check which API keys are configured.

---

## Architecture

```
User Query (NL)
    ↓
[Gemini 2.5 Flash Lite] → StructuredIntent (JSON)
    ↓
[Geoapify + Foursquare] → Candidate POIs
    ↓
[Scoring] → Utility scores (W_n = αP + βR + γT + δC)
    ↓
[DBSCAN] → Spatial clusters
    ↓
[MMR Anchor Selection] → High-utility, geographically diverse anchors
    ↓
[Neighborhood Expansion] → Per-day local candidate sets
    ↓
[Beam Search] → Optimal daily sequences
    ↓
[Iterative Refinement] → Remove backtracking, improve coherence
    ↓
Itinerary + Score
```

## Key Design Decisions

- **LLM scope is extraction only** — Gemini is never the planner
- **Sparse KNN graph** (O(N log N)) instead of O(N²) dense graph
- **DBSCAN clustering** — density-aware, no fixed cluster count
- **MMR anchor selection** — balances utility + geographic diversity
- **Beam search** instead of exhaustive NP-hard traversal
- **Iterative refinement** removes backtracking after initial plan

## Project Structure

```
travelara/
├── app/
│   ├── config.py           # Settings + env vars
│   ├── schemas.py          # All Pydantic models
│   ├── plan.py             # API endpoints
│   ├── extractor.py        # Gemini NL → StructuredIntent
│   ├── retrieval.py        # Geoapify + Foursquare POI fetch
│   ├── graph.py            # KNN graph, DBSCAN, utility scoring
│   └── planner.py          # Anchors, beam search, refinement
├── main.py                 # FastAPI app + CORS
├── requirements.txt
├── .env.example
└── README.md
```

## Roadmap (from architecture docs)

- [ ] Phase 2: Full temporal graph (opening hours, crowd density, weather)
- [ ] Phase 3: RLHF feedback loop (implicit signals → preference learning)
- [ ] Phase 4: Real-time replanning (closures, weather, fatigue)
- [ ] OR-Tools integration for hard constraint optimization
- [ ] PostgreSQL + PostGIS for persistent POI storage
- [ ] FAISS/HNSW for semantic vector retrieval
