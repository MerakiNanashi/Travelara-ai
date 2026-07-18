V1.0.0 Due date: 18 - done

# Issue 1:
- a single change in schema ended up in hundred lines of code needing update across multiple files and folders
sol: standardized the structure with stages knowing config and adding global state, only using internal schemas inside for implementation details.

# Issue 2:
- Hitting read timeout & exhausted token noise from LLM

# Issue 3: - MAJOR ISSUE
- Silent exceptions and fails for retreival
- no retry loop for gemini

identified: issue originating from schema and prefs_to_legacyprefs -> originally was skipping subjective prefs -> If the LLM produced only subj prefs, the pipeline failed.
res: (temp) considering all prefs, regardless of type

# Issue 4:
- Cold start everytime
sol: build intialization that runs instantly once the unicorn launches the endpoint

# Issue 4:
- High latency spike at reranker due to recall heavy arch running cosine sim on emb 
pot. sol.:
1. Further light weight filtering using travel-specific scorer
2. Late interaction (ColBERT)
3. Better pruning at stages before: Level wise pruning - adaptive pruning based on retreived length, days, etc.
4. Asymmetric (dual) encoders
5. caching

Method	Relative quality	Relative speed	Online transformer?
BGE-M3 embeddings	100%	1×	Yes
MiniLM embeddings	90–95%	3–6×	Yes
SPLADE-Tiny	~80–90%	Faster retrieval; encoding still needed	Yes
BM25 + synonym expansion	70–90%	20–100×	No
Feature-based scorer	80–95%*	100×+	No
- RapidFuzz
- TF-IDF
- BM25

- main question: which model/strategy is good enough for the system?

# issue 5:
schema unable to resolve complicated to simple queries

# issue 6:
taxamony not mapped the best

res: pre indexed taxamony -> prefs etc.

# issue 7:
pruning too aggresive for smaller clusters/less survival score clusters

# Trade offs:
1. architecture -> sequential to hierarchial
2. h3 index vs hdbscan & strict cluster boundaries vs flexible boundareies
3. 

# Design decisions:
1. sep stages, shared files and implementation details
2. Clustering:
Retrieve
      ↓
HDBSCAN
      ↓
Score clusters
      ↓
Merge nearby weak clusters
      ↓
Split overloaded clusters
      ↓
Absorb nearby noise
      ↓
Prune by expected marginal utility
      ↓
Scheduler

# Tasks:
1. Build seeds for reproducible query tests
2. evaluate retreival & add more options
3. evluate clusterscore & threshold
4. evaluate hdbscan vs h3 vs others
5. 

# Main Task:
- determine KPI 
- determine earlier established benchmarks to compare against
Quality (how good is the output?)
Efficiency (how fast and expensive is it?)
Robustness (does it still work under difficult conditions?)
Scalability (does it degrade gracefully?)
Ablation (what actually contributes to performance?)
- System performance criterias
- 