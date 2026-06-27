- Boost cluster score if another anchor is present in the cluster 

3 scores -> 1. cluster, 2. anchor, 3. POI

1. Anchor score for all potential anchors.
2. Cluster score based on Anchor and relative distance, etc.
3. Select Cluster, and then Anchor
4. Populate around Anchor, past potential anchors are valid candidates - only enrich further if not enough quality POIs in the cluster.



pre cluster score 
clustering
cummlative cluster score + distance metrics
choose cluster
choose anchor
expand POIs

For evaluation:

- Could use GPT/CLaude etc. for trips on a select few locations
- Against Mindtrip etc.
- Against sota architectures for travel planning
