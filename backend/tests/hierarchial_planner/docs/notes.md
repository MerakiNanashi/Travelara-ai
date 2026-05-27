Architecture:

Note: Maintain a global state or thread level state to potentially pass to a reviewer agent

1. Global Intent/Extractor

    I/P: User Input
    O/P: Dest, Starting Point/Stay, Budget,  Preferences: Hard, Soft, Conflicting (w priority - trigger chat for info); Constraints: Hard, Soft, Conflicting (w priority - trigger chat for info); days: int, international: bool, queries for anchor selection based on preferences/constraints
-> 
    Geographic Location of Dest - Filter and adjust radius according to Location & Population (zoom - needs to be dynamic) - Retreive Info on Dest
->
2. Anchor Selection:

    1.Select Anchor based on available time slots using LLM/SLM Scoring+ML Scoring (On the assumption each anchor has to be distinct from each other)
    2.Seperate Anchor & Search Radius/Bounding Box adjusted according to Distance & Density
    *Note: In case of high quantity -> Hard pruning/Filter Eg. Lat/Lon too close, Duplicates, Irrelevant category, out of budget (shouldnt be more than 50% of budget), timing issues, etc. Before step 1
    *Note: conflicts ie. overlapping radius/too close Anchors -> reject, choose next After step 2
->
3. POI Retreival:

    1. LLM/SLM pass -> i/p info on destination, anchors, preferences, constraits (global state) -> o/p queries for POI + Time slot assignment + Anchor Day assignment
->
4. GNN/GAT Based POI Selection - Feasible Day Construction

    Each node -> POI -> each edge a weight based on some linear/non-linear combination -> o/p a set of POIs + Anchors with their assigned day

5. LLM Review Layer - Option to switch out or redo a certain step for better results

