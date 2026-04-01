import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename="mods_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

MODS = [
    # Turbos
    "Garrett turbocharger",
    "BorgWarner turbocharger",
    "Precision turbocharger",
    "Holset turbocharger",
    "IHI turbocharger",
    # Superchargers
    "Eaton supercharger",
    "Roots type supercharger",
    "Twin-screw supercharger",
    "Centrifugal supercharger",
    # Fuel systems
    "Direct injection engine",
    "Port fuel injection",
    "Bosch fuel injector",
    # Intercoolers
    "Intercooler",
    "Air to water intercooler",
    # Suspension
    "Coilover suspension",
    "Sway bar",
    "Strut brace",
    # Wheels
    "BBS wheels",
    "Enkei wheels",
    "Rays Engineering wheels",
    # Brakes
    "Brembo brake",
    "StopTech brakes",
    "Performance brake rotor",
    # Engine internals
    "Forged piston",
    "Connecting rod engine",
    "Crankshaft",
    "Camshaft",
    "Cylinder head",
]

def search_wikipedia(query):
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
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
            return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
    except Exception as e:
        logging.error(f"Search failed for {query}: {e}")
    return None

def scrape_mod(mod_name, url):
    data = []
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Get intro paragraph for context
        paragraphs = soup.find_all("p")
        intro = ""
        for p in paragraphs[:3]:
            text = p.get_text(strip=True)
            if len(text) > 50:
                intro = text
                break

        if intro:
            data.append({
                "mod": mod_name,
                "spec": "description",
                "value": intro[:500],
                "source": url,
                "scraped_at": datetime.now().isoformat()
            })

        # Get tables
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
                            "mod": mod_name,
                            "spec": key,
                            "value": value,
                            "source": url,
                            "scraped_at": datetime.now().isoformat()
                        })

        logging.info(f"Scraped {mod_name}: {len(data)} rows")
    except Exception as e:
        logging.error(f"Failed to scrape {mod_name}: {e}")
    return data

def run_mods_scraper():
    print(f"Starting mods scrape at {datetime.now()}")
    logging.info("Mods scrape started")
    all_data = []

    for mod in MODS:
        print(f"Searching for {mod}...")
        url = search_wikipedia(mod)
        if url:
            print(f"  Found: {url}")
            data = scrape_mod(mod, url)
            all_data.extend(data)
        else:
            print(f"  Not found: {mod}")

    df = pd.DataFrame(all_data)
    df.to_csv("mods_specs.csv", index=False)
    print(f"\nDone! {len(df)} rows scraped")
    logging.info(f"Mods scrape complete: {len(df)} rows")
    return len(df)

if __name__ == "__main__":
    run_mods_scraper()
