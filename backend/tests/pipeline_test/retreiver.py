# retriever.py

import csv
import os
from rapidfuzz import fuzz
import serpapi
from dotenv import load_dotenv

from helper import measure_latency
from extractor import extract_user_input

load_dotenv()

# config
SERP_API_KEY = os.getenv("SERP_API_KEY")
serpapi_client = serpapi.Client(api_key=SERP_API_KEY)

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

# config

BASE_DIR = os.getcwd()
PARENT_DIR = os.path.join(BASE_DIR, "backend", "tests", "pipeline_test")
DATA_DIR = os.path.join(PARENT_DIR, "data")
LATLON = os.path.join(DATA_DIR, "latlon_index")

def retreive_latlon(dest, international):
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

if __name__ == "__main__":

    from extractor import extract_user_input
    import json

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

    # -------------------------
    # EXTRACT USER INPUT
    # -------------------------

    structured_input = extract_user_input(input_text)

    # convert to pure JSON-safe dict if needed
    if isinstance(structured_input, str):
        structured_input = json.loads(structured_input)

    print("\n" + "=" * 60)
    print("[STRUCTURED INPUT]")
    print("=" * 60)

    print(json.dumps(structured_input, indent=2, ensure_ascii=False))

    # -------------------------
    # RETRIEVE LAT/LON
    # -------------------------

    print("\n" + "=" * 60)
    print("[LOCATION RETRIEVAL]")
    print("=" * 60)

    data = structured_input.get("data", structured_input)

    destination = data.get("destination")
    international = data.get("international", False)

    dest, lat, lon, zoom = retreive_latlon(
        destination,
        international
    )

    print(f"Destination : {dest}")
    print(f"Latitude    : {lat}")
    print(f"Longitude   : {lon}")
    print(f"Zoom Level  : {zoom}")

    # -------------------------
    # EXTRACT CATEGORIES
    # -------------------------

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

    print(f"\n[INFO] Categories to search: {queries}")

    breakpoint()

    # -------------------------
    # FETCH SERPAPI RESULTS
    # -------------------------

    print("\n" + "=" * 60)
    print("[SERPAPI FETCH]")
    print("=" * 60)

    for query in queries:

        print(f"\n[QUERY] {query}")

        results = fetch_serpapi(
            lat=lat,
            lon=lon,
            zoom=zoom,
            query=query
        )

        if not results:
            print("No results found.")
            continue

        print(f"Results Found: {len(results)}")

        # print only first 3 for readability
        # print(
        #     json.dumps(
        #         results[:1],
        #         indent=2,
        #         ensure_ascii=False
        #     )
        # )