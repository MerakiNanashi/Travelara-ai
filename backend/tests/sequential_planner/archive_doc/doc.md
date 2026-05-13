## Problem:

Itinerary Generation: Provide an itinerary that optimizes for multiple objectives such as budget, travel time, user preference, etc. and the generated itinerary needs to be a viable solution.

### Sub Problems:

1. Multi Objective:
    - Budget
    - Destination
    - Days Of Stay
    - User Preference
    - User Constraints
    - User History
    - Travel Time
    - Travel Fatigue
    - Opening & Closing Hours
    - Group/Solo Travel
    - Physical Health Of User
    - Implicit Objectives

2. Levels of Optimization:
    - Slot Level Optimization
    - Day Level Optimization
    - Journey Level Optimization

    The itinerary should make sense holistically. 

3. Dynamic Replanning
Handle delays, weather, closures, cancellations, and real-time changes.

4. Uncertainty Handling
Account for unreliable travel times, queues, weather, and human unpredictability.

5. Scalability & Data Quality
Large-scale optimization with incomplete, noisy, and constantly changing travel data.

6. Explainability
Users should understand why the itinerary was generated and what tradeoffs were made.

7. Evaluation Problem
Measuring “good itinerary quality” is subjective and difficult.

8. Experience Quality Optimization
Optimize not just efficiency, but overall trip quality:
    variety
    emotional flow
    scenic timing
    rest balance

## Technical Challenges:
1. Multiple changing constraints & user preferences eg. "Don't like crowded places", etc.
2. Multi Objective Optimisation: Must optimize for budget, open & closing hours, travel time, preferences, constraints, etc.
3. Seasonal trends, outdated data, fragmented data, missingness in data, etc.
4. 


# POI data:

current: SerpAPI (250 per month - too low limit, doesn't require for use case - can be added to enrich POI/fallback)

Migrate to:
1. yelp fusion
2. foursquare
3. Geoapify (for main points)
4. bing maps
5. osm - fallback

# Distance matrix:

1. Geoapify
2. 

Tips/Loc Data:

1. Wikivoyage
2. 


effective_distance =
    haversine_distance
    × urban_density_factor
    × terrain_penalty
    × congestion_factor


current approach (Implemented till Retreiver, rejected due to complexity and practicality, failed to be v1):

user input -> NLU/NLP (Currently gemini 2.5 flash lite) -> Structured JSON (User constraints, preferences, etc. + Itinerary Structure)
-> SerpAPI/Data Source (Fetch POIs based on  Itinerary Structure) -> Filter (Based on Upper Budget Limit) -> Calculate Haversine for sequential POIs and Population Density -> Candidate Generator [ML model+ Fine tuned SLM, will rank for each slot and build itinerary] -> Ranker (LLM, will rank the top itineraries based on user preference & constraints) -> Itinerary Generated

Problems: 
1. Haversine calculation requires the knowledge of previous point, calculating for each candidate that can fit the slot before will create noise for the model
2. Need to decide a direction or radius for each day
3. This approach would require me to run two stages iteratively over and over again ie. calculate haversine, rank candidates for a slot, fill slot, then do it all again since I need to know the previous slot candidate
4. I require flexibility in my solution as itinerary should be updated according to anchor points -> no anchor points currently
