"""
generation_scraper.py — Phase 2: Car Generation + Trim Scraper

For each car in scrape_queue.csv:
1. Finds the car's Wikipedia page
2. Detects if multiple generations exist (links to gen-specific pages)
3. For each generation page — scrapes infobox for all engine/trim combos
4. Writes one row per vehicle/generation/trim/engine combo

Output:
  raw_vehicle_specs.csv — one row per car/gen/trim/engine combination
"""

import os
import re
import logging
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "generation_scraper.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"}

# ── Generation detection patterns ────────────────────────────────────────────

# Matches Wikipedia generation page title patterns:
# "Ford Mustang (first generation)"
# "BMW M3 (E46)"
# "Toyota Supra (A80)"
# "Nissan GT-R (R35)"
GEN_PAGE_PATTERNS = [
    r'(?:first|second|third|fourth|fifth|sixth|seventh|eighth)\s+generation',
    r'\([A-Z]\d{2,3}\)',          # (E46), (R34), (A80)
    r'\([A-Z]\d{2}/[A-Z]{2}\)',   # (J29/DB)
    r'\(W\d{3}\)',                 # Mercedes (W205)
    r'\(F\d{2,3}\)',               # BMW (F80)
    r'\(G\d{2,3}\)',               # BMW (G80)
    r'\(S\d{3}\)',                 # Mustang (S550)
    r'\([A-Z]{2}\d{2,3}\)',        # (GR86), (MK4)
    r'mk\d|mark\s+\d',            # MK4, Mark 4
    r'\(\d{4}[–-]\d{4}\)',        # (1993–2002)
    r'\(\d{4}[–-]present\)',      # (2019–present)
]

# Generation ordinal words → numbers
GEN_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4,
    "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4,
    "5th": 5, "6th": 6, "7th": 7, "8th": 8,
}

# Known chassis code → generation number mappings
CHASSIS_GEN_MAP = {
    # BMW M3
    "e30": 1, "e36": 2, "e46": 3, "e90": 4, "e92": 4, "e93": 4,
    "f80": 5, "g80": 6,
    # BMW M5
    "e28": 1, "e34": 2, "e39": 3, "e60": 4, "f10": 5, "f90": 6,
    # Ford Mustang
    "s197": 5, "s550": 6, "s650": 7,
    # Toyota Supra
    "a40": 1, "a50": 1, "a60": 2, "a70": 3, "a80": 4, "j29": 5,
    # Nissan Skyline GT-R
    "r32": 1, "r33": 2, "r34": 3, "r35": 4,
    # Porsche 911
    "996": 4, "997": 5, "991": 6, "992": 7,
}


# ── Value extraction helpers ──────────────────────────────────────────────────

def extract_power_hp(text):
    """Extract HP from infobox power field, handling kW/PS/bhp."""
    if not text:
        return None
    text = text.replace(",", "")
    for pattern, mult in [
        (r'(\d{2,4})\s*(?:hp|bhp)',  1.0),
        (r'(\d{2,4})\s*ps',          0.9863),
        (r'(\d{2,4})\s*kw',          1.341),
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = round(float(m.group(1)) * mult, 1)
            if 30 < val < 3000:
                return val
    return None


def extract_all_power_values(text):
    """
    Extract ALL power values from a field — handles multiple engines/trims.
    '435 hp (GT), 526 hp (GT350), 760 hp (GT500)'
    Returns list of (power_hp, trim_hint) tuples.
    """
    if not text:
        return []
    results = []
    text_clean = text.replace(",", "")

    # Try to find power + trim pairs
    # Pattern: number unit (optional trim name)
    for pattern, mult in [
        (r'(\d{2,4})\s*(?:hp|bhp)\s*(?:\(([^)]+)\))?', 1.0),
        (r'(\d{2,4})\s*ps\s*(?:\(([^)]+)\))?',          0.9863),
        (r'(\d{2,4})\s*kw\s*(?:\(([^)]+)\))?',          1.341),
    ]:
        for m in re.finditer(pattern, text_clean, re.IGNORECASE):
            val = round(float(m.group(1)) * mult, 1)
            if 30 < val < 3000:
                trim_hint = m.group(2).strip() if m.group(2) else None
                results.append((val, trim_hint))

    # Deduplicate by power value
    seen = set()
    deduped = []
    for val, trim in results:
        if val not in seen:
            seen.add(val)
            deduped.append((val, trim))
    return deduped


def extract_displacement_cc(text):
    """Extract displacement in cc from infobox field."""
    if not text:
        return None
    text = text.replace(",", "")
    # Prefer explicit cc
    m = re.search(r'([\d.]+)\s*(?:cc|cm³|cm3)', text, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        if 50 < val < 15000:
            return round(val, 0)
    # Fall back to litres
    m = re.search(r'(\d+\.?\d*)\s*[Ll](?:itre|iter)?', text)
    if m:
        val = float(m.group(1))
        if 0.5 < val < 15:
            return round(val * 1000, 0)
    return None


def extract_years(text):
    """Extract year_start, year_end from production field."""
    if not text:
        return None, None
    m = re.search(r'((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'((?:19|20)\d{2})\s*[-–]\s*present', text, re.IGNORECASE)
    if m:
        return int(m.group(1)), None
    m = re.search(r'((?:19|20)\d{2})', text)
    if m:
        return int(m.group(1)), None
    return None, None


def extract_torque_nm(text):
    """Extract torque in Nm."""
    if not text:
        return None
    text = text.replace(",", "")
    for pattern, mult in [
        (r'(\d{2,4})\s*(?:nm|n·m|newton)',  1.0),
        (r'(\d{2,4})\s*(?:lb.?ft|lbf)',     1.3558),
        (r'(\d{2,4})\s*(?:kgm|kgf)',        9.807),
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = round(float(m.group(1)) * mult, 1)
            if 10 < val < 5000:
                return val
    return None


def detect_generation_number(page_title, page_text=""):
    """
    Infer generation number from page title or content.
    Returns int or None.
    """
    title_lower = page_title.lower()

    # Ordinal words
    for word, num in GEN_ORDINALS.items():
        if word in title_lower:
            return num

    # Chassis codes
    for code, num in CHASSIS_GEN_MAP.items():
        if code in title_lower:
            return num

    # Chassis code in parentheses e.g. (E46)
    m = re.search(r'\(([a-zA-Z]\d{2,3})\)', page_title)
    if m:
        code = m.group(1).lower()
        if code in CHASSIS_GEN_MAP:
            return CHASSIS_GEN_MAP[code]

    return None


# ── Wikipedia fetching ────────────────────────────────────────────────────────

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        logging.error(f"Fetch failed for {url}: {e}")
    return None


def search_wikipedia(query):
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 3,
        }
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            timeout=10,
            headers=HEADERS,
        )
        data = r.json()
        results = data.get("query", {}).get("search", [])
        return [(r["title"], f"https://en.wikipedia.org/wiki/{r['title'].replace(' ', '_')}")
                for r in results]
    except Exception as e:
        logging.error(f"Search failed for {query}: {e}")
    return []


def get_page_title(soup):
    tag = soup.find("h1", {"id": "firstHeading"})
    return tag.get_text(strip=True) if tag else None


# ── Generation page detection ─────────────────────────────────────────────────

def is_generation_page_link(title):
    """Return True if this Wikipedia title looks like a generation-specific page."""
    title_lower = title.lower()
    for pattern in GEN_PAGE_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    return False


def find_generation_pages(soup, car_name):
    """
    From a car's main Wikipedia page, find links to generation-specific pages.
    Returns list of (title, url, gen_number) tuples.
    """
    gen_pages = []
    seen_urls = set()
    car_lower = car_name.lower().split("(")[0].strip()

    # Look for generation links in the page body and infobox
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/wiki/"):
            continue
        if ":" in href[6:]:
            continue

        link_text = a.get_text(strip=True)
        full_url  = "https://en.wikipedia.org" + href
        title     = href[6:].replace("_", " ")

        if full_url in seen_urls:
            continue

        # Must reference the same car
        if car_lower not in title.lower() and car_lower not in link_text.lower():
            continue

        if is_generation_page_link(title) or is_generation_page_link(link_text):
            seen_urls.add(full_url)
            gen_num = detect_generation_number(title)
            gen_pages.append((title, full_url, gen_num))

    return gen_pages


# ── Infobox scraping ──────────────────────────────────────────────────────────

def scrape_infobox(soup):
    """
    Extract key fields from a Wikipedia car infobox.
    Returns dict of raw field values.
    """
    fields = {}

    infobox = (
        soup.find("table", class_=lambda c: c and "infobox" in " ".join(c))
    )
    if not infobox:
        return fields

    for row in infobox.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if not th or not td:
            continue
        key   = re.sub(r'\[.*?\]', '', th.get_text(strip=True)).lower().strip()
        value = re.sub(r'\[.*?\]', '', td.get_text(" ", strip=True)).strip()
        if key and value:
            fields[key] = value

    return fields


def parse_engine_trims(fields, manufacturer, car_name, gen_label):
    """
    From infobox fields, extract one row per engine/trim combination.

    Handles pages with multiple engines listed in the engine field:
    'engine: 5.0L V8 (GT)\n5.2L V8 flat-plane (GT350)\n5.2L supercharged V8 (GT500)'
    """
    rows = []

    # Extract base fields
    production_text = fields.get("production", "") or fields.get("model years", "")
    year_start, year_end = extract_years(production_text)

    # Engine field — may have multiple engines
    engine_text = (
        fields.get("engine", "") or
        fields.get("powertrain", "") or
        fields.get("engine(s)", "") or ""
    )

    # Power field
    power_text = (
        fields.get("power output", "") or
        fields.get("power", "") or
        fields.get("maximum power", "") or
        fields.get("max power", "") or ""
    )

    # Torque field
    torque_text = (
        fields.get("torque", "") or
        fields.get("max torque", "") or
        fields.get("maximum torque", "") or ""
    )

    # Displacement
    displacement_text = (
        fields.get("displacement", "") or
        fields.get("engine displacement", "") or
        fields.get("capacity", "") or ""
    )

    # Layout/config
    layout = (
        fields.get("layout", "") or
        fields.get("engine configuration", "") or
        fields.get("configuration", "") or ""
    )

    # Body style
    body_style = fields.get("body style", "") or fields.get("body styles", "") or ""

    # Get all power values — one row per distinct power figure
    power_values = extract_all_power_values(power_text)

    if not power_values:
        # Single row even without power data
        power_values = [(None, None)]

    # Get all engine names from the engine field
    engine_names = []
    if engine_text:
        # Split on newlines or bullet points
        parts = re.split(r'\n|•|·', engine_text)
        for part in parts:
            part = part.strip()
            if part and len(part) > 3:
                engine_names.append(part)
    if not engine_names:
        engine_names = [engine_text or ""]

    # If multiple power values AND multiple engines — try to pair them
    # Otherwise use all engines for each power value
    if len(power_values) == len(engine_names) and len(power_values) > 1:
        pairs = list(zip(engine_names, power_values))
    else:
        # Cross product — one row per engine per power value
        # But if too many combinations, just use first engine + all powers
        if len(engine_names) > 1 and len(power_values) > 1:
            pairs = [(eng, (None, None)) for eng in engine_names]
            for _, (pwr, trim) in zip(engine_names, power_values):
                pass
            # Just pair sequentially up to min length
            pairs = list(zip(
                engine_names[:len(power_values)],
                power_values
            ))
            # Add remaining engines without power
            for eng in engine_names[len(power_values):]:
                pairs.append((eng, (None, None)))
        else:
            pairs = [(engine_names[0] if engine_names else "", pv)
                     for pv in power_values]

    for engine_raw, (power_hp, trim_hint) in pairs:
        # Clean engine name
        engine_clean = re.sub(r'\[.*?\]', '', str(engine_raw)).strip()
        engine_clean = re.sub(r'\s+', ' ', engine_clean)[:100]

        # Displacement
        disp_cc = extract_displacement_cc(displacement_text)
        if not disp_cc:
            disp_cc = extract_displacement_cc(engine_clean)

        # Torque
        torque_nm = extract_torque_nm(torque_text)

        # Trim label
        trim_label = trim_hint or ""

        row = {
            "manufacturer":   manufacturer,
            "vehicle":        car_name,
            "generation":     gen_label,
            "trim":           trim_label,
            "engine":         engine_clean,
            "year_start":     year_start,
            "year_end":       year_end,
            "power_hp":       power_hp,
            "torque_nm":      torque_nm,
            "displacement_cc":disp_cc,
            "layout":         layout[:80] if layout else None,
            "body_style":     body_style[:80] if body_style else None,
            "confidence":     "wikipedia_scraped",
            "source":         "",  # filled by caller
            "scraped_at":     datetime.now().isoformat(),
        }
        rows.append(row)

    return rows


# ── Core scraper ──────────────────────────────────────────────────────────────

def scrape_car(manufacturer, model_name, region="Unknown"):
    """
    Scrape all generations of a car model.
    Returns list of raw spec rows.
    """
    all_rows = []

    print(f"  Scraping: {manufacturer} {model_name}")

    # Find the car's Wikipedia page
    search_results = search_wikipedia(f"{manufacturer} {model_name}")
    if not search_results:
        print(f"    No Wikipedia results found")
        logging.warning(f"No Wikipedia results for {manufacturer} {model_name}")
        return []

    main_title, main_url = search_results[0]
    main_soup = fetch_page(main_url)
    if not main_soup:
        return []

    actual_title = get_page_title(main_soup) or main_title
    print(f"    Found: {actual_title}")

    # ── Check for generation pages ────────────────────────────────────────────
    gen_pages = find_generation_pages(main_soup, actual_title)

    if gen_pages:
        print(f"    {len(gen_pages)} generation page(s) found")
        for gen_title, gen_url, gen_num in gen_pages:
            gen_label = f"Gen {gen_num}" if gen_num else gen_title
            print(f"      → {gen_label}: {gen_title}")

            gen_soup = fetch_page(gen_url)
            if not gen_soup:
                continue

            fields = scrape_infobox(gen_soup)
            if not fields:
                logging.warning(f"No infobox found for {gen_title}")
                continue

            rows = parse_engine_trims(
                fields, manufacturer, actual_title, gen_label
            )
            for r in rows:
                r["source"] = gen_url
            all_rows.extend(rows)
            print(f"        {len(rows)} trim/engine row(s)")

    else:
        # No generation pages — scrape the main page directly
        print(f"    No generation pages — scraping main page")
        fields = scrape_infobox(main_soup)
        if fields:
            rows = parse_engine_trims(
                fields, manufacturer, actual_title, "base"
            )
            for r in rows:
                r["source"] = main_url
            all_rows.extend(rows)
            print(f"    {len(rows)} trim/engine row(s)")

    logging.info(f"{manufacturer} {model_name}: {len(all_rows)} rows")
    return all_rows


# ── Runner ────────────────────────────────────────────────────────────────────

def run_generation_scraper(limit=None):
    """
    Read scrape_queue.csv and scrape each car.
    limit: max number of cars to process (None = all)
    """
    print(f"Starting generation scraper at {datetime.now()}")
    logging.info("Generation scraper started")

    queue_path = os.path.join(BASE_DIR, "scrape_queue.csv")
    if not os.path.exists(queue_path):
        print(f"ERROR: {queue_path} not found — run manufacturer_discovery.py first")
        return []

    queue_df = pd.read_csv(queue_path)
    print(f"Loaded {len(queue_df)} cars from scrape queue")

    if limit:
        queue_df = queue_df.head(limit)
        print(f"Processing first {limit} cars (limit set)")

    all_rows = []
    processed = 0
    failed = 0

    for _, row in queue_df.iterrows():
        manufacturer = str(row.get("manufacturer", "")).strip()
        model        = str(row.get("model", "")).strip()
        region       = str(row.get("region", "Unknown")).strip()

        if not manufacturer or not model:
            continue

        try:
            rows = scrape_car(manufacturer, model, region)
            all_rows.extend(rows)
            processed += 1
        except Exception as e:
            logging.error(f"Failed to scrape {manufacturer} {model}: {e}")
            failed += 1

    # ── Save raw vehicle specs ────────────────────────────────────────────────
    output_path = os.path.join(BASE_DIR, "raw_vehicle_specs.csv")

    if all_rows:
        new_df = pd.DataFrame(all_rows)

        if os.path.exists(output_path):
            existing = pd.read_csv(output_path)
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            combined = new_df

        combined.to_csv(output_path, index=False)
        print(f"\nSaved {len(all_rows)} rows → {output_path}")
        print(f"Total in file: {len(combined)} rows")
    else:
        print("\nNo data scraped")

    print(f"\nProcessed: {processed} cars | Failed: {failed}")
    logging.info(
        f"Generation scraper complete: {len(all_rows)} rows, "
        f"{processed} cars, {failed} failed"
    )
    return all_rows


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_generation_scraper(limit=limit)
