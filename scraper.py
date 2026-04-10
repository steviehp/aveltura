import requests
import time
from bs4 import BeautifulSoup
import pandas as pd
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "scraper.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

ENGINES = [
    # JDM
    "Toyota JZ engine",
    "Nissan SR engine",
    "Nissan RB engine",
    "Honda K engine",
    "Honda B engine",
    "Mitsubishi Sirius engine",
    "Subaru EJ engine",
    "Nissan VQ engine",
    "Honda F20C engine",
    "Toyota 2GR engine",
    "Nissan KA engine",
    "Honda J engine",
    "Toyota 1UR engine",
    "Subaru FA engine",
    "Mitsubishi 4B11 engine",
    # American
    "GM LS engine",
    "Chrysler Hemi engine",
    "Ford Modular engine",
    "Cadillac Northstar engine",
    "Ford Coyote engine",
    "Chevrolet Small-Block engine",
    "Ford Windsor engine",
    "Chrysler LA engine",
    "Buick 3800 engine",
    "Ford FE engine",
    "Dodge Viper V10 engine",
    "Chevrolet Big-Block engine",
    # European
    "BMW M54 engine",
    "BMW S54 engine",
    "BMW S65 engine",
    "BMW N54 engine",
    "BMW N55 engine",
    "BMW S55 engine",
    "BMW M62 engine",
    "Mercedes-Benz M156 engine",
    "Mercedes-Benz M113 engine",
    "Mercedes-Benz OM642 engine",
    "Audi five-cylinder engine",
    "Audi V8 engine",
    "Porsche flat-six engine",
    "Porsche M96 engine",
    "Volkswagen EA888 engine",
    "Volkswagen VR6 engine",
    "Ferrari F136 engine",
    "Ferrari Colombo engine",
    "Lamborghini V12 engine",
]

# ── Module-level constants ────────────────────────────────────────────────────

INFOBOX_CLASSES = {"infobox", "wikitable", "infobox_v2"}

SPEC_SIGNALS = {
    "displacement", "power", "torque", "bore", "stroke",
    "compression", "configuration", "valvetrain", "fuel",
    "cooling", "manufacturer", "production", "redline",
    "horsepower", "bhp", "hp", "kw", "capacity", "engine type",
}

NAV_SIGNALS = {
    "see also", "references", "external links", "notes",
    "further reading", "history", "racing", "motorsport",
    "applications", "vehicles", "models", "films", "television",
    "people", "locations", "fandom", "media", "management",
}

APPLICATIONS_BLACKLIST = {
    "see also", "references", "external links", "notes", "further reading",
    "history", "overview", "production", "specifications", "performance",
    "variants", "racing", "motorsport", "legacy", "reception",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_engine(title):
    title_lower = title.lower()
    if "list of" in title_lower:
        return False
    if title_lower.startswith("list"):
        return False
    if "disambiguation" in title_lower:
        return False
    if "category:" in title_lower:
        return False
    return True


def is_family_page(title):
    if re.search(r'\d{2,}', title):
        return False
    lower = title.lower()
    if lower.endswith((" engine", " engines")):
        return True
    return False


def get_page_title(soup):
    tag = soup.find("h1", {"id": "firstHeading"})
    if tag:
        return tag.get_text(strip=True)
    return None


def is_spec_table(table):
    classes = table.get("class", [])
    has_infobox_class = False
    for cls in classes:
        if any(infobox_cls in cls.lower() for infobox_cls in INFOBOX_CLASSES):
            has_infobox_class = True
            break

    # Navboxes and model history tables have many rows — real infoboxes don't.
    # Cap at 40 rows: anything larger is almost certainly a navbox or timeline.
    row_count = len(table.find_all("tr"))
    if row_count > 40 and not has_infobox_class:
        return False

    if has_infobox_class:
        return True

    first_col_texts = [
        row.find(["th", "td"]).get_text(strip=True).lower()
        for row in table.find_all("tr")
        if row.find(["th", "td"])
    ]
    if any(any(sig in cell for sig in SPEC_SIGNALS) for cell in first_col_texts):
        return True
    return False


def table_is_after_nav_header(table):
    for elem in table.find_all_previous("h2"):
        text = re.sub(r'\[.*?\]', '', elem.get_text(strip=True)).lower()
        if text in NAV_SIGNALS:
            return True
        return False
    return False


def is_valid_spec_key(key):
    k = key.strip()
    # Anything starting with a 4-digit year is an application row, not a spec
    # Catches both "1994" and "20022005Honda Civic" regardless of length
    if re.match(r'^(19|20)\d{2}', k):
        return False
    # Engine sub-codes e.g. K20A1, M54B30, N55B30
    if re.match(r'^[A-Z][A-Z0-9]{2,11}$', k) and any(c.isdigit() for c in k):
        return False
    # Too long to be a spec name — likely a car name or sentence
    if len(k) > 60:
        return False
    # Short all-caps with no vowels — abbreviation artifact
    if k.isupper() and len(k) <= 4 and not any(v in k for v in "AEIOU"):
        return False
    return True


# ── Variant expansion ─────────────────────────────────────────────────────────

def extract_variant_pages(soup):
    variant_pages = []
    seen_urls = set()
    variant_keys = {"variants", "also called", "also known", "also known as"}

    for row in soup.find_all("tr"):
        cols = row.find_all(["th", "td"])
        if len(cols) < 2:
            continue
        key_text = cols[0].get_text(strip=True).lower()
        if key_text not in variant_keys:
            continue
        for a in cols[1].find_all("a", href=True):
            href = a["href"]
            if not href.startswith("/wiki/"):
                continue
            if ":" in href[6:]:
                continue
            link_title = a.get_text(strip=True)
            full_url = "https://en.wikipedia.org" + href
            if not any(c.isdigit() for c in link_title):
                continue
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            variant_pages.append((link_title, full_url))

    return variant_pages


# ── Value parsing ─────────────────────────────────────────────────────────────

def parse_variant_values(value_str):
    if not value_str or pd.isna(value_str):
        return [("base", value_str)]
    val = str(value_str).strip()

    liter_pattern = re.findall(r'(\d+\.?\d*)\s*[Ll]\s*\(?([\d,]+)\s*cc\)?', val)
    valid_liter = [(l, cc) for l, cc in liter_pattern if float(l) <= 15]
    if len(valid_liter) > 1:
        return [(f"{l}L", f"{cc.replace(',', '')}cc") for l, cc in valid_liter]

    cc_pattern = re.findall(r'([\d,]+)\s*cc', val)
    if len(cc_pattern) > 1:
        results = []
        seen = set()
        for cc in cc_pattern:
            cc_num = int(cc.replace(",", ""))
            if cc_num < 100 or cc_num > 15000:
                continue
            liter = round(cc_num / 1000, 1)
            label = f"{liter}L"
            if label not in seen:
                seen.add(label)
                results.append((label, f"{cc.replace(',', '')}cc"))
        if len(results) > 1:
            return results

    hp_pattern = re.findall(r'([\d,]+)\s*(?:hp|bhp)', val, re.IGNORECASE)
    hp_filtered = [v for v in hp_pattern if int(v.replace(",", "")) >= 50]
    if len(hp_filtered) > 1:
        seen = set()
        results = []
        for v in hp_filtered:
            if v not in seen:
                seen.add(v)
                results.append((f"{v}hp", f"{v}hp"))
        if len(results) > 1:
            return results

    kw_pattern = re.findall(r'([\d,]+)\s*kw', val, re.IGNORECASE)
    kw_filtered = [v for v in kw_pattern if int(v.replace(",", "")) >= 30]
    if len(kw_filtered) > 1:
        seen = set()
        results = []
        for v in kw_filtered:
            if v not in seen:
                seen.add(v)
                results.append((f"{v}kW", f"{v}kW"))
        if len(results) > 1:
            return results

    return [("base", val)]


# ── Applications scraper ──────────────────────────────────────────────────────

def _extract_hp_from_text(text):
    for pattern, multiplier in [
        (r'(\d{2,4})\s*(?:hp|bhp)', 1.0),
        (r'(\d{2,4})\s*ps',         0.9863),
        (r'(\d{2,4})\s*kw',         1.341),
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = round(float(m.group(1)) * multiplier, 1)
            if 30 < val < 2000:
                return val
    return None


def _split_years(text):
    m = re.search(r'((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})', str(text))
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'((?:19|20)\d{2})', str(text))
    if m:
        return int(m.group(1)), None
    return None, None


def _extract_years_from_text(text):
    m = re.search(r'((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})', text)
    if m:
        return f"{m.group(1)}–{m.group(2)}"
    years = re.findall(r'\b((?:19|20)\d{2})\b', text)
    if years:
        years = sorted(set(years))
        return years[0] if len(years) == 1 else f"{years[0]}–{years[-1]}"
    return ""


def scrape_applications(soup, engine_name, url):
    applications = []
    seen = set()

    APPLICATION_HEADERS = {
        "applications", "vehicles", "automobile applications",
        "cars", "vehicle applications", "models", "used in",
    }

    def _add(vehicle_text, years_str, power_hp, notes=""):
        vehicle_text = vehicle_text.strip()
        if not vehicle_text or len(vehicle_text) < 3:
            return
        if vehicle_text.lower() in APPLICATIONS_BLACKLIST:
            return
        if re.match(r'^\d+$', vehicle_text):
            return
        key = (engine_name, vehicle_text[:80])
        if key in seen:
            return
        seen.add(key)
        year_start, year_end = _split_years(years_str)
        applications.append({
            "engine":     engine_name,
            "vehicle":    vehicle_text,
            "year_start": year_start,
            "year_end":   year_end,
            "power_hp":   power_hp,
            "torque_nm":  None,
            "notes":      notes[:120] if notes else "",
            "source":     url,
        })

    for header in soup.find_all(["h2", "h3", "h4"]):
        header_text = re.sub(r'\[.*?\]', '', header.get_text(strip=True)).lower()
        if header_text not in APPLICATION_HEADERS:
            continue

        header_tag = header.name
        stop_tags = {"h2", "h3", "h4"}
        if header_tag == "h3":
            stop_tags = {"h2", "h3"}
        elif header_tag == "h2":
            stop_tags = {"h2"}

        for sibling in header.find_next_siblings():
            if sibling.name in stop_tags:
                break
            for li in sibling.find_all("li"):
                text    = li.get_text(" ", strip=True)
                years   = _extract_years_from_text(text)
                hp      = _extract_hp_from_text(text)
                vehicle = re.split(r'\(|\b(?:19|20)\d{2}\b', text)[0].strip(" –-,")
                if vehicle:
                    _add(vehicle, years, hp, notes=text)
            for row in sibling.find_all("tr"):
                cols = row.find_all(["th", "td"])
                if not cols:
                    continue
                if all(c.name == "th" for c in cols):
                    continue
                texts   = [c.get_text(" ", strip=True) for c in cols]
                full    = " | ".join(texts)
                years   = _extract_years_from_text(full)
                hp      = _extract_hp_from_text(full)
                vehicle = texts[0].strip()
                if vehicle:
                    _add(vehicle, years, hp, notes=full)

    return applications


def save_applications(new_apps, base_dir):
    if not new_apps:
        return 0
    apps_path = os.path.join(base_dir, "engine_applications.csv")
    new_df    = pd.DataFrame(new_apps)
    if os.path.exists(apps_path):
        existing = pd.read_csv(apps_path)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined = combined.drop_duplicates(subset=["engine", "vehicle"], keep="first")
    combined.to_csv(apps_path, index=False)
    return len(new_df)


# ── Core scraper ──────────────────────────────────────────────────────────────

def scrape_engine(engine_name, url, _depth=0, _all_apps=None):
    data    = []
    is_root = _all_apps is None
    if is_root:
        _all_apps = []

    if _depth > 2:
        logging.warning(f"Max recursion depth reached for {engine_name} — skipping")
        return data

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"},
            timeout=10
        )
        if response.status_code != 200:
            logging.warning(f"HTTP {response.status_code} for {url}")
            return data

        soup = BeautifulSoup(response.text, "html.parser")
        actual_name = get_page_title(soup) or engine_name

        # Scrape applications
        apps = scrape_applications(soup, actual_name, url)
        if apps:
            _all_apps.extend(apps)
            print(f"    ✦ {len(apps)} application(s) found for {actual_name}")

        # Family page expansion
        if is_family_page(actual_name):
            variant_pages = extract_variant_pages(soup)
            if variant_pages:
                logging.info(f"'{actual_name}' is a family page → expanding {len(variant_pages)} variant(s)")
                print(f"    ↳ Family page detected ({actual_name}), expanding {len(variant_pages)} variant(s)...")
                for variant_name, variant_url in variant_pages:
                    print(f"      → {variant_name}  ({variant_url})")
                    sub_data = scrape_engine(variant_name, variant_url, _depth + 1, _all_apps)
                    data.extend(sub_data)
                if is_root and _all_apps:
                    saved = save_applications(_all_apps, BASE_DIR)
                    logging.info(f"Saved {saved} application rows for {actual_name} family")
                return data
            else:
                logging.info(f"'{actual_name}' looks like a family page but has no variant links — scraping directly.")

        # Spec table scrape — infobox only
        raw_rows = []
        for table in soup.find_all("table"):
            if not is_spec_table(table):
                continue
            if table_is_after_nav_header(table):
                continue
            for row in table.find_all("tr"):
                cols = row.find_all(["th", "td"])
                if len(cols) >= 2:
                    key   = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    if key and value:
                        raw_rows.append((key, value))

        raw_rows = [(k, v) for k, v in raw_rows if is_valid_spec_key(k)]

        variant_specs = {}
        all_variants  = set()

        for key, value in raw_rows:
            parsed = parse_variant_values(value)
            if len(parsed) > 1:
                variant_specs[key] = parsed
                for variant_name_inner, _ in parsed:
                    all_variants.add(variant_name_inner)

        if all_variants:
            for variant_name_inner in all_variants:
                for key, value in raw_rows:
                    if key in variant_specs:
                        for vname, vvalue in variant_specs[key]:
                            if vname == variant_name_inner:
                                data.append({
                                    "engine":     actual_name,
                                    "variant":    variant_name_inner,
                                    "spec":       key,
                                    "value":      vvalue,
                                    "source":     url,
                                    "scraped_at": datetime.now().isoformat()
                                })
                    else:
                        data.append({
                            "engine":     actual_name,
                            "variant":    variant_name_inner,
                            "spec":       key,
                            "value":      value,
                            "source":     url,
                            "scraped_at": datetime.now().isoformat()
                        })
        else:
            for key, value in raw_rows:
                data.append({
                    "engine":     actual_name,
                    "variant":    "base",
                    "spec":       key,
                    "value":      value,
                    "source":     url,
                    "scraped_at": datetime.now().isoformat()
                })

        logging.info(
            f"Scraped '{actual_name}': {len(data)} spec rows, "
            f"{len(all_variants)} infobox variants, "
            f"{len(apps)} applications"
        )

    except Exception as e:
        logging.error(f"Failed to scrape {engine_name} ({url}): {e}")

    if is_root and _all_apps:
        saved = save_applications(_all_apps, BASE_DIR)
        if saved:
            logging.info(f"Saved {saved} application rows for '{engine_name}'")

    return data


# ── Wikipedia search ──────────────────────────────────────────────────────────

def search_wikipedia(engine_name):
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": engine_name,
            "format": "json",
            "srlimit": 1
        }
        time.sleep(0.3)  # polite delay before each API call
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"}
        )
        if response.status_code != 200 or not response.text.strip():
            return None
        data = response.json()
        results = data.get("query", {}).get("search", [])
        if results:
            title = results[0]["title"]
            if not is_valid_engine(title):
                return None
            return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
    except Exception as e:
        logging.error(f"Search failed for {engine_name}: {e}")
    return None


# ── Runner ────────────────────────────────────────────────────────────────────

def run_scraper():
    print(f"Starting scrape at {datetime.now()}")
    logging.info("Scrape started")

    all_data = []

    for engine in ENGINES:
        print(f"\nSearching: {engine}")
        url = search_wikipedia(engine)
        if url:
            print(f"  Found: {url}")
            data = scrape_engine(engine, url)
            all_data.extend(data)
            print(f"  → {len(data)} spec rows collected")
        else:
            print(f"  Not found: {engine}")
            logging.warning(f"Could not find Wikipedia page for {engine}")
        time.sleep(0.75)  # rate limit — avoid Wikipedia blocking

    df = pd.DataFrame(all_data)
    csv_path  = os.path.join(BASE_DIR, "engine_specs.csv")
    xlsx_path = os.path.join(BASE_DIR, "engine_specs.xlsx")
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    apps_path = os.path.join(BASE_DIR, "engine_applications.csv")
    if os.path.exists(apps_path):
        apps_df = pd.read_csv(apps_path)
        print(f"\nApplications table: {len(apps_df)} rows in engine_applications.csv")

    print(f"\nDone! {len(df)} spec rows scraped")
    logging.info(f"Scrape complete: {len(df)} spec rows")
    return len(df)


if __name__ == "__main__":
    run_scraper()
