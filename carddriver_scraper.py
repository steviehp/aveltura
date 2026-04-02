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
    filename=os.path.join(BASE_DIR, "carddriver_scraper.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Car and Driver engine specs search URLs
ENGINES = [
    ("Toyota 2JZ-GTE", "https://www.caranddriver.com/research/a32839232/toyota-2jz-gte-engine-specs/"),
    ("Nissan RB26DETT", "https://www.caranddriver.com/research/a32839232/nissan-rb26dett-engine-specs/"),
    ("Honda K20", "https://www.caranddriver.com/research/a32839232/honda-k20-engine-specs/"),
    ("GM LS3", "https://www.caranddriver.com/research/a32839232/gm-ls3-engine-specs/"),
    ("Ford Coyote 5.0", "https://www.caranddriver.com/research/a32839232/ford-coyote-engine-specs/"),
    ("Chrysler Hemi 6.4", "https://www.caranddriver.com/research/a32839232/chrysler-hemi-64-engine-specs/"),
    ("BMW S54", "https://www.caranddriver.com/research/a32839232/bmw-s54-engine-specs/"),
    ("BMW N54", "https://www.caranddriver.com/research/a32839232/bmw-n54-engine-specs/"),
]

def scrape_carddriver(engine_name, url):
    data = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logging.warning(f"Got {response.status_code} for {engine_name}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Try to find spec tables
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all(["th", "td"])
                if len(cols) >= 2:
                    key = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    if key and value:
                        data.append({
                            "engine": engine_name,
                            "variant": "base",
                            "spec": key,
                            "value": value,
                            "source": url,
                            "scraped_at": datetime.now().isoformat()
                        })

        # Also try definition lists
        dl_items = soup.find_all("dl")
        for dl in dl_items:
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True)
                value = dd.get_text(strip=True)
                if key and value:
                    data.append({
                        "engine": engine_name,
                        "variant": "base",
                        "spec": key,
                        "value": value,
                        "source": url,
                        "scraped_at": datetime.now().isoformat()
                    })

        logging.info(f"Scraped {engine_name} from C&D: {len(data)} rows")
        print(f"  Got {len(data)} rows from Car and Driver")

    except Exception as e:
        logging.error(f"Failed to scrape {engine_name} from C&D: {e}")
    return data

def run_carddriver_scraper():
    print(f"Starting Car and Driver scrape at {datetime.now()}")
    all_data = []

    for engine_name, url in ENGINES:
        print(f"Scraping {engine_name}...")
        data = scrape_carddriver(engine_name, url)
        all_data.extend(data)

    if not all_data:
        print("No data scraped from Car and Driver")
        return 0

    # Append to existing engine specs
    new_df = pd.DataFrame(all_data)
    existing_path = os.path.join(BASE_DIR, "engine_specs.csv")

    if os.path.exists(existing_path):
        existing_df = pd.read_csv(existing_path)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["engine", "variant", "spec"], keep="first")
    else:
        combined = new_df

    combined.to_csv(existing_path, index=False)
    print(f"\nDone! Added {len(all_data)} rows from Car and Driver")
    logging.info(f"C&D scrape complete: {len(all_data)} rows")
    return len(all_data)

if __name__ == "__main__":
    run_carddriver_scraper()
