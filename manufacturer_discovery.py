"""
manufacturer_discovery.py — Phase 1: Manufacturer → Car Model Discovery

For each manufacturer seed:
1. Finds the manufacturer's Wikipedia page
2. Extracts all car models mentioned
3. Tags each as performance/sports/muscle/jdm/hypercar/standard/truck/suv
4. Tier 1 (performance) → immediate scrape queue
5. Tier 2 (standard/truck/suv) → discovery_queue.txt for future runs

Output:
  scrape_queue.csv      — cars to scrape now (Tier 1)
  discovery_queue.txt   — cars to scrape later (Tier 2)
"""

import os
import re
import csv
import logging
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "manufacturer_discovery.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ── Manufacturer seeds ────────────────────────────────────────────────────────

MANUFACTURERS = [
    # JDM / Asian
    {"name": "Toyota",       "region": "JDM",      "wiki": "Toyota"},
    {"name": "Nissan",       "region": "JDM",      "wiki": "Nissan"},
    {"name": "Honda",        "region": "JDM",      "wiki": "Honda"},
    {"name": "Subaru",       "region": "JDM",      "wiki": "Subaru"},
    {"name": "Mitsubishi",   "region": "JDM",      "wiki": "Mitsubishi_Motors"},
    {"name": "Mazda",        "region": "JDM",      "wiki": "Mazda"},
    {"name": "Lexus",        "region": "JDM",      "wiki": "Lexus"},
    {"name": "Acura",        "region": "JDM",      "wiki": "Acura"},
    {"name": "Infiniti",     "region": "JDM",      "wiki": "Infiniti"},
    {"name": "Suzuki",       "region": "JDM",      "wiki": "Suzuki"},
    {"name": "Hyundai",      "region": "JDM",      "wiki": "Hyundai_Motor_Company"},
    {"name": "Kia",          "region": "JDM",      "wiki": "Kia_Corporation"},
    {"name": "Genesis",      "region": "JDM",      "wiki": "Genesis_Motor"},
    # American
    {"name": "Ford",         "region": "American", "wiki": "Ford_Motor_Company"},
    {"name": "Chevrolet",    "region": "American", "wiki": "Chevrolet"},
    {"name": "Dodge",        "region": "American", "wiki": "Dodge"},
    {"name": "Cadillac",     "region": "American", "wiki": "Cadillac"},
    {"name": "Jeep",         "region": "American", "wiki": "Jeep"},
    {"name": "Ram",          "region": "American", "wiki": "Ram_Trucks"},
    {"name": "Lincoln",      "region": "American", "wiki": "Lincoln_Motor_Company"},
    {"name": "Buick",        "region": "American", "wiki": "Buick"},
    {"name": "Pontiac",      "region": "American", "wiki": "Pontiac"},
    # European — German
    {"name": "BMW",          "region": "European", "wiki": "BMW"},
    {"name": "Mercedes-Benz","region": "European", "wiki": "Mercedes-Benz"},
    {"name": "Audi",         "region": "European", "wiki": "Audi"},
    {"name": "Porsche",      "region": "European", "wiki": "Porsche"},
    {"name": "Volkswagen",   "region": "European", "wiki": "Volkswagen"},
    # European — Italian
    {"name": "Ferrari",      "region": "European", "wiki": "Ferrari"},
    {"name": "Lamborghini",  "region": "European", "wiki": "Lamborghini"},
    {"name": "Maserati",     "region": "European", "wiki": "Maserati"},
    {"name": "Alfa Romeo",   "region": "European", "wiki": "Alfa_Romeo"},
    {"name": "FIAT",         "region": "European", "wiki": "Fiat_Automobiles"},
    {"name": "Lancia",       "region": "European", "wiki": "Lancia"},
    {"name": "Pagani",       "region": "European", "wiki": "Pagani"},
    # European — British
    {"name": "McLaren",      "region": "European", "wiki": "McLaren_Automotive"},
    {"name": "Aston Martin", "region": "European", "wiki": "Aston_Martin"},
    {"name": "Jaguar",       "region": "European", "wiki": "Jaguar_Cars"},
    {"name": "Lotus",        "region": "European", "wiki": "Lotus_Cars"},
    # European — French
    {"name": "Renault",      "region": "European", "wiki": "Renault"},
    {"name": "Peugeot",      "region": "European", "wiki": "Peugeot"},
    {"name": "Citroën",      "region": "European", "wiki": "Citroën"},
    # European — Other
    {"name": "Koenigsegg",   "region": "European", "wiki": "Koenigsegg"},
    {"name": "Bugatti",      "region": "European", "wiki": "Bugatti_Automobiles"},
    {"name": "Volvo",        "region": "European", "wiki": "Volvo_Cars"},
    {"name": "Seat",         "region": "European", "wiki": "SEAT"},
]

# ── Performance keywords ──────────────────────────────────────────────────────
# Used to classify cars into tiers

PERFORMANCE_SIGNALS = {
    "hypercar":    ["chiron", "veyron", "laferrari", "p1", "918", "huayra", "agera",
                    "regera", "jesko", "one-77", "valkyrie", "speedtail"],
    "supercar":    ["aventador", "huracan", "murcielago", "gallardo", "enzo", "f40",
                    "f50", "458", "488", "sf90", "720s", "570s", "mclaren f1",
                    "carrera gt", "viper", "gt", "nsx", "lfa"],
    "sports":      ["supra", "rx-7", "rx7", "s2000", "86", "brz", "gr86", "mx-5",
                    "miata", "cayman", "boxster", "z4", "slk", "slc", "tt",
                    "370z", "350z", "300zx", "240sx", "silvia", "celica",
                    "elise", "exige", "emira", "evora", "lotus"],
    "performance": ["m3", "m4", "m5", "m6", "m8", "m2", "rs3", "rs4", "rs5", "rs6",
                    "rs7", "r8", "c63", "e63", "s63", "amg", "type r", "type-r",
                    "gti", "golf r", "megane rs", "clio rs", "focus rs", "focus st",
                    "mustang gt", "mustang shelby", "camaro ss", "camaro z28",
                    "camaro zl1", "challenger", "charger", "corvette", "ct5-v",
                    "cts-v", "lancer evo", "impreza wrx", "wrx sti", "sti",
                    "stinger", "genesis g70", "elantra n", "i30n", "civic si",
                    "integra type r", "skyline", "gt-r", "gtr", "alpine"],
    "muscle":      ["mustang", "camaro", "challenger", "charger", "firebird",
                    "trans am", "gto", "el camino", "chevelle", "nova ss",
                    "barracuda", "cuda", "roadrunner"],
    "jdm_iconic":  ["2jz", "rb26", "sr20", "evo", "evolution", "impreza",
                    "nsx", "supra", "silvia", "180sx", "rx-7", "s2000",
                    "civic type r", "integra", "sw20", "ae86"],
}

TIER2_SIGNALS = ["van", "minivan", "pickup", "truck", "suv", "crossover",
                 "sedan", "saloon", "hatchback", "wagon", "estate", "mpv",
                 "people carrier", "transit", "sprinter", "econoline",
                 "f-150", "f-250", "tacoma", "tundra", "hilux", "land cruiser",
                 "rav4", "cr-v", "hr-v", "qashqai", "tiguan", "touareg",
                 "prius", "corolla", "civic", "accord", "camry", "fusion",
                 "focus", "fiesta", "golf", "polo", "passat", "jetta"]

# Not cars at all
BLACKLIST_SIGNALS = ["concept only", "racing only", "prototype", "one-off",
                     "show car", "study", "formula", "f1", "formula 1",
                     "motorcycle", "bike", "truck", "bus", "commercial"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def classify_car(car_name):
    """
    Returns (tier, category):
      tier 1 = scrape now
      tier 2 = queue for later
    """
    name_lower = car_name.lower()

    # Blacklist check first
    if any(s in name_lower for s in BLACKLIST_SIGNALS):
        return None, None

    # Check performance tiers
    for category, signals in PERFORMANCE_SIGNALS.items():
        if any(s in name_lower for s in signals):
            return 1, category

    # Check tier 2
    if any(s in name_lower for s in TIER2_SIGNALS):
        return 2, "standard"

    # Default — uncertain, queue for later review
    # Better to miss something than flood with trash
    return 2, "unknown"


def fetch_wiki_page(wiki_title):
    url = f"https://en.wikipedia.org/wiki/{wiki_title}"
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"},
            timeout=15
        )
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser"), url
    except Exception as e:
        logging.error(f"Failed to fetch {wiki_title}: {e}")
    return None, url


# Words that indicate a link is NOT a car model
NON_MODEL_WORDS = {
    "list", "category", "history", "production", "company", "corporation",
    "motors", "automotive", "group", "holdings", "limited", "inc", "llc",
    "racing", "motorsport", "formula", "championship", "series", "team",
    "engine", "platform", "transmission", "technology", "design", "studio",
    "concept", "prototype", "show", "exhibit", "museum", "factory", "plant",
    "recall", "lawsuit", "executive", "ceo", "founder", "merger", "acquisition",
    "wikipedia", "portal", "template", "talk", "user", "file", "help",
    "international", "worldwide", "global", "division", "subsidiary",
    "joint venture", "partnership", "alliance", "brand",
}

# A link must contain the manufacturer name OR look like a real model name
# Real model names: contain digits, or are short alphanumeric codes
def looks_like_car_model(name, mfr_lower):
    """Return True if the name looks like a car model."""
    name_lower = name.lower().strip()

    # Too short or too long
    if len(name) < 2 or len(name) > 60:
        return False

    # Contains non-model words
    for word in NON_MODEL_WORDS:
        if word in name_lower:
            return False

    # Must start with uppercase or digit
    if not re.match(r'[A-Z0-9]', name):
        return False

    # Contains manufacturer name — likely a model page
    if mfr_lower in name_lower:
        return True

    # Looks like a model code: letters+digits (M3, 911, GR86, RS6, GT-R)
    if re.search(r'[A-Z]+\d|\d+[A-Z]', name):
        return True

    # Contains displacement hint (5.0, 3.8L, V8, V12)
    if re.search(r'\d+\.\d|[Vv]\d{1,2}\b', name):
        return True

    # Short all-caps or mixed code (GTS, AMG, STI, WRX)
    if re.match(r'[A-Z0-9]{2,8}$', name):
        return True

    return False


def extract_car_models(soup, manufacturer_name):
    """
    Extract car model names from a manufacturer Wikipedia page.
    Uses strict filtering to only return actual car model names.
    """
    car_models = []
    seen = set()
    mfr_lower = manufacturer_name.lower()

    def _add(name, source=""):
        name = name.strip()
        key  = name.lower()
        if key in seen:
            return
        if not looks_like_car_model(name, mfr_lower):
            return
        seen.add(key)
        car_models.append({"model": name, "source": source})

    # ── Strategy 1: Model/Vehicle section headers ─────────────────────────────
    model_section_keywords = {
        "models", "vehicles", "current models", "past models",
        "current vehicles", "discontinued models", "lineup", "automobiles",
        "production vehicles", "road cars", "production cars", "products"
    }

    for header in soup.find_all(["h2", "h3", "h4"]):
        header_text = re.sub(r'\[.*?\]', '', header.get_text(strip=True)).lower()
        if not any(kw in header_text for kw in model_section_keywords):
            continue
        for sibling in header.find_next_siblings():
            if sibling.name in ["h2", "h3"] and sibling != header:
                break
            for a in sibling.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("/wiki/") or ":" in href[6:]:
                    continue
                _add(a.get_text(strip=True), source="section")

    # ── Strategy 2: Navbox tables (manufacturer-specific only) ────────────────
    for table in soup.find_all("table"):
        classes = " ".join(table.get("class", []))
        if "navbox" not in classes:
            continue
        table_text = table.get_text().lower()
        # Must be about this manufacturer
        if mfr_lower not in table_text[:300]:
            continue
        # Skip if it's a general industry/racing navbox
        if any(w in table_text[:300] for w in ["formula 1", "motorsport", "racing series"]):
            continue
        for a in table.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("/wiki/") or ":" in href[6:]:
                continue
            _add(a.get_text(strip=True), source="navbox")

    return car_models


def search_wikipedia(query):
    """Search Wikipedia and return the best matching URL."""
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1
        }
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"}
        )
        data = r.json()
        results = data.get("query", {}).get("search", [])
        if results:
            title = results[0]["title"]
            return title, f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
    except Exception as e:
        logging.error(f"Search failed for {query}: {e}")
    return None, None


# ── Main runner ───────────────────────────────────────────────────────────────

def run_manufacturer_discovery():
    print(f"Starting manufacturer discovery at {datetime.now()}")
    print(f"Processing {len(MANUFACTURERS)} manufacturers...")
    logging.info("Manufacturer discovery started")

    scrape_queue   = []   # Tier 1 — scrape now
    discovery_queue = []  # Tier 2 — scrape later

    for mfr in MANUFACTURERS:
        name   = mfr["name"]
        region = mfr["region"]
        wiki   = mfr["wiki"]

        print(f"\n  {name} ({region})")
        soup, url = fetch_wiki_page(wiki)

        if not soup:
            print(f"    Could not fetch page")
            logging.warning(f"Could not fetch {wiki}")
            continue

        models = extract_car_models(soup, name)
        print(f"    Found {len(models)} candidate models")

        tier1_count = 0
        tier2_count = 0

        for model_info in models:
            model_name = model_info["model"]
            tier, category = classify_car(model_name)

            if tier is None:
                continue

            entry = {
                "manufacturer": name,
                "region":       region,
                "model":        model_name,
                "category":     category,
                "wiki_source":  url,
                "discovered_at": datetime.now().isoformat(),
            }

            if tier == 1:
                scrape_queue.append(entry)
                tier1_count += 1
            else:
                discovery_queue.append(entry)
                tier2_count += 1

        print(f"    Tier 1 (scrape now): {tier1_count} | Tier 2 (queue): {tier2_count}")
        logging.info(f"{name}: {tier1_count} tier1, {tier2_count} tier2")

    # ── Save scrape queue ─────────────────────────────────────────────────────
    scrape_queue_path = os.path.join(BASE_DIR, "scrape_queue.csv")
    if scrape_queue:
        # Merge with existing queue if present
        new_df = pd.DataFrame(scrape_queue)
        if os.path.exists(scrape_queue_path):
            existing = pd.read_csv(scrape_queue_path)
            combined = pd.concat([existing, new_df], ignore_index=True)
            combined = combined.drop_duplicates(
                subset=["manufacturer", "model"], keep="first"
            )
        else:
            combined = new_df
        combined.to_csv(scrape_queue_path, index=False)
        print(f"\nScrape queue: {len(scrape_queue)} new entries → {scrape_queue_path}")

    # ── Save discovery queue ──────────────────────────────────────────────────
    discovery_queue_path = os.path.join(BASE_DIR, "discovery_queue.txt")
    if discovery_queue:
        with open(discovery_queue_path, "a") as f:
            for entry in discovery_queue:
                f.write(
                    f"{datetime.now().isoformat()} | "
                    f"{entry['manufacturer']} | "
                    f"{entry['model']} | "
                    f"{entry['category']} | "
                    f"tier2\n"
                )
        print(f"Discovery queue: {len(discovery_queue)} entries appended → {discovery_queue_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"Total tier 1 (scrape now): {len(scrape_queue)}")
    print(f"Total tier 2 (queue later): {len(discovery_queue)}")

    if scrape_queue:
        df = pd.DataFrame(scrape_queue)
        print(f"\nTier 1 by category:")
        print(df["category"].value_counts().to_string())
        print(f"\nTier 1 by manufacturer:")
        print(df["manufacturer"].value_counts().head(10).to_string())

    logging.info(
        f"Discovery complete: {len(scrape_queue)} tier1, "
        f"{len(discovery_queue)} tier2"
    )
    return scrape_queue, discovery_queue


if __name__ == "__main__":
    run_manufacturer_discovery()
