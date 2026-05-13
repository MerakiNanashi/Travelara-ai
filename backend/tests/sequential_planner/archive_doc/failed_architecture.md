# Failed Architecture — Sequential Slot-Based Itinerary Optimization

## Status

Rejected for V1 due to:
- excessive computational complexity
- unstable sequential dependencies
- impractical iterative optimization
- weak global itinerary coherence

Implementation completed until:
- NLU/NLP → structured itinerary extraction
- POI retrieval
- preliminary filtering

Some failure points below were directly observed during implementation, while others were architectural deductions based on projected scaling behavior.

---

# Proposed Pipeline

```text
User Input
    ↓
NLU/NLP (Gemini 2.5 Flash Lite)
    ↓
Structured JSON
    ↓
POI Retrieval
    ↓
Budget Filtering
    ↓
Sequential Haversine + Population Density
    ↓
Candidate Generator
    ↓
LLM Ranker
    ↓
Final Itinerary
```

---

# Core Problem

The architecture would attempt to optimize the itinerary sequentially at slot level.

Example:

```text
slot_3 depends on slot_2
slot_2 depends on slot_1
```

Distance calculations and ranking scores would therefore become dependent on uncertain previous selections.

This would likely produce unstable feature generation and noisy candidate scoring.

---

# Main Failure Points

## 1. Recursive Sequential Dependency

Haversine distance calculation would require knowledge of the previously selected POI.

This would create cascading dependencies across slots and days.

A candidate could not be reliably scored without partially knowing future itinerary structure.

---

## 2. O(N²) Repeated Computation

The architecture would require repeated pairwise spatial calculations across candidates.

Approximate behavior:

```text
For x days and y slots:

O((x * y)²)
```

Additionally, recalculation would likely occur after every slot selection:

```text
calculate distance
→ rank candidates
→ select candidate
→ recompute downstream distances
→ rerank
```

This would become computationally impractical as:
- POI count increases
- constraints increase
- itinerary flexibility increases

---

## 3. Lack of Stable Geographic Anchors

The system would not initially define:
- anchor POIs
- regional boundaries
- day-level geographic direction

Without anchors:
- routing direction becomes ambiguous
- daily clustering becomes unstable
- haversine features lose meaning

The architecture would require deciding:
- radius
- progression direction
- geographic grouping

before the itinerary structure itself is stable.

---

## 4. Feature Noise Injection

The model would receive spatial features derived from uncertain itinerary states.

Example:

```text
distance(candidate_A)
```

would change depending on:
- previous slot selection
- future routing
- candidate permutations

This would likely produce:
- unstable ranking signals
- weak learning consistency
- noisy optimization behavior

---

## 5. Local Optimization vs Global Coherence

The architecture would optimize slots locally instead of optimizing the itinerary holistically.

A locally optimal POI could negatively affect:
- future travel time
- fatigue balance
- opening-hour feasibility
- day coherence
- overall experience flow

This would likely cause globally weak itineraries despite strong individual slot scores.

---

# Architectural Insight

The implementation suggested that itinerary generation should not be treated primarily as:
- sequential recommendation
- slot ranking
- autoregressive generation

It more closely resembles:
- constrained planning
- route optimization
- spatial-temporal scheduling
- multi-objective optimization

The itinerary quality would emerge globally rather than at slot level.

---

# Likely Better Direction

```text
Constraint Extraction
    ↓
Anchor Extraction
    ↓
POI Retrieval
    ↓
Geographic Clustering
    ↓
Feasible Day Construction
    ↓
Route Optimization
    ↓
LLM Explanation Layer
```

Key difference:
- routing would happen after clustering
- optimization would happen after feasibility filtering
- LLMs would not act as primary optimizers

---

# Additional Issues To Investigate

Potential future concerns not fully tested yet:

- combinatorial explosion with dynamic replanning
- uncertainty propagation across itinerary states
- real-world travel time inaccuracies
- opening-hour conflicts during reranking
- experience-quality optimization complexity
- balancing exploration vs efficiency
- multi-user/group preference conflicts
- stochastic human behavior and delays

---

# Conclusion

The architecture would likely fail because:
- routing dependencies would emerge too early
- slot-level optimization would create unstable global behavior
- repeated spatial recomputation would scale poorly
- geographic coherence would lack anchor constraints

The implementation would still provide important insights:

- itinerary optimization is globally coupled
- local ranking is insufficient
- routing requires stable anchors
- feasibility filtering should precede route optimization
- experience quality should be treated as a first-class objective