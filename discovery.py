import requests
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv
from scraper import search_wikipedia, scrape_engine, is_family_page, extract_variant_pages

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

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize(name):
    return name.lower().strip().replace("-", " ").replace("_", " ")


def is_valid_engine(title):
    """
    Filter out pages that are definitely not engine articles.
    NOTE: We do NOT require 'engine' or 'motor' in the title anymore —
    specific variant pages like 'Nissan SR20DET' or 'Honda K20A' are valid
    but won't contain those words.
    """
    title_lower = title.lower()

    if "list of" in title_lower:
        return False
    if title_lower.startswith("list"):
        return False
    if "disambiguation" in title_lower:
        return False
    if "category:" in title_lower:
        return False
    if "template:" in title_lower:
        return False
    if "wikipedia:" in title_lower:
        return False

    # Skip obvious non-engine articles (car model pages, person pages, etc.)
    # that might appear in search results
    NON_ENGINE_SIGNALS = [
        "automobile", "car model", "racing team", "race car",
        "biography", "person", "company", "corporation",
    ]
    if any(s in title_lower for s in NON_ENGINE_SIGNALS):
        return False

    return True


def get_existing_engines():
    csv_path = os.path.join(BASE_DIR, "engine_specs.csv")
    if not os.path.exists(csv_path):
        print("  engine_specs.csv not found — treating all discovered engines as new")
        return set()
    try:
        df = pd.read_csv(csv_path)
        engines = set(df["engine"].dropna().unique())
        return engines
    except Exception as e:
        logging.error(f"Could not read existing engines: {e}")
        print(f"  Warning: could not read engine_specs.csv ({e})")
        return set()


# ── Wikipedia category search ─────────────────────────────────────────────────

def discover_engines_from_category(category, limit=25):
    """
    Search Wikipedia for pages related to a category seed term.
    Returns a list of page titles that pass the validity filter.
    Uses continuation to pull up to `limit` results.
    """
    discovered = []
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": category,
            "format": "json",
            "srlimit": min(limit, 50),   # API max per call is 50
        }
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"},
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
        logging.error(f"Discovery failed for '{category}': {e}")

    return discovered


# ── Variant expansion (mirrors scraper.py logic) ──────────────────────────────

def expand_family_page(title, url):
    """
    Fetch a family page and return its variant sub-pages.
    Falls back to scraping the family page directly if no variants found.
    Returns list of (name, url) tuples to scrape.
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"},
            timeout=10,
        )
        if response.status_code != 200:
            return [(title, url)]

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        variants = extract_variant_pages(soup)

        if variants:
            logging.info(
                f"Family page '{title}' expanded to {len(variants)} variant(s)"
            )
            return variants
        else:
            # No variant links found — scrape as-is
            logging.info(
                f"Family page '{title}' has no variant links — scraping directly"
            )
            return [(title, url)]

    except Exception as e:
        logging.error(f"Could not expand family page '{title}': {e}")
        return [(title, url)]


# ── Main runner ───────────────────────────────────────────────────────────────

def run_discovery():
    print(f"Starting discovery at {datetime.now()}")
    logging.info("Discovery started")

    existing = get_existing_engines()
    existing_normalized = {normalize(e) for e in existing}
    print(f"Currently have {len(existing)} engines in database")

    # ── Step 1: Collect candidate titles from all seed categories ────────────
    all_discovered = []
    for category in SEED_CATEGORIES:
        print(f"  Searching: {category}...")
        found = discover_engines_from_category(category, limit=50)
        print(f"    → {len(found)} candidates")
        all_discovered.extend(found)

    # Deduplicate by normalized name
    seen = set()
    deduped = []
    for title in all_discovered:
        n = normalize(title)
        if n not in seen:
            seen.add(n)
            deduped.append(title)
    all_discovered = deduped

    print(f"\nTotal unique candidates: {len(all_discovered)}")

    # ── Step 2: Filter out engines already in the database ───────────────────
    new_engines = [
        e for e in all_discovered
        if normalize(e) not in existing_normalized
    ]
    print(f"New engines not yet in database: {len(new_engines)}")

    if not new_engines:
        print("No new engines found — database is up to date")
        logging.info("Discovery complete: no new engines found")
        return

    # ── Step 3: Scrape each new engine, expanding family pages ───────────────
    new_data = []
    scrape_targets = []   # list of (name, url)

    for engine_title in new_engines:
        print(f"\n  Looking up: {engine_title}")
        url = search_wikipedia(engine_title)
        if not url:
            print(f"    → No Wikipedia URL found")
            logging.warning(f"No URL found for '{engine_title}'")
            continue

        # If it's a family page, expand to variants before scraping
        if is_family_page(engine_title):
            print(f"    → Family page detected, expanding variants...")
            targets = expand_family_page(engine_title, url)
            for name, target_url in targets:
                print(f"      → {name}")
            scrape_targets.extend(targets)
        else:
            scrape_targets.append((engine_title, url))

    # Deduplicate scrape targets by URL
    seen_urls = set()
    unique_targets = []
    for name, url in scrape_targets:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_targets.append((name, url))
    scrape_targets = unique_targets

    print(f"\nScraping {len(scrape_targets)} target pages...")

    for name, url in scrape_targets:
        print(f"  Scraping: {name}  ({url})")
        data = scrape_engine(name, url)
        new_data.extend(data)
        if data:
            logging.info(f"Added: '{name}' — {len(data)} rows")

    # ── Step 4: Merge into engine_specs.csv ──────────────────────────────────
    if new_data:
        csv_path = os.path.join(BASE_DIR, "engine_specs.csv")
        new_df = pd.DataFrame(new_data)

        if os.path.exists(csv_path):
            existing_df = pd.read_csv(csv_path)
            combined = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined = new_df

        combined = combined.drop_duplicates(
            subset=["engine", "variant", "spec"], keep="first"
        )
        combined.to_csv(csv_path, index=False)
        combined.to_excel(
            os.path.join(BASE_DIR, "engine_specs.xlsx"), index=False
        )

        print(f"\nDone — added {len(new_data)} rows from {len(scrape_targets)} pages")
        logging.info(
            f"Discovery complete: {len(new_data)} new rows, "
            f"{len(scrape_targets)} pages scraped"
        )
    else:
        print("\nDiscovery found candidates but scraped no data")
        logging.warning("Discovery complete: candidates found but no data scraped")


if __name__ == "__main__":
    run_discovery()
