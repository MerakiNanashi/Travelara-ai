# Hierarchical Anchor-Based Itinerary Planning Architecture

---

# Overview

This architecture approaches itinerary generation as a:

- hierarchical planning problem
- globally coupled optimization problem
- spatial-temporal constraint satisfaction problem

rather than:
- sequential slot prediction
- autoregressive POI recommendation
- greedy next-best selection

The primary design goal is to stabilize itinerary optimization by introducing:

- anchor-based decomposition
- geographic clustering
- constrained candidate generation
- globally informed routing

The architecture attempts to reduce:
- recursive optimization instability
- candidate space explosion
- geographically incoherent routing
- unstable downstream dependencies

---

# Core Design Philosophy

The architecture assumes:

```text
Itinerary quality emerges globally,
not through local slot optimization.
```

Therefore:
- routing should not happen before geographic structure exists
- candidate generation should not operate on unstable downstream states
- POI selection should occur inside constrained spatial regions
- optimization should be hierarchical rather than sequential

---

# Global Architecture Flow

```text
User Input
    ↓
Global Intent Extraction
    ↓
Destination Understanding
    ↓
Anchor Selection
    ↓
Anchor Region Construction
    ↓
POI Retrieval
    ↓
Feasible Day Construction
    ↓
Graph-Based Optimization
    ↓
LLM Review Layer
    ↓
Final Itinerary
```

---

# Global State Management

A global itinerary state should be maintained throughout the pipeline.

This state acts as:
- shared optimization context
- reviewer-agent memory
- feasibility tracking layer
- planning state representation

---

## Example Global State

```python
State = {
    destination,
    anchors,
    selected_pois,
    remaining_budget,
    temporal_constraints,
    soft_constraints,
    fatigue_score,
    routing_structure,
    unresolved_conflicts,
    regional_clusters,
    itinerary_confidence
}
```

The global state enables:
- consistency across modules
- iterative refinement
- reviewer-agent intervention
- partial replanning

---

# 1. Global Intent Extraction Layer

## Purpose

The intent extraction layer converts free-form user input into structured planning constraints.

---

## Input

```text
Natural language user request
```

Example:

```text
Plan a 5-day Japan itinerary focused on anime culture,
food, and nightlife with a medium budget.
```

---

## Output

Structured itinerary representation:

```json
{
  "destination": "...",
  "starting_point": "...",
  "budget": "...",
  "days": 5,
  "international": true,
  "preferences": {
    "hard": [],
    "soft": [],
    "conflicting": []
  },
  "constraints": {
    "hard": [],
    "soft": [],
    "conflicting": []
  }
}
```

---

## Responsibilities

The layer extracts:

- destination
- hotel/stay location
- budget
- travel duration
- international/domestic travel
- hard preferences
- soft preferences
- conflicting preferences
- hard constraints
- soft constraints
- conflicting constraints

---

## Conflict Resolution

If conflicting constraints are detected:

```text
Low budget
+
Luxury dining
+
Minimal travel
+
Dense itinerary
```

the system should:
- assign priority weights
- trigger clarification dialogue
- resolve optimization ambiguity

---

## Destination Understanding

After extraction:

- retrieve destination metadata
- identify geographic structure
- estimate density
- estimate reachable regions
- dynamically adjust planning radius

---

## Dynamic Radius Scaling

Radius should not rely purely on:
- haversine distance
- static geographic radius

Instead, radius should adapt based on:

- population density
- transportation structure
- urban topology
- travel velocity
- geographic barriers
- walkability

---

## Preferred Interpretation

Instead of:

```text
5km radius
```

prefer:

```text
POIs reachable within 30 minutes
```

This produces more stable routing behavior.

---

# 2. Anchor Selection Layer

# Purpose

The anchor selection layer identifies the:

```text
semantic and geographic highlights
```

of the itinerary.

Anchors act as:
- spatial stabilizers
- geographic organizers
- clustering centroids
- routing references
- itinerary structure primitives

---

# What Defines an Anchor?

An anchor is:

```text
A high-importance POI selected as the primary
spatial-semantic organizer for a day or itinerary segment.
```

Example:

```text
Trip to Shoja
→ Serolsar Lake becomes an anchor
```

because it:
- defines direction
- shapes surrounding POI retrieval
- acts as the highlight of the day
- stabilizes routing structure

---

# Why Anchors Must Exist

Without anchors:

- geographic clustering becomes unstable
- routing direction oscillates
- candidate generation becomes noisy
- optimization becomes globally unstable

Anchors reduce:
- search-space entropy
- routing ambiguity
- recursive downstream instability

---

# Anchor Selection Objectives

The system selects anchors by solving:

```text
arg max(f(a_i))
```

subject to:
- distinctness constraints
- geographic separation
- temporal feasibility
- itinerary coverage

where:

```text
a_i ∈ A
```

and:

```text
A = set of anchor candidates
```

---

# Distinctness Constraint

Anchors should remain distinct from future anchors:

```text
a_i ≠ a_j
```

This prevents:
- anchor collapse
- regional redundancy
- repetitive itinerary structure

Example failure case:

```text
5 nightlife anchors
all inside Shinjuku
```

which may optimize locally but weakens global diversity.

---

# Anchor Selection Pipeline

## Step 1 — Hard Pruning

Before anchor scoring:

- remove duplicates
- remove geographically overlapping POIs
- remove irrelevant categories
- remove timing conflicts
- remove infeasible POIs
- remove budget violations
- remove low-quality POIs

---

## Step 2 — Anchor Scoring

Candidate anchors are scored using:

- LLM/SLM reasoning
- ML scoring
- heuristic scoring

under the assumption that:
- anchors must remain distinct
- anchors should improve global itinerary structure

---

## Step 3 — Spatial Separation

After selection:

- assign dynamic search radius
- assign geographic bounding region
- reject overlapping anchors
- reject spatial conflicts

If conflicts exist:

```text
Anchor overlap
→ reject
→ choose next candidate
```

---

# Anchor Score Function

```text
AnchorScore =
    semantic_importance
  + geographic_connectivity
  + routing_centrality
  + preference_alignment
  - isolation_penalty
  - temporal_cost
```

---

# Anchor Score Components

## Semantic Importance

Measures:
- landmark significance
- experiential uniqueness
- destination relevance

---

## Geographic Connectivity

Measures:
- nearby POI richness
- transit accessibility
- cluster generation potential

---

## Routing Centrality

Measures:
- usefulness as a routing hub
- ability to stabilize itinerary flow

---

## Preference Alignment

Measures:
- alignment with user intent
- compatibility with constraints

---

## Isolation Penalty

Penalizes:
- geographically isolated POIs
- routing inefficiency
- disconnected attractions

---

## Temporal Cost

Penalizes:
- excessive time consumption
- rigid scheduling requirements
- itinerary distortion

---

# 3. POI Retrieval Layer

# Purpose

Retrieve candidate POIs around anchor regions.

The retrieval process is globally informed rather than sequential.

---

# Input Context

The retrieval layer receives:

- destination metadata
- anchor structure
- user preferences
- constraints
- global itinerary state

---

# LLM/SLM Retrieval Pass

The retrieval model generates:

- POI queries
- category expansion
- contextual search terms
- slot-aware retrieval
- anchor-day associations

---

# Output

```text
Anchor
    ↓
Associated POIs
    ↓
Candidate clusters
```

with:
- tentative slot assignments
- tentative day assignments

---

# Retrieval Constraints

The retrieval layer should enforce:

- geographic relevance
- category diversity
- budget feasibility
- timing feasibility
- transportation feasibility

before optimization.

---

# 4. Graph-Based POI Selection & Feasible Day Construction

# Purpose

Construct geographically coherent and feasible itinerary days.

---

# Graph Representation

Each:

```text
node → POI
edge → relationship weight
```

Edge weights may include:

- travel time
- transit difficulty
- semantic similarity
- preference alignment
- temporal feasibility
- routing efficiency
- fatigue cost

---

# Optimization Goal

The graph optimization layer attempts to:

- construct feasible days
- maximize itinerary quality
- minimize routing inefficiency
- maintain geographic coherence
- preserve anchor structure

---

# Possible Optimization Methods

Potential approaches:

- weighted graph search
- beam search
- graph clustering
- local search optimization
- GNN/GAT architectures
- constraint programming
- hybrid heuristic optimization

---

# Important Consideration

GNN/GAT architectures may require:
- large-scale trajectory data
- behavioral datasets
- transition statistics

Simpler graph optimization methods may be more practical initially.

---

# Feasible Day Construction

Each day should optimize:

- temporal feasibility
- spatial compactness
- pacing quality
- POI diversity
- travel efficiency

rather than:
- raw POI quantity

---

# 5. LLM Review Layer

# Purpose

The review layer performs:
- itinerary validation
- quality inspection
- anomaly detection
- refinement suggestions

---

# Reviewer Responsibilities

The reviewer should explicitly check:

- geographic coherence
- pacing anomalies
- excessive transitions
- temporal conflicts
- category redundancy
- fatigue spikes
- poor anchor placement
- low diversity
- budget violations

---

# Reviewer Actions

The reviewer may:

- reject a route
- replace POIs
- swap anchors
- trigger replanning
- rerun partial pipeline stages

---

# Important Constraint

Reviewer agents should remain bounded.

Without explicit review criteria:
- review becomes nondeterministic
- reasoning becomes unbounded
- optimization becomes unstable

---

# Core Optimization Philosophy

The architecture assumes:

```text
Local optimization alone is insufficient.
```

The system must optimize simultaneously for:

- geographic coherence
- preference alignment
- temporal feasibility
- pacing quality
- routing efficiency
- diversity
- resilience
- experience quality

---

# Key Architectural Insight

The primary architectural insight is:

```text
Candidate generation must operate
inside stable geographic structure.
```

Anchors therefore act as:

- optimization stabilizers
- routing primitives
- geographic constraints
- semantic organizers

This reduces:
- recursive instability
- candidate drift
- reranking collapse
- globally incoherent routing

---

# Remaining Open Problems

Several difficult problems still remain:

- stochastic travel delays
- dynamic replanning
- uncertainty modeling
- fatigue prediction
- multi-user preference balancing
- sparse POI metadata
- explainability
- cold-start destinations
- scalable global optimization

---

# Final Summary

This architecture reframes itinerary generation as:

```text
Hierarchical constrained spatial-temporal optimization
```

rather than:

```text
Sequential recommendation
```

The key structural improvement is the introduction of:

```text
Anchor-based hierarchical decomposition
```

which stabilizes:
- candidate generation
- geographic clustering
- routing structure
- global optimization behavior