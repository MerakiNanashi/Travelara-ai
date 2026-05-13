# retriever.py

# To do: improve query by adding tags/semantic hints from the activity slots (Eg. if a slot has tags like "family-friendly", "offbeat", etc. we can add those to the query to get more relevant results from SerpAPI, etc.)
# To do: implement a fallback mechanism if no good matches are found in the local geonames dataset (Eg. use SerpAPI to search for the destination and extract lat/lon from there, etc.)
# Fallback mechanism for geoname lat/lon: SerpAPI or any other method
# To do: implement fallback for SerpAPI results, try for local nighborhood-level search if city-level search doesn't yield good results, etc./ decrease zoom level to get more results, etc./try for more pages of results, etc.
# To do: for variety preference, can search longer for a specific category (ie. more pages of results) to get more options for candidate generation, etc.
# To do: better zoom level estimation based on city size/type (Eg. for a major city like Paris, we can use a higher zoom level to get more localized results, while for a smaller town, we can use a lower zoom level to cover the whole area, etc.) and according to user preferences (Eg. if user prefers more variety, we can use a lower zoom level to get a wider range of results, etc.)


# To do: add latency and price estimation for retreiver step.
# To do: implement caching for retreived results to speed up subsequent runs with similar inputs (Eg. if we already have lat/lon for Paris, we can cache that and reuse it instead of parsing the geonames dataset again, etc.)
# To do: check relevancy of retreived results (Eg. if we get lat/lon for a different Paris in the US instead of Paris, France, we can detect that based on the population, feature code, or by doing a quick SerpAPI search with the lat/lon to see if it matches the intended destination, etc.) and implement a fallback if the results are not relevant (Eg. use SerpAPI to search for the destination and extract lat/lon from there, etc.)

import csv
import os
from rapidfuzz import fuzz
import serpapi
from dotenv import load_dotenv
from datetime import datetime
import json
import asyncio
import random
import httpx

from helper import measure_latency
from extractor import extract_user_input

load_dotenv()

# config
SERP_API_KEY = os.getenv("SERP_API_KEY")
serpapi_client = serpapi.Client(api_key=SERP_API_KEY)

# config

BASE_DIR = os.getcwd()
PARENT_DIR = os.path.join(BASE_DIR, "backend", "tests", "sequential_planner")
DATA_DIR = os.path.join(PARENT_DIR, "data")
LATLON = os.path.join(DATA_DIR, "latlon_index")

SERP_URL = "https://serpapi.com/search.json"


def parse_geonames(filepath):
    cleaned = []

    with open(filepath, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")

        for row in reader:
            try:
                name = row[1].strip().lower()
                lat = float(row[4])
                lon = float(row[5])
                feature_code = row[7]
                population = int(row[14]) if row[14] else 0

                # Keep populated places + admin regions
                if not (feature_code.startswith("PPL") or feature_code.startswith("ADM")):
                    continue

                cleaned.append({
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "feature_code": feature_code,
                    "population": population
                })

            except Exception:
                continue

    return cleaned


def filter_dataset(dest, data, threshold=70):
    dest = dest.lower().strip()
    scored = []

    for row in data:
        name = row.get("name", "")
        score = fuzz.partial_ratio(dest, name)

        if score >= threshold:
            scored.append((score, row))

    if not scored:
        return []

    # Sort by fuzzy score first, then population
    scored.sort(
        key=lambda x: (x[0], x[1].get("population", 0)),
        reverse=True
    )

    return [row for _, row in scored]


def get_zoom(population):
    if population > 1_000_000:
        return 10   # major city
    elif population > 100_000:
        return 12   # mid-sized city
    elif population > 10_000:
        return 14   # town
    else:
        return 16   # small place


def get_best_location(dest, data):
    filtered = filter_dataset(dest, data)

    if not filtered:
        return dest, None, None, None

    # Choose highest population among fuzzy matches
    best_match = max(filtered, key=lambda r: r.get("population", 0))

    population = best_match.get("population", 0)
    lat = best_match.get("lat")
    lon = best_match.get("lon")

    zoom = get_zoom(population)

    return dest, lat, lon, zoom

@measure_latency
def retreive_latlon(dest, international):
    data = None
    try:
        if not international:
            filepath = os.path.join(LATLON, "IN.txt")
            data = parse_geonames(filepath)
        if international or data is None:
            filepath = os.path.join(LATLON, "cities500.txt")
            data = parse_geonames(filepath)
    except Exception as e:
        print(f"Error parsing geonames data: {e}")
        return dest, None, None, None        

    return get_best_location(dest, data)

@measure_latency
def fetch_serpapi(lat, lon, zoom, query):
    try:
        results = serpapi_client.search(
            engine="google_maps",
            q=query,
            ll=f"@{lat},{lon},{zoom}z"
        )
        return results['local_results']
    except Exception as e:
        print(f"Error fetching SerpAPI data: {e}")
        return {}

def save_results(dest, results):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    dir_1 = "output"

    if not os.path.exists(dir_1):
        os.makedirs(dir_1)

    dir_2 = os.path.join(dir_1, "serpapi_results")

    if not os.path.exists(dir_2):
        os.makedirs(dir_2)

    filename = f"{dest}_{timestamp}.json"

    filepath = os.path.join(dir_2, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


async def fetch_serpapi_async(
    client,
    semaphore,
    lat,
    lon,
    zoom,
    query,
    api_key,
    max_retries=5,
    base_delay=1
):

    params = {
        "engine": "google_maps",
        "q": query,
        "ll": f"@{lat},{lon},{zoom}z",
        "api_key": api_key
    }

    async with semaphore:

        for attempt in range(max_retries):

            try:

                response = await client.get(
                    SERP_URL,
                    params=params,
                    timeout=30
                )

                # Rate limit
                if response.status_code == 429:

                    delay = (
                        base_delay * (2 ** attempt)
                        + random.uniform(0, 1)
                    )

                    print(
                        f"[{query}] Rate limited. "
                        f"Retrying in {delay:.2f}s"
                    )

                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()

                data = response.json()

                return query, data.get("local_results", [])

            except (
                httpx.TimeoutException,
                httpx.HTTPStatusError,
                httpx.NetworkError
            ) as e:

                delay = (
                    base_delay * (2 ** attempt)
                    + random.uniform(0, 1)
                )

                print(
                    f"[{query}] Error: {e} | "
                    f"Retrying in {delay:.2f}s"
                )

                await asyncio.sleep(delay)

        print(f"[{query}] Failed after retries.")

        return query, []


@measure_latency
async def retreive_poi(
    debug=False,
    detailed_debug=False,
    max_concurrency=5,
    **kwargs
):

    structured_input = kwargs.get("structured_input")

    if isinstance(structured_input, str):
        structured_input = json.loads(structured_input)

    data = structured_input.get("data", structured_input)

    destination = data.get("destination")
    international = data.get("international", False)

    dest, lat, lon, zoom = retreive_latlon(
        destination,
        international
    )

    categories = set()

    itinerary = (
        data.get("itinerary_structure", {})
            .get("day_itinerary", [])
    )

    for day in itinerary:

        for slot in day.get("slots", []):

            category = slot.get("category")

            if category:
                categories.add(category)

    queries = list(categories)

    if not queries:
        print("No categories found.")
        return {}

    if detailed_debug:

        print("\n" + "=" * 60)
        print("[STRUCTURED INPUT]")
        print("=" * 60)

        print(
            json.dumps(
                structured_input,
                indent=2,
                ensure_ascii=False
            )
        )

    if debug:

        print(
            "[STRUCTURED INPUT]",
            json.dumps(
                structured_input,
                indent=2,
                ensure_ascii=False
            )[:100]
        )

        print("\n" + "=" * 60)
        print("[LOCATION RETRIEVAL]")
        print("=" * 60)

        print(f"Destination : {dest}")
        print(f"Latitude    : {lat}")
        print(f"Longitude   : {lon}")
        print(f"Zoom Level  : {zoom}")

        print("\n" + "=" * 60)
        print("[SERPAPI FETCH]")
        print("=" * 60)

        print(f"\n[INFO] Categories: {queries}")

    semaphore = asyncio.Semaphore(max_concurrency)

    all_results = {}

    async with httpx.AsyncClient() as client:

        # --------------------------------------------------
        # Warmup request
        # --------------------------------------------------

        warmup_query = queries[0]

        if debug:
            print(f"\n[WARMUP QUERY] {warmup_query}")

        warmup_query, warmup_results = (
            await fetch_serpapi_async(
                client=client,
                semaphore=semaphore,
                lat=lat,
                lon=lon,
                zoom=zoom,
                query=warmup_query,
                api_key=SERP_API_KEY
            )
        )

        if not warmup_results:

            print(
                "[ERROR] Warmup request failed. "
                "Aborting concurrent fetch."
            )

            return {}

        all_results[warmup_query] = warmup_results

        if debug:
            print(
                f"[WARMUP SUCCESS] "
                f"{len(warmup_results)} results"
            )

        # --------------------------------------------------
        # Remaining concurrent tasks
        # --------------------------------------------------

        remaining_queries = queries[1:]

        tasks = [

            fetch_serpapi_async(
                client=client,
                semaphore=semaphore,
                lat=lat,
                lon=lon,
                zoom=zoom,
                query=query,
                api_key=SERP_API_KEY
            )

            for query in remaining_queries
        ]

        for task in asyncio.as_completed(tasks):

            query, results = await task

            if not results:

                print(f"[{query}] No results.")
                continue

            all_results[query] = results

            print(
                f"[{query}] "
                f"Results Found: {len(results)}"
            )

            if detailed_debug:

                print(
                    json.dumps(
                        results[:1],
                        indent=2,
                        ensure_ascii=False
                    )
                )

    save_results(dest, all_results)

    return all_results

def retreive_test():
    pass

if __name__ == "__main__":

    input_text = (
        "I want to visit Paris for 5 days with a budget of $2000. "
        "I love art, history, and food. "
        "I will be starting from London."
        "I'm quite flexible with my plans and open to suggestions, but I do want to make sure I hit some key landmarks and try the local cuisine."
        "I also prefer to have a mix of activities each day, like visiting museums in the morning and exploring local markets or cafes in the afternoon."
        "Don't want to spend too much time traveling between locations, so ideally, activities should be clustered by area."
        "Don't want to spend all the time on touristy spots; would love to discover some hidden gems and local favorites as well."
        "I can handle a moderately busy schedule. I don't mind having some free time, but I also want to make the most of my trip and see as much as possible without feeling rushed."
    )

    structured_input = extract_user_input(input_text)
    asyncio.run(
    retreive_poi(
        debug=True,
        detailed_debug=False,
        structured_input=structured_input
    )
)