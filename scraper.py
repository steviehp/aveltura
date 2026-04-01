import requests
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

def search_wikipedia(engine_name):
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": engine_name,
            "format": "json",
            "srlimit": 1
        }
        response = requests.get(
            search_url, params=params, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
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

def parse_variant_values(value_str):
    if not value_str or pd.isna(value_str):
        return [("base", value_str)]

    val = str(value_str).strip()

    # Look for liter patterns like "3.5 L (3,473 cc)" repeated
    liter_pattern = re.findall(r'(\d+\.?\d*)\s*[Ll]\s*\(?([\d,]+)\s*cc\)?', val)
    valid_liter = [(l, cc) for l, cc in liter_pattern if float(l) <= 15]
    if len(valid_liter) > 1:
        return [(f"{l}L", f"{cc.replace(',', '')}cc") for l, cc in valid_liter]

    # Look for repeated cc patterns
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

    # Look for repeated hp/bhp variants
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

    # Look for repeated kW variants
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

def scrape_engine(engine_name, url):
    data = []
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table")

        raw_rows = []
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all(["th", "td"])
                if len(cols) >= 2:
                    key = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    if key and value:
                        raw_rows.append((key, value))

        variant_specs = {}
        all_variants = set()
        for key, value in raw_rows:
            parsed = parse_variant_values(value)
            if len(parsed) > 1:
                variant_specs[key] = parsed
                for variant_name, _ in parsed:
                    all_variants.add(variant_name)

        if all_variants:
            for variant_name in all_variants:
                for key, value in raw_rows:
                    if key in variant_specs:
                        for vname, vvalue in variant_specs[key]:
                            if vname == variant_name:
                                data.append({
                                    "engine": engine_name,
                                    "variant": variant_name,
                                    "spec": key,
                                    "value": vvalue,
                                    "source": url,
                                    "scraped_at": datetime.now().isoformat()
                                })
                    else:
                        data.append({
                            "engine": engine_name,
                            "variant": variant_name,
                            "spec": key,
                            "value": value,
                            "source": url,
                            "scraped_at": datetime.now().isoformat()
                        })
        else:
            for key, value in raw_rows:
                data.append({
                    "engine": engine_name,
                    "variant": "base",
                    "spec": key,
                    "value": value,
                    "source": url,
                    "scraped_at": datetime.now().isoformat()
                })

        logging.info(f"Scraped {engine_name}: {len(data)} rows, {len(all_variants)} variants")
    except Exception as e:
        logging.error(f"Failed to scrape {engine_name}: {e}")
    return data

def run_scraper():
    print(f"Starting scrape at {datetime.now()}")
    logging.info("Scrape started")
    all_data = []

    for engine in ENGINES:
        print(f"Searching for {engine}...")
        url = search_wikipedia(engine)
        if url:
            print(f"  Found: {url}")
            data = scrape_engine(engine, url)
            all_data.extend(data)
        else:
            print(f"  Not found: {engine}")
            logging.warning(f"Could not find Wikipedia page for {engine}")

    df = pd.DataFrame(all_data)
    df.to_csv(os.path.join(BASE_DIR, "engine_specs.csv"), index=False)
    df.to_excel(os.path.join(BASE_DIR, "engine_specs.xlsx"), index=False)
    print(f"\nDone! {len(df)} rows scraped")
    logging.info(f"Scrape complete: {len(df)} rows")
    return len(df)

if __name__ == "__main__":
    run_scraper()
