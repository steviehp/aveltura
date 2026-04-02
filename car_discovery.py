import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from scraper import search_wikipedia, scrape_engine

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "car_discovery.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

CARS = [
    "Kia Stinger",
    "Audi TT RS",
    "BMW M2",
    "BMW M4",
    "Porsche 911 GT3",
    "Porsche Cayman GT4",
    "Nissan 370Z",
    "Nissan GT-R",
    "Chevrolet Camaro SS",
    "Chevrolet Camaro ZL1",
    "Ford Mustang Shelby GT500",
    "Ford Mustang GT350",
    "Subaru WRX STI",
    "Mitsubishi Lancer Evolution",
    "Honda Civic Type R",
    "Toyota GR86",
    "Toyota Supra A90",
    "Mazda RX-7",
    "Mazda MX-5 Miata",
    "Alfa Romeo Giulia Quadrifoglio",
    "Mercedes-Benz C63 AMG",
    "Mercedes-Benz E63 AMG",
    "Lamborghini Huracan",
    "Ferrari 488",
    "McLaren 720S",
    "Aston Martin Vantage",
    "Jaguar F-Type SVR",
    "Dodge Viper",
    "Chevrolet Corvette Z06",
    "Chevrolet Corvette ZR1",
    "Cadillac CT5-V Blackwing",
    "Lexus LFA",
    "Honda NSX",
    "Acura NSX",
    "Bugatti Veyron",
    "Bugatti Chiron",
    "Koenigsegg Agera",
    "Pagani Huayra",
]

BLACKLIST = [
    "turbo", "turbocharged", "twin-turbo", "twin-turbocharged",
    "supercharged", "naturally aspirated", "petrol", "diesel",
    "gasoline", "electric", "hybrid", "quad-turbo", "quad-turbocharged",
    "inline", "boxer", "flat", "v6", "v8", "v10", "v12",
    "manual", "automatic", "sequential", "transmission", "gearbox",
    "awd", "rwd", "fwd", "4wd", "all-wheel", "rear-wheel", "front-wheel"
]

def get_wikipedia_url(car_name):
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": car_name,
            "format": "json",
            "srlimit": 1
        }
        response = requests.get(
            search_url, params=params, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if response.status_code != 200 or not response.text.strip():
            return None, None
        data = response.json()
        results = data.get("query", {}).get("search", [])
        if results:
            title = results[0]["title"]
            return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}", title
    except Exception as e:
        logging.error(f"Search failed for {car_name}: {e}")
    return None, None

def is_valid_engine_name(text):
    text = text.strip()
    if len(text) < 3 or len(text) > 80:
        return False
    if text.lower() in BLACKLIST:
        return False
    if any(bl in text.lower() for bl in BLACKLIST[:8]):  # check prefix blacklist
        return False
    # Must look like a real engine name
    has_engine_code = bool(re.search(r'[A-Z]{1,3}\d', text))  # VQ37, LS3, 1LR
    has_engine_word = "engine" in text.lower()
    has_displacement_config = bool(re.search(r'\d\.\d.*[Vv]\d', text))  # 3.7L V6
    has_known_name = any(kw in text for kw in [
        "Lambda", "Theta", "Viper", "Coyote", "Hemi", "Voodoo",
        "Trinity", "Hellcat", "Demon", "Redeye", "Blackwing",
        "Predator", "Aluminator", "Modular", "Cammer"
    ])
    return has_engine_code or has_engine_word or has_displacement_config or has_known_name

def extract_engine_from_car_page(url, car_name):
    engines_found = []
    displacement_found = None

    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        infobox = soup.find("table", class_="infobox")
        if not infobox:
            return engines_found, None

        rows = infobox.find_all("tr")
        for row in rows:
            header = row.find("th")
            data = row.find("td")
            if not header or not data:
                continue

            header_text = header.get_text(strip=True).lower()
            data_text = data.get_text(strip=True)

            if "engine" in header_text:
                # Try displacement from engine field
                disp_match = re.findall(r'(\d+\.?\d*)\s*[Ll]', data_text)
                if disp_match:
                    disp_val = float(disp_match[0])
                    if 0.5 < disp_val < 15:
                        displacement_found = disp_val

                # Extract engine links
                links = data.find_all("a")
                for link in links:
                    link_text = link.get_text(strip=True)
                    if is_valid_engine_name(link_text):
                        engines_found.append(link_text)

            if "displacement" in header_text or "capacity" in header_text:
                disp_match = re.findall(r'(\d+\.?\d*)\s*[Ll]', data_text)
                if disp_match:
                    disp_val = float(disp_match[0])
                    if 0.5 < disp_val < 15:
                        displacement_found = disp_val

        logging.info(f"Found engines for {car_name}: {engines_found}, displacement: {displacement_found}")

    except Exception as e:
        logging.error(f"Failed to extract engine from {car_name}: {e}")

    return engines_found, displacement_found

def get_existing_engines():
    try:
        df = pd.read_csv(os.path.join(BASE_DIR, "engine_specs.csv"))
        return set(df["engine"].unique())
    except:
        return set()

def normalize(name):
    return name.lower().strip().replace("-", " ").replace("_", " ")

def run_car_discovery():
    print(f"Starting car-based engine discovery at {datetime.now()}")
    logging.info("Car discovery started")

    existing = get_existing_engines()
    existing_normalized = {normalize(e) for e in existing}
    print(f"Currently have {len(existing)} engines")

    discovered_engines = {}
    all_new_data = []

    for car in CARS:
        print(f"\nLooking up {car}...")
        url, wiki_title = get_wikipedia_url(car)
        if not url:
            print(f"  Not found on Wikipedia")
            continue

        engines, displacement = extract_engine_from_car_page(url, car)
        if not engines:
            print(f"  No engines found for {car}")
            continue

        print(f"  Found engines: {engines[:3]}")
        if displacement:
            print(f"  Displacement hint: {displacement}L")

        for engine_name in engines:
            engine_clean = engine_name.strip()
            if normalize(engine_clean) in existing_normalized:
                print(f"  Already have: {engine_clean}")
                continue
            if engine_clean not in discovered_engines:
                discovered_engines[engine_clean] = {
                    "displacement_hint": displacement,
                    "car_source": car
                }

    print(f"\nDiscovered {len(discovered_engines)} potentially new engines")

    for engine_name, meta in discovered_engines.items():
        print(f"Scraping discovered engine: {engine_name}...")
        engine_url = search_wikipedia(engine_name)
        if not engine_url:
            print(f"  Wikipedia page not found for {engine_name}")
            continue

        data = scrape_engine(engine_name, engine_url)
        if not data:
            print(f"  No data scraped for {engine_name}")
            continue

        if meta["displacement_hint"]:
            data.append({
                "engine": engine_name,
                "variant": "base",
                "spec": "displacement_hint",
                "value": f"{meta['displacement_hint']}L",
                "source": f"car_discovery:{meta['car_source']}",
                "scraped_at": datetime.now().isoformat()
            })

        all_new_data.extend(data)
        existing_normalized.add(normalize(engine_name))
        print(f"  Added {len(data)} rows for {engine_name}")

    if all_new_data:
        existing_df = pd.read_csv(os.path.join(BASE_DIR, "engine_specs.csv"))
        new_df = pd.DataFrame(all_new_data)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["engine", "variant", "spec"], keep="first")
        combined.to_csv(os.path.join(BASE_DIR, "engine_specs.csv"), index=False)
        print(f"\nAdded {len(all_new_data)} new rows from car discovery")
        logging.info(f"Car discovery complete: {len(all_new_data)} rows added")
    else:
        print("No new data found")

if __name__ == "__main__":
    run_car_discovery()
