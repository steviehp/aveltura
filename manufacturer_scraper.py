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
    filename=os.path.join(BASE_DIR, "manufacturer_scraper.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# These are direct Wikipedia pages for specific engine variants
# More specific than family pages — one page per actual engine
SPECIFIC_ENGINES = [
    ("Toyota 2JZ-GTE", "https://en.wikipedia.org/wiki/Toyota_JZ_engine#2JZ-GTE"),
    ("Nissan RB26DETT", "https://en.wikipedia.org/wiki/Nissan_RB_engine#RB26DETT"),
    ("Honda K20A", "https://en.wikipedia.org/wiki/Honda_K_engine#K20A"),
    ("Honda B18C", "https://en.wikipedia.org/wiki/Honda_B_engine#B18C"),
    ("Mitsubishi 4G63T", "https://en.wikipedia.org/wiki/Mitsubishi_Sirius_engine#4G63"),
    ("Subaru EJ257", "https://en.wikipedia.org/wiki/Subaru_EJ_engine#EJ257"),
    ("GM LS3", "https://en.wikipedia.org/wiki/GM_LS_engine#LS3"),
    ("GM LS7", "https://en.wikipedia.org/wiki/GM_LS_engine#LS7"),
    ("Ford 5.0 Coyote", "https://en.wikipedia.org/wiki/Ford_Modular_engine#5.0L_Coyote"),
    ("Chrysler 6.4 Hemi", "https://en.wikipedia.org/wiki/Chrysler_Hemi_engine#6.4L"),
    ("BMW S54B32", "https://en.wikipedia.org/wiki/BMW_S54"),
    ("BMW N54B30", "https://en.wikipedia.org/wiki/BMW_N54"),
    ("BMW S65B40", "https://en.wikipedia.org/wiki/BMW_S65"),
    ("Mercedes M156", "https://en.wikipedia.org/wiki/Mercedes-Benz_M156_engine"),
    ("Porsche M96", "https://en.wikipedia.org/wiki/Porsche_M96"),
    ("Lamborghini V12 6.5", "https://en.wikipedia.org/wiki/Lamborghini_V12#6.5_L_(6,498_cc)_LP_series"),
    ("Ferrari F136 4.5", "https://en.wikipedia.org/wiki/Ferrari_F136_engine"),
    ("Ford GT500 5.8", "https://en.wikipedia.org/wiki/Ford_Shelby_GT500#2013"),
    ("Dodge Hellcat 6.2", "https://en.wikipedia.org/wiki/Chrysler_Hemi_engine#6.2L_Hellcat"),
    ("Chevrolet LS9", "https://en.wikipedia.org/wiki/GM_LS_engine#LS9"),
]

def scrape_specific_engine(engine_name, url):
    data = []
    try:
        # Use base URL without anchor for scraping
        base_url = url.split("#")[0]
        response = requests.get(
            base_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        soup = BeautifulSoup(response.text, "html.parser")
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

        logging.info(f"Scraped {engine_name}: {len(data)} rows")
        print(f"  Got {len(data)} rows")
    except Exception as e:
        logging.error(f"Failed {engine_name}: {e}")
    return data

def run_manufacturer_scraper():
    print(f"Starting specific engine scrape at {datetime.now()}")
    all_data = []

    for engine_name, url in SPECIFIC_ENGINES:
        print(f"Scraping {engine_name}...")
        data = scrape_specific_engine(engine_name, url)
        all_data.extend(data)

    if not all_data:
        print("No data scraped")
        return 0

    new_df = pd.DataFrame(all_data)
    existing_path = os.path.join(BASE_DIR, "engine_specs.csv")

    if os.path.exists(existing_path):
        existing_df = pd.read_csv(existing_path)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["engine", "variant", "spec"], keep="first")
    else:
        combined = new_df

    combined.to_csv(existing_path, index=False)
    print(f"\nDone! Added {len(all_data)} rows")
    logging.info(f"Specific scrape complete: {len(all_data)} rows")
    return len(all_data)

if __name__ == "__main__":
    run_manufacturer_scraper()
