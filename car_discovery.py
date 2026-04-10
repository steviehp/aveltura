import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from scraper import search_wikipedia, scrape_engine, save_applications

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "car_discovery.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ── Car seed list ─────────────────────────────────────────────────────────────
# Covers all engine families in the scraper + verified_seeds
# JDM, American, European, Exotic

CARS = [
    # ── Toyota / Lexus ────────────────────────────────────────────────────────
    "Toyota Supra A80",
    "Toyota Supra A90",
    "Toyota GR86",
    "Toyota Camry V6",
    "Toyota Land Cruiser 200",
    "Toyota Tundra 5.7",
    "Toyota Century",
    "Lexus LFA",
    "Lexus IS-F",
    "Lexus GS-F",
    "Lexus LC500",
    "Lexus LS400",
    "Lexus SC300",
    "Lexus SC400",
    # ── Nissan ───────────────────────────────────────────────────────────────
    "Nissan GT-R R35",
    "Nissan GT-R R34",
    "Nissan GT-R R33",
    "Nissan Skyline R32",
    "Nissan 370Z",
    "Nissan 350Z",
    "Nissan 240SX",
    "Nissan Silvia S15",
    "Nissan Silvia S14",
    "Nissan 180SX",
    "Nissan Maxima",
    "Nissan Frontier",
    "Nissan 300ZX",
    # ── Honda / Acura ─────────────────────────────────────────────────────────
    "Honda S2000",
    "Honda Civic Type R FK8",
    "Honda Civic Type R EP3",
    "Honda Integra Type R DC5",
    "Honda Integra Type R DC2",
    "Honda NSX NA1",
    "Honda NSX NA2",
    "Acura NSX",
    "Acura RSX Type S",
    "Acura TSX",
    "Honda Accord Euro R",
    "Honda CR-V",
    # ── Subaru ───────────────────────────────────────────────────────────────
    "Subaru Impreza WRX STI",
    "Subaru BRZ",
    "Subaru Outback",
    "Subaru Forester XT",
    "Subaru Legacy GT",
    # ── Mitsubishi ───────────────────────────────────────────────────────────
    "Mitsubishi Lancer Evolution X",
    "Mitsubishi Lancer Evolution IX",
    "Mitsubishi Lancer Evolution VIII",
    "Mitsubishi Eclipse GSX",
    "Mitsubishi 3000GT VR-4",
    # ── Mazda ────────────────────────────────────────────────────────────────
    "Mazda RX-7 FD",
    "Mazda RX-7 FC",
    "Mazda MX-5 Miata",
    "Mazda 6 MPS",
    # ── American ─────────────────────────────────────────────────────────────
    "Chevrolet Corvette C8 Z06",
    "Chevrolet Corvette C7 Z06",
    "Chevrolet Corvette C7 ZR1",
    "Chevrolet Corvette C6 Z06",
    "Chevrolet Corvette C5 Z06",
    "Chevrolet Camaro ZL1",
    "Chevrolet Camaro SS",
    "Chevrolet Camaro Z28",
    "Cadillac CT5-V Blackwing",
    "Cadillac CTS-V",
    "Ford Mustang Shelby GT500",
    "Ford Mustang GT350",
    "Ford Mustang GT350R",
    "Ford Mustang Mach 1",
    "Ford Mustang Boss 302",
    "Ford Mustang GT",
    "Ford GT",
    "Ford F-150 Raptor",
    "Dodge Challenger SRT Hellcat",
    "Dodge Challenger SRT Demon",
    "Dodge Charger Hellcat",
    "Dodge Viper ACR",
    "Dodge Viper GTS",
    "Jeep Grand Cherokee Trackhawk",
    "Ram 1500 TRX",
    "Chrysler 300 SRT8",
    # ── BMW ───────────────────────────────────────────────────────────────────
    "BMW M3 E46",
    "BMW M3 E90",
    "BMW M3 E92",
    "BMW M3 F80",
    "BMW M3 G80",
    "BMW M4 F82",
    "BMW M4 G82",
    "BMW M5 E60",
    "BMW M5 F10",
    "BMW M5 F90",
    "BMW M2 Competition",
    "BMW M6 F13",
    "BMW 1M",
    "BMW Z4 M",
    "BMW M8",
    "BMW X5 M",
    "BMW 740i E38",
    "BMW 540i E39",
    # ── Mercedes-Benz ────────────────────────────────────────────────────────
    "Mercedes-Benz C63 AMG W204",
    "Mercedes-Benz C63 AMG W205",
    "Mercedes-Benz E63 AMG W212",
    "Mercedes-Benz E63 AMG W213",
    "Mercedes-Benz S63 AMG",
    "Mercedes-Benz SLS AMG",
    "Mercedes-Benz AMG GT",
    "Mercedes-Benz AMG GT Black Series",
    "Mercedes-Benz G63 AMG",
    "Mercedes-Benz ML63 AMG",
    "Mercedes-Benz GLK350",
    # ── Audi ─────────────────────────────────────────────────────────────────
    "Audi RS3",
    "Audi RS4 B8",
    "Audi RS5",
    "Audi RS6 C8",
    "Audi R8 V10",
    "Audi TT RS",
    "Audi S4 B8",
    "Audi S5",
    # ── Porsche ──────────────────────────────────────────────────────────────
    "Porsche 911 GT3 RS 991",
    "Porsche 911 Turbo S 992",
    "Porsche 911 Carrera S 997",
    "Porsche Cayman GT4",
    "Porsche Boxster GTS",
    "Porsche Panamera Turbo",
    "Porsche Cayenne Turbo",
    # ── Exotic ───────────────────────────────────────────────────────────────
    "Lamborghini Huracan",
    "Lamborghini Gallardo",
    "Lamborghini Aventador",
    "Lamborghini Murcielago",
    "Ferrari 458 Italia",
    "Ferrari 488 GTB",
    "Ferrari F40",
    "Ferrari F50",
    "Ferrari Enzo",
    "Ferrari LaFerrari",
    "McLaren 720S",
    "McLaren 600LT",
    "McLaren P1",
    "McLaren F1",
    "Bugatti Veyron",
    "Bugatti Chiron",
    "Pagani Huayra",
    "Koenigsegg Agera RS",
    "Aston Martin Vantage V8",
    "Aston Martin DBS Superleggera",
    "Jaguar F-Type SVR",
    "Alfa Romeo Giulia Quadrifoglio",
]

BLACKLIST = {
    "turbo", "turbocharged", "twin-turbo", "twin-turbocharged",
    "supercharged", "naturally aspirated", "petrol", "diesel",
    "gasoline", "electric", "hybrid", "quad-turbo", "quad-turbocharged",
    "inline", "boxer", "flat", "v6", "v8", "v10", "v12",
    "manual", "automatic", "sequential", "transmission", "gearbox",
    "awd", "rwd", "fwd", "4wd", "all-wheel", "rear-wheel", "front-wheel",
}


# ── Wikipedia search ──────────────────────────────────────────────────────────

def get_wikipedia_url(car_name):
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": car_name,
            "format": "json",
            "srlimit": 1
        }
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"}
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


# ── Infobox extraction ────────────────────────────────────────────────────────

def is_valid_engine_name(text):
    text = text.strip()
    if len(text) < 3 or len(text) > 80:
        return False
    if text.lower() in BLACKLIST:
        return False
    if any(bl in text.lower() for bl in list(BLACKLIST)[:8]):
        return False
    has_engine_code         = bool(re.search(r'[A-Z]{1,3}\d', text))
    has_engine_word         = "engine" in text.lower()
    has_displacement_config = bool(re.search(r'\d\.\d.*[Vv]\d', text))
    has_known_name          = any(kw in text for kw in [
        "Lambda", "Theta", "Viper", "Coyote", "Hemi", "Voodoo",
        "Trinity", "Hellcat", "Demon", "Redeye", "Blackwing",
        "Predator", "Aluminator", "Modular", "Cammer", "Godzilla",
    ])
    return has_engine_code or has_engine_word or has_displacement_config or has_known_name


def _parse_power(text):
    """Extract first plausible HP value from infobox power field."""
    for pattern, mult in [
        (r'(\d{2,4})\s*(?:hp|bhp)',  1.0),
        (r'(\d{2,4})\s*ps',          0.9863),
        (r'(\d{2,4})\s*kw',          1.341),
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = round(float(m.group(1)) * mult, 1)
            if 50 < val < 2000:
                return val
    return None


def _parse_years(text):
    """Extract year_start, year_end from infobox production field."""
    m = re.search(r'((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'((?:19|20)\d{2})', text)
    if m:
        return int(m.group(1)), None
    return None, None


def _parse_displacement(text):
    """Extract displacement in litres from text."""
    # Prefer explicit cc value
    cc_m = re.search(r'([\d,]+)\s*cc', text, re.IGNORECASE)
    if cc_m:
        cc = float(cc_m.group(1).replace(",", ""))
        if 50 < cc < 15000:
            return round(cc / 1000, 1)
    # Fall back to litre value
    l_m = re.search(r'(\d+\.?\d*)\s*[Ll]', text)
    if l_m:
        val = float(l_m.group(1))
        if 0.5 < val < 15:
            return val
    return None


def extract_car_info(url, car_name):
    """
    Scrape a car Wikipedia page infobox.
    Returns dict with: engines, displacement_l, power_hp, year_start, year_end
    """
    result = {
        "engines":        [],
        "displacement_l": None,
        "power_hp":       None,
        "year_start":     None,
        "year_end":       None,
    }

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AvelturaScraper/1.0)"},
            timeout=10
        )
        soup = BeautifulSoup(response.text, "html.parser")

        # Find infobox — try multiple class patterns
        infobox = (
            soup.find("table", class_="infobox") or
            soup.find("table", {"class": lambda c: c and "infobox" in c})
        )
        if not infobox:
            logging.warning(f"No infobox found for {car_name} at {url}")
            return result

        for row in infobox.find_all("tr"):
            header = row.find("th")
            data   = row.find("td")
            if not header or not data:
                continue

            header_text = header.get_text(strip=True).lower()
            data_text   = data.get_text(" ", strip=True)

            # Engine name
            if "engine" in header_text:
                disp = _parse_displacement(data_text)
                if disp:
                    result["displacement_l"] = disp
                for link in data.find_all("a"):
                    link_text = link.get_text(strip=True)
                    if is_valid_engine_name(link_text):
                        result["engines"].append(link_text)
                # Also try plain text if no links found
                if not result["engines"] and is_valid_engine_name(data_text):
                    result["engines"].append(data_text.strip())

            # Displacement
            elif "displacement" in header_text or "capacity" in header_text:
                disp = _parse_displacement(data_text)
                if disp:
                    result["displacement_l"] = disp

            # Power
            elif any(k in header_text for k in ["power", "output", "horsepower"]):
                hp = _parse_power(data_text)
                if hp:
                    result["power_hp"] = hp

            # Production years
            elif "production" in header_text or "years" in header_text:
                ys, ye = _parse_years(data_text)
                if ys:
                    result["year_start"] = ys
                    result["year_end"]   = ye

        logging.info(
            f"{car_name}: engines={result['engines'][:2]}, "
            f"disp={result['displacement_l']}L, "
            f"hp={result['power_hp']}, "
            f"years={result['year_start']}-{result['year_end']}"
        )

    except Exception as e:
        logging.error(f"Failed to extract info from {car_name}: {e}")

    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize(name):
    return name.lower().strip().replace("-", " ").replace("_", " ")


def get_existing_engines():
    path = os.path.join(BASE_DIR, "engine_specs.csv")
    if not os.path.exists(path):
        return set()
    try:
        df = pd.read_csv(path)
        return set(df["engine"].dropna().unique())
    except Exception:
        return set()


# ── Main runner ───────────────────────────────────────────────────────────────

def run_car_discovery():
    print(f"Starting car discovery at {datetime.now()}")
    logging.info("Car discovery started")

    existing         = get_existing_engines()
    existing_norm    = {normalize(e) for e in existing}
    new_engine_data  = []   # rows for engine_specs.csv
    new_applications = []   # rows for engine_applications.csv
    discovered_new   = {}   # engines not yet in db

    for car in CARS:
        print(f"\n  {car}")
        url, wiki_title = get_wikipedia_url(car)
        if not url:
            print(f"    Not found on Wikipedia")
            continue

        info = extract_car_info(url, car)

        if not info["engines"]:
            print(f"    No engine found in infobox")
            continue

        print(f"    Engine(s): {info['engines'][:3]}")
        if info["power_hp"]:
            print(f"    Power: {info['power_hp']}hp")
        if info["year_start"]:
            print(f"    Years: {info['year_start']}–{info['year_end'] or 'present'}")

        # ── Write to engine_applications.csv ─────────────────────────────────
        for engine_name in info["engines"]:
            new_applications.append({
                "engine":     engine_name,
                "vehicle":    wiki_title or car,
                "year_start": info["year_start"],
                "year_end":   info["year_end"],
                "power_hp":   info["power_hp"],
                "torque_nm":  None,
                "notes":      f"car_discovery",
                "source":     url,
            })

        # ── Queue unknown engines for spec scraping ───────────────────────────
        for engine_name in info["engines"]:
            if normalize(engine_name) not in existing_norm:
                if engine_name not in discovered_new:
                    discovered_new[engine_name] = {
                        "displacement_hint": info["displacement_l"],
                        "car_source":        car,
                    }

    # ── Save applications ─────────────────────────────────────────────────────
    if new_applications:
        apps_path = os.path.join(BASE_DIR, "engine_applications.csv")
        new_df    = pd.DataFrame(new_applications)

        if os.path.exists(apps_path):
            existing_apps = pd.read_csv(apps_path)
            combined      = pd.concat([existing_apps, new_df], ignore_index=True)
        else:
            combined = new_df

        combined = combined.drop_duplicates(subset=["engine", "vehicle"], keep="first")
        combined.to_csv(apps_path, index=False)
        print(f"\nSaved {len(new_applications)} application rows → engine_applications.csv")
        print(f"Total applications: {len(combined)}")
        logging.info(f"Saved {len(new_applications)} application rows")

    # ── Scrape specs for newly discovered engines ─────────────────────────────
    print(f"\nDiscovered {len(discovered_new)} new engines to scrape...")

    for engine_name, meta in discovered_new.items():
        print(f"\n  Scraping: {engine_name}")
        engine_url = search_wikipedia(engine_name)
        if not engine_url:
            print(f"    Wikipedia page not found")
            continue

        data = scrape_engine(engine_name, engine_url)
        if not data:
            print(f"    No spec data found")
            continue

        # Attach displacement hint for normalizer
        if meta["displacement_hint"]:
            data.append({
                "engine":     engine_name,
                "variant":    "base",
                "spec":       "displacement_hint",
                "value":      f"{meta['displacement_hint']}L",
                "source":     f"car_discovery:{meta['car_source']}",
                "scraped_at": datetime.now().isoformat()
            })

        new_engine_data.extend(data)
        existing_norm.add(normalize(engine_name))
        print(f"    {len(data)} spec rows")

    # ── Merge new engine specs into engine_specs.csv ──────────────────────────
    if new_engine_data:
        specs_path  = os.path.join(BASE_DIR, "engine_specs.csv")
        new_df      = pd.DataFrame(new_engine_data)

        if os.path.exists(specs_path):
            existing_df = pd.read_csv(specs_path)
            combined    = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined = new_df

        combined = combined.drop_duplicates(
            subset=["engine", "variant", "spec"], keep="first"
        )
        combined.to_csv(specs_path, index=False)
        combined.to_excel(
            os.path.join(BASE_DIR, "engine_specs.xlsx"), index=False
        )
        print(f"\nAdded {len(new_engine_data)} spec rows from {len(discovered_new)} new engines")
        logging.info(f"Car discovery complete: {len(new_engine_data)} spec rows added")
    else:
        print("\nNo new engine specs to add")

    logging.info("Car discovery complete")


if __name__ == "__main__":
    run_car_discovery()
