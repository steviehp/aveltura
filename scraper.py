import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename="scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

ENGINES = [
    "Toyota JZ engine",
    "Nissan SR engine",
    "Nissan RB engine",
    "Honda K engine",
    "Honda B engine",
    "Mitsubishi Sirius engine",
    "Subaru EJ engine",
    "Nissan VQ engine",
    "GM LS engine",
    "Chrysler Hemi engine",
    "Ford Modular engine",
    "Cadillac Northstar engine",
    "Ford Coyote engine",
    "Chevrolet Small-Block engine",
    "BMW S54",
    "BMW S65",
    "Mercedes-Benz M156 engine",
    "Audi five-cylinder engine",
    "Porsche flat-six engine",
    "BMW N54",
    "Volkswagen EA888",
]

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
            logging.warning(f"Empty response for {engine_name}")
            return None
        data = response.json()
        results = data.get("query", {}).get("search", [])
        if results:
            title = results[0]["title"]
            return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
    except Exception as e:
        logging.error(f"Search failed for {engine_name}: {e}")
    return None

def scrape_engine(engine_name, url):
    data = []
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
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
                            "spec": key,
                            "value": value,
                            "source": url,
                            "scraped_at": datetime.now().isoformat()
                        })
        logging.info(f"Scraped {engine_name}: {len(data)} rows")
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
    df.to_csv("engine_specs.csv", index=False)
    df.to_excel("engine_specs.xlsx", index=False)
    print(f"\nDone! {len(df)} rows scraped")
    logging.info(f"Scrape complete: {len(df)} rows")
    return len(df)

if __name__ == "__main__":
    run_scraper()
