import requests
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv
from scraper import search_wikipedia, scrape_engine

load_dotenv()

import os
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "discovery.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

SEED_CATEGORIES = [
    "Toyota engine",
    "Nissan engine",
    "Honda engine",
    "Mitsubishi engine",
    "Subaru engine",
    "Mazda engine",
    "General Motors engine",
    "Ford engine",
    "Chrysler engine",
    "BMW engine",
    "Mercedes-Benz engine",
    "Audi engine",
    "Porsche engine",
    "Volkswagen engine",
    "Ferrari engine",
    "Lamborghini engine",
]

def normalize(name):
    return name.lower().strip().replace("-", " ").replace("_", " ")

def is_valid_engine(title):
    title_lower = title.lower()
    # Skip list pages
    if "list of" in title_lower:
        return False
    if title_lower.startswith("list"):
        return False
    # Skip disambiguation pages
    if "disambiguation" in title_lower:
        return False
    # Skip category pages
    if "category:" in title_lower:
        return False
    # Must mention engine or motor
    if "engine" not in title_lower and "motor" not in title_lower:
        return False
    return True

def get_existing_engines():
    try:
        df = pd.read_csv(os.path.join(BASE_DIR, "engine_specs.csv"))
        return set(df["engine"].unique())
    except:
        return set()

def discover_engines_from_category(category):
    discovered = []
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": category,
            "format": "json",
            "srlimit": 10
        }
        response = requests.get(
            search_url, params=params, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if response.status_code != 200 or not response.text.strip():
            return []
        data = response.json()
        results = data.get("query", {}).get("search", [])
        for r in results:
            title = r["title"]
            if is_valid_engine(title):
                discovered.append(title)
    except Exception as e:
        logging.error(f"Discovery failed for {category}: {e}")
    return discovered

def run_discovery():
    print(f"Starting discovery at {datetime.now()}")
    logging.info("Discovery started")

    existing = get_existing_engines()
    print(f"Currently have {len(existing)} engines")

    all_discovered = []
    for category in SEED_CATEGORIES:
        print(f"Searching category: {category}...")
        found = discover_engines_from_category(category)
        all_discovered.extend(found)

    all_discovered = list(set(all_discovered))
    print(f"Discovered {len(all_discovered)} potential engines")

    existing_normalized = {normalize(e) for e in existing}
    new_engines = [e for e in all_discovered if normalize(e) not in existing_normalized]

    seen = set()
    deduped = []
    for e in new_engines:
        n = normalize(e)
        if n not in seen:
            seen.add(n)
            deduped.append(e)
    new_engines = deduped

    # Filter out list pages from new engines too
    new_engines = [e for e in new_engines if is_valid_engine(e)]

    print(f"Found {len(new_engines)} new engines to add")
    logging.info(f"Found {len(new_engines)} new engines")

    if not new_engines:
        print("No new engines found")
        return

    new_data = []
    for engine in new_engines:
        print(f"Scraping new engine: {engine}...")
        url = search_wikipedia(engine)
        if url:
            data = scrape_engine(engine, url)
            new_data.extend(data)
            logging.info(f"Added new engine: {engine}")

    if new_data:
        existing_df = pd.read_csv(os.path.join(BASE_DIR, "engine_specs.csv"))
        new_df = pd.DataFrame(new_data)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["engine", "variant", "spec"], keep="first")
        combined.to_csv(os.path.join(BASE_DIR, "engine_specs.csv"), index=False)
        combined.to_excel(os.path.join(BASE_DIR, "engine_specs.xlsx"), index=False)
        print(f"Added {len(new_data)} new rows to database")
        logging.info(f"Discovery complete: added {len(new_data)} rows")
    else:
        print("No new data scraped")

if __name__ == "__main__":
    run_discovery()
