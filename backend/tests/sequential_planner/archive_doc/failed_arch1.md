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

---

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

# Core Failure

The primary issue was not simply:

- sequential ranking

The deeper issue was:

```text
Unstable candidate generation
```

The candidate generator itself relied on:

- previous slot selections
- projected routing direction
- geographic progression
- downstream feasibility assumptions

while those same downstream states were still unresolved.

This created recursive instability across the optimization pipeline.

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

# Why The Architecture Failed

The issue was that:

```text
The downstream pipeline relied on the candidate generator,
while the candidate generator itself relied on uncertain downstream selections.
```

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

# Recursive Dependency Loop

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

# Why This Was Architecturally Dangerous

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

# Hidden Failure Mode

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

# Example Failure Scenario

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

# Consequence

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

---

# System Modules

---

# 1. NLU / NLP Layer

## Purpose

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
  ]
}
```

---

## Responsibilities

The module extracted:

- trip duration
- destinations
- budget level
- travel style
- interests
- pacing preferences
- group size
- activity preferences

This module itself was relatively stable and was not the primary failure point.

---

# 2. POI Retrieval Layer

## Purpose

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

## Responsibilities

The system attempted to retrieve:

- geographically relevant POIs
- preference-aligned POIs
- budget-compatible POIs
- operationally feasible POIs

---

## Early Filtering

Basic filtering removed:

- permanently closed places
- out-of-budget locations
- low-quality POIs
- irrelevant categories

This stage reduced search space before optimization.

---

# 3. Sequential Candidate Generator

## Purpose

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

## Proposed Algorithm

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

# Core Architectural Failure

The architecture assumed that the itinerary could be optimized incrementally.

This assumption failed because itinerary quality is highly dependent on future states that are unknown during early slot selection.

Example:

```text
slot_3 depends on slot_2
slot_2 depends on slot_1
slot_1 indirectly affects slot_8
```

A poor early decision could:

- force inefficient routing later
- create opening-hour conflicts
- increase travel fatigue
- reduce clustering quality
- break pacing balance

This created recursive optimization instability.

---

# 4. Recursive Sequential Dependency

## Problem

The architecture created cascading dependencies across itinerary states.

Spatial scoring required knowledge of previously selected POIs.

Example:

```text
distance(candidate_A, previous_POI)
```

However:

- previous POIs were themselves uncertain
- future routing remained unknown
- downstream feasibility was unresolved

This meant candidate scoring depended on unstable itinerary states.

---

## Why This Failed

The architecture effectively attempted to solve:

```text
best(current_slot | previous_slot)
```

But the actual problem behaves more like:

```text
best(global_itinerary)
```

under constraints.

The system therefore optimized local transitions without understanding global structure.

---

## Result

This caused:

- unstable rankings
- reranking loops
- cascading recalculations
- inconsistent spatial scoring

The optimizer could not converge reliably because the state space kept changing after every selection.

---

# 5. Spatial Feature Instability

## Purpose of Spatial Features

The architecture relied heavily on geographic scoring features such as:

- haversine distance
- neighborhood density
- regional progression
- travel duration

These features were intended to improve geographic coherence.

---

## Failure Mechanism

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

## Consequences

This injected noise into:

- ranking models
- candidate scoring
- downstream optimization

The model received inconsistent signals for the same POI depending on:

- current permutation
- previous selections
- routing path

This dramatically weakened optimization reliability.

---

# 6. Lack of Geographic Anchors

## Problem

The architecture attempted routing before defining stable geographic anchors.

The system never initially established:

- regional clusters
- neighborhood boundaries
- directional progression
- anchor destinations

As a result:

- day construction became unstable
- routing direction became ambiguous
- POIs drifted geographically

---

## Example Failure

A generated day could accidentally evolve like:

```text
Morning:
    North Tokyo

Lunch:
    Central Tokyo

Evening:
    West Tokyo

Night:
    East Tokyo
```

Individually strong POIs could still create terrible routing behavior.

---

## Missing Concept

The system lacked hierarchical planning.

It attempted:

- slot optimization first
- geographic organization later

The order needed to be reversed.

---

# 7. Local Optimization vs Global Optimization

## Fundamental Contradiction

The architecture optimized:

- individual slots
- local transitions
- immediate ranking scores

But itinerary quality emerges globally.

---

## Example

A POI may score highly because:

- it matches preferences
- it is nearby
- it is popular

Yet it could still damage:

- future route efficiency
- opening-hour feasibility
- fatigue balance
- pacing
- experiential flow

---

## Illustration

Locally optimal:

```text
Best next attraction
```

Globally poor:

```text
Creates 2-hour detour later
```

This contradiction appeared repeatedly during design analysis.

---

# 8. Computational Complexity Explosion

## Original Computational Pattern

The architecture repeatedly recomputed spatial relationships after every slot selection.

Approximate structure:

```python
for slot in slots:

    for candidate in candidates:

        compute_distance()
        compute_score()

    select_candidate()

    recompute_all_downstream_states()
```

---

## Scaling Problem

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

## Practical Consequences

This produced:

- expensive reranking loops
- unstable search behavior
- high latency
- computational inefficiency

The architecture became impractical for large-scale itinerary generation.

---

# 9. Hidden State Explosion

## Problem

The system attempted optimization while too many variables remained unresolved simultaneously.

Unknowns included:

- future POIs
- route direction
- time allocation
- travel delays
- opening-hour feasibility
- pacing quality
- fatigue accumulation

Because these variables were interdependent, uncertainty propagated through the itinerary.

---

## Result

The optimizer effectively operated on partially invalid assumptions at every stage.

This created:

- unstable downstream predictions
- repeated correction cycles
- fragile itinerary structures

---

# 10. Incorrect Role Assignment for the LLM

## Initial Assumption

The architecture treated the LLM as the primary optimizer.

The LLM was expected to:

- rank POIs
- optimize flow
- infer routing quality
- resolve spatial tradeoffs

---

## Why This Failed

LLMs are strong at:

- semantic understanding
- reasoning over preferences
- explanation generation
- soft ranking

They are weak at:

- combinatorial optimization
- constrained routing
- spatial scheduling
- deterministic feasibility optimization

The architecture attempted to use the LLM for problems better solved using:

- graph algorithms
- heuristic search
- constraint solvers
- clustering systems

---

# Architectural Reframing

The implementation revealed that itinerary generation is fundamentally closer to:

```text
constrained graph optimization
```

than:

```text
autoregressive recommendation
```

The problem resembles:

- Vehicle Routing Problems
- Orienteering Problems
- Time-window scheduling
- Multi-objective optimization

rather than traditional recommendation systems.

---

# Better Architectural Direction

The revised direction reorganized the planning hierarchy.

Instead of:

```text
slot → slot → slot
```

the system should operate as:

```text
Global Intent
    ↓
Anchor Extraction
    ↓
Regional Clustering
    ↓
Feasible Day Construction
    ↓
Intra-Day Routing
    ↓
Flexible Slot Filling
    ↓
LLM Explanation Layer
```

---

# Why This Direction Is Better

This architecture stabilizes the optimization process because:

- geographic structure is established early
- routing happens after clustering
- feasibility filtering occurs before optimization
- local search occurs inside stable regions
- LLMs are used for interpretation instead of hard optimization

---

# Revised Optimization Philosophy

The key realization was:

```text
Local optimization alone is insufficient.
```

The system must optimize:

- feasibility
- geographic coherence
- pacing
- temporal constraints
- experience quality

simultaneously.

Global structure must emerge before local refinement.

---

# Remaining Open Problems

Even with improved architecture, several difficult research problems remain.

---

## 1. Dynamic Replanning

Users may:

- skip attractions
- arrive late
- change preferences mid-trip

The system must adapt without fully recomputing the itinerary.

---

## 2. Human Uncertainty

Real travel behavior is stochastic.

Factors include:

- weather
- queue times
- traffic
- fatigue
- spontaneous exploration

Rigid optimization often performs worse than resilient optimization.

---

## 3. Multi-Objective Tradeoffs

The system must balance:

- efficiency
- exploration
- novelty
- comfort
- budget
- pacing

These objectives frequently conflict.

---

## 4. Group Preference Resolution

Multiple travelers introduce:

- conflicting interests
- pacing disagreements
- budget mismatches

Optimization becomes significantly harder.

---

# Final Conclusion

The sequential slot-based architecture failed because the optimization assumptions were fundamentally incorrect.

The primary issues were:

- itinerary quality is globally coupled
- routing dependencies emerged too early
- spatial features depended on unstable states
- local ranking produced globally weak itineraries
- repeated recomputation scaled poorly
- geographic structure lacked stable anchors

The implementation nevertheless produced critical architectural insights:

- itinerary optimization is a global planning problem
- feasibility must precede routing
- anchor extraction is essential
- geographic clustering must occur early
- LLMs should augment optimization, not replace it
- experience quality must be treated as a first-class optimization objective