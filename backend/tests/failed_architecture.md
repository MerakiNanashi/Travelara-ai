# Failed Architecture — Sequential Slot-Based Itinerary Optimization

---

# Status

This architecture was rejected during early-stage system design and partial implementation because the optimization model itself was fundamentally unstable.

The original approach attempted to construct itineraries sequentially by filling itinerary slots one at a time while continuously recalculating spatial and ranking features after every selection.

Although parts of the system worked independently, the overall architecture failed because itinerary quality is not a locally decomposable problem.

The implementation reached the following stages successfully:

- Natural language understanding
- Structured itinerary extraction
- POI retrieval
- Preliminary filtering

However, the optimization layer exposed multiple architectural contradictions that made the approach computationally expensive, unstable, and difficult to scale.

# Original Objective

The original system did not attempt a purely greedy:

```text
best slot
→ best next slot
→ best day
→ best itinerary
```

style optimization.

Instead, the architecture attempted to combine:
- candidate generation
- heuristic ranking
- LLM reasoning
- local + global itinerary evaluation

inside a sequential iterative pipeline.

The intended idea was:

```text
Generate candidate POIs
    ↓
Rank top-K candidates per slot
    ↓
Pass candidates to LLM ranker
    ↓
LLM reasons about:
    - local fit
    - global itinerary fit
    - pacing
    - coherence
    - routing quality
    ↓
Select candidate
    ↓
Recompute downstream state
```

The architecture therefore attempted to partially incorporate global reasoning rather than relying entirely on greedy slot selection.

However, the system still failed because the entire downstream pipeline depended on an unstable candidate generator whose own inputs depended on uncertain future itinerary states.

---

# System Modules

---

## 1. NLU / NLP Layer

### Purpose

The Natural Language Understanding layer converted free-form user queries into structured constraints that downstream systems could process.

Example input:

```text
I want a 5-day Tokyo itinerary focused on food, anime culture, and nightlife with a medium budget.
```

Example output:

```json
{
  "destination": "Tokyo",
  "days": 5,
  "budget": "medium",
  "preferences": [
    "food",
    "anime",
    "nightlife"
  ],
  "itinerary_structure":[
     ...
  ]
}
```

---

### Responsibilities

The module extracted:

- trip duration
- destinations
- budget level
- travel style
- interests
- pacing preferences
- activity preferences
- itinerary skeleton

This module itself was relatively stable and was not the primary failure point.

---

## 2. POI Retrieval Layer

### Purpose

The POI retrieval system fetched candidate attractions, restaurants, landmarks, and experiences from external databases.

Example outputs:

```text
Shibuya Sky
Akihabara
Senso-ji Temple
Tsukiji Market
Golden Gai
```

---

### Responsibilities

The system attempted to retrieve:

- geographically relevant POIs
- preference-aligned POIs
- budget-compatible POIs
- operationally feasible POIs

---

### Early Filtering

Basic filtering removed:

- permanently closed places
- out-of-budget locations
- low-quality POIs
- irrelevant categories

This stage reduced search space before optimization.

---

## 3. Sequential Candidate Generator

### Purpose

The candidate generator attempted to fill itinerary slots sequentially.

Example:

```text
Day 1:
  Slot 1 → breakfast
  Slot 2 → sightseeing
  Slot 3 → lunch
  Slot 4 → activity
```

Each slot would generate candidate POIs based on:

- previous slot selection
- geographic distance
- user preferences
- estimated travel time

---

### Proposed Algorithm

The architecture roughly followed this pattern:

```python
for day in days:
    for slot in slots:

        candidates = retrieve_candidates()

        for candidate in candidates:
            score(candidate)

        best_candidate = rank(candidates)

        select(best_candidate)

        recompute_downstream_features()
```

This design appeared reasonable initially but introduced major hidden dependencies.

---

# Candidate Generator Architecture

The candidate generator was intended to:
- retrieve geographically relevant POIs
- rank POIs heuristically
- produce top-K candidates for LLM evaluation

The LLM would then act as a higher-level reasoning layer capable of evaluating:
- local slot quality
- itinerary coherence
- experiential flow
- travel efficiency
- pacing balance

Approximate pipeline:

```text
Candidate Retrieval
    ↓
Spatial Filtering
    ↓
Distance Scoring
    ↓
Heuristic Ranking
    ↓
Top-K Candidate Selection
    ↓
LLM Reasoning Layer
    ↓
Final Slot Selection
```

---


## Why The Architecture Failed

The issue was that:

```
The downstream pipeline relied on the candidate generator,
while the candidate generator itself relied on uncertain downstream selections
```

The candidate generator itself relied on:
- previous slot selections
- projected routing direction
- geographic progression
- downstream feasibility assumptions

while those same downstream states were still unresolved.

This created a recursive dependency loop.

Example:

```text
Candidate score for Slot_4
depends on:

- Slot_3 selection
- projected Slot_5 direction
- expected regional flow
- future travel feasibility
```

But:
- Slot_3 was not fully stable
- Slot_5 did not yet exist
- regional clustering had not converged
- routing structure was still evolving

As a result:
- candidate generation became unstable
- ranking signals became noisy
- LLM reasoning operated on shifting search spaces

---

# 1. Recursive Dependency Loop

The architecture effectively behaved like:

```text
candidate_generator(slot_n)
    depends on selected(slot_n-1)

selected(slot_n-1)
    depends on LLM_ranking(topK_candidates)

topK_candidates
    depends on downstream feasibility

downstream feasibility
    depends on future slot selections
```

This created circular optimization dependencies.

The system continuously attempted to optimize against partially unresolved future states.

---

## Consequences

The LLM layer itself was not necessarily the problem.

The actual issue was that the LLM only received:
- candidates generated upstream
- spatial features computed upstream
- ranking signals computed upstream

If the candidate generator itself became unstable:
- the LLM could only reason over unstable search spaces
- globally strong solutions might never appear in top-K
- candidate diversity could collapse prematurely

This meant:
- poor upstream candidate generation permanently constrained downstream reasoning quality

---

# 3. Spatial Features

The architecture relied heavily on geographic scoring features such as:

- haversine distance
- neighborhood density
- regional progression
- travel duration

These features were intended to improve geographic coherence.

## Consequences

Spatial features only remain meaningful if itinerary anchors are stable.

However, the system attempted to calculate spatial features before stable geographic structure existed.

Example:

```text
distance(candidate_A)
```

has no stable meaning unless:

- previous POI is fixed
- routing direction is fixed
- day cluster is fixed

Since those values changed continuously during optimization, the features themselves became unstable.

---

# 2. Scaling Problem

As:

- POI count increased
- itinerary length increased
- constraints increased

the recomputation cost grew rapidly.

Approximate complexity:

```text
O((days × slots)²)
```

Realistically, the effective complexity would become even worse because:

- reranking occurred repeatedly
- future states changed dynamically
- candidate neighborhoods shifted continuously

---

## Consequences

This produced:

- expensive reranking loops
- unstable search behavior
- high latency
- computational inefficiency

The architecture became impractical for large-scale itinerary generation.

---

# 3. Hidden Failure Mode

This introduced a dangerous hidden bottleneck:

```text
Candidate Generator
    becomes the true optimizer
```

even though the architecture appeared LLM-driven.

Because:
- the LLM only reasoned over pre-filtered candidates
- candidate pruning happened earlier
- search-space reduction occurred before reasoning

the actual optimization quality became heavily dependent on:
- candidate stability
- ranking consistency
- geographic coherence during generation

Once unstable candidates entered the pipeline:
- downstream reasoning quality degraded immediately

---

## Example Failure Scenario

Suppose the system generates:

```text
Slot 1:
    Tokyo Station

Slot 2:
    Candidate Set:
        - Akihabara
        - Shibuya
        - Asakusa
```

The ranking of Slot 2 candidates may depend on assumptions about:
- where Slot 3 will occur
- regional flow direction
- future restaurant placement
- evening/nightlife clustering

But those future states are unresolved.

So:
- the generator produces unstable rankings
- different downstream assumptions produce different candidate sets
- LLM reasoning becomes inconsistent

The system therefore oscillates between partially conflicting itinerary structures.

---

## Consequence

The architecture unintentionally created:

```text
A globally coupled optimization problem
inside a sequential candidate pipeline.
```

This is the core contradiction that caused the architecture to fail.

The system attempted:
- sequential decomposition

on a problem that fundamentally required:
- simultaneous global optimization

---

# Final Insight

The key realization was:

```text
Local and global optimization cannot be separated cleanly.
```

Candidate generation itself must already understand:
- global geographic structure
- regional anchors
- temporal feasibility
- route progression
- pacing constraints

Otherwise:
- the generated candidate space becomes unstable
- downstream ranking becomes noisy
- LLM reasoning loses reliability
- itinerary quality collapses globally