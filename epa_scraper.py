import requests
import pandas as pd
import os
import logging
from dotenv import load_dotenv
from io import StringIO

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "epa_scraper.log"),
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

EPA_CSV_URL = "https://fueleconomy.gov/feg/epadata/vehicles.csv.zip"

# Map our engine names to make/model/year combos in EPA data
ENGINE_TO_VEHICLE = {
    "Toyota 2JZ-GTE": [("TOYOTA", "Supra", 1993), ("TOYOTA", "Supra", 1994), ("TOYOTA", "Supra", 1995), ("TOYOTA", "Supra", 1996), ("TOYOTA", "Supra", 1997)],
    "Nissan RB26DETT": [("NISSAN", "Skyline GT-R", 1990)],
    "Honda K20A": [("HONDA", "Civic Si", 2002), ("HONDA", "Civic Si", 2003)],
    "Honda B18C": [("ACURA", "Integra", 1994), ("ACURA", "Integra", 1995)],
    "GM LS3": [("CHEVROLET", "Corvette", 2008), ("CHEVROLET", "Camaro SS", 2010)],
    "GM LS7": [("CHEVROLET", "Corvette Z06", 2006), ("CHEVROLET", "Corvette Z06", 2007)],
    "Ford 5.0 Coyote": [("FORD", "Mustang GT", 2011), ("FORD", "Mustang GT", 2012)],
    "Chrysler 6.4 Hemi": [("DODGE", "Challenger SRT", 2012), ("DODGE", "Charger SRT", 2012)],
    "Chrysler 6.2 Hellcat": [("DODGE", "Challenger SRT Hellcat", 2015), ("DODGE", "Charger SRT Hellcat", 2015)],
    "BMW S54B32": [("BMW", "M3", 2001), ("BMW", "M3", 2002), ("BMW", "M3", 2003)],
    "BMW N54B30": [("BMW", "335i", 2007), ("BMW", "135i", 2008)],
    "Mercedes M156": [("MERCEDES-BENZ", "C63 AMG", 2008), ("MERCEDES-BENZ", "E63 AMG", 2007)],
}

def download_epa_data():
    print("Downloading EPA vehicle data...")
    cache_path = os.path.join(BASE_DIR, "epa_vehicles.csv")

    if os.path.exists(cache_path):
        print("Using cached EPA data")
        return pd.read_csv(cache_path, low_memory=False)

    response = requests.get(EPA_CSV_URL, timeout=60)
    import zipfile
    import io
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        with z.open("vehicles.csv") as f:
            df = pd.read_csv(f, low_memory=False)

    df.to_csv(cache_path, index=False)
    print(f"Downloaded {len(df)} EPA vehicle records")
    return df

def get_engine_specs_from_epa(epa_df, engine_name, vehicle_list):
    results = []
    for make, model, year in vehicle_list:
        mask = (
            epa_df["make"].str.upper() == make.upper()
        ) & (
            epa_df["model"].str.upper().str.contains(model.upper(), na=False)
        ) & (
            epa_df["year"] == year
        )
        matches = epa_df[mask]
        if not matches.empty:
            row = matches.iloc[0]
            results.append({
                "engine": engine_name,
                "variant": "base",
                "spec": "Displacement",
                "value": f"{row.get('displ', '')} L",
                "source": f"EPA fueleconomy.gov ({make} {model} {year})",
                "scraped_at": pd.Timestamp.now().isoformat()
            })
            results.append({
                "engine": engine_name,
                "variant": "base",
                "spec": "Configuration",
                "value": f"V{row.get('cylinders', '')}" if row.get('cylinders') else "",
                "source": f"EPA fueleconomy.gov ({make} {model} {year})",
                "scraped_at": pd.Timestamp.now().isoformat()
            })
            print(f"  Found {make} {model} {year}: {row.get('displ')}L, {row.get('cylinders')} cylinders")

    return results

def run_epa_scraper():
    print(f"Starting EPA scrape...")
    logging.info("EPA scrape started")

    try:
        epa_df = download_epa_data()
    except Exception as e:
        print(f"Failed to download EPA data: {e}")
        return 0

    all_data = []
    for engine_name, vehicle_list in ENGINE_TO_VEHICLE.items():
        print(f"Looking up {engine_name}...")
        data = get_engine_specs_from_epa(epa_df, engine_name, vehicle_list)
        all_data.extend(data)

    if not all_data:
        print("No data found")
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
    print(f"\nAdded {len(all_data)} EPA verified rows")
    logging.info(f"EPA scrape complete: {len(all_data)} rows")
    return len(all_data)

if __name__ == "__main__":
    run_epa_scraper()
