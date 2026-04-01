import pandas as pd
import re
import logging
from datetime import datetime

logging.basicConfig(
    filename="cleaner.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def clean_value(val):
    if not isinstance(val, str):
        return val
    # Remove citation brackets like [1], [note 1], [a]
    val = re.sub(r'\[.*?\]', '', val)
    # Remove excessive whitespace
    val = re.sub(r'\s+', ' ', val).strip()
    # Remove unicode garbage
    val = val.encode('ascii', 'ignore').decode('ascii')
    return val

def is_garbage_row(row):
    spec = str(row['spec']).strip()
    value = str(row['value']).strip()

    # Empty or too short
    if len(spec) < 2 or len(value) < 1:
        return True
    # Just a number with no context
    if re.match(r'^\d+$', value):
        return True
    # Wikipedia artifacts
    if any(x in spec.lower() for x in ['retrieved', 'archived', 'cite', 'isbn', 'doi']):
        return True
    if any(x in value.lower() for x in ['retrieved', 'archived', 'wikimedia', 'wikipedia']):
        return True
    # Obviously wrong HP values
    if 'power' in spec.lower() or 'hp' in spec.lower():
        numbers = re.findall(r'\d+', value)
        if numbers and int(numbers[0]) > 10000:
            return True
    return False

def normalize_units(val):
    if not isinstance(val, str):
        return val
    val = val.replace('horsepower', 'hp')
    val = val.replace('Horsepower', 'hp')
    val = val.replace('kilowatts', 'kW')
    val = val.replace('Newton metres', 'Nm')
    val = val.replace('newton metres', 'Nm')
    val = val.replace('pound-feet', 'lb-ft')
    val = val.replace('cubic centimetres', 'cc')
    val = val.replace('cubic inches', 'cu in')
    return val

def run_cleaner():
    print(f"Starting cleaner at {datetime.now()}")
    logging.info("Cleaner started")

    df = pd.read_csv("engine_specs.csv")
    original_rows = len(df)
    print(f"Original rows: {original_rows}")

    # Clean values
    df['spec'] = df['spec'].apply(clean_value)
    df['value'] = df['value'].apply(clean_value)
    df['value'] = df['value'].apply(normalize_units)

    # Remove garbage rows
    df = df[~df.apply(is_garbage_row, axis=1)]

    # Remove duplicates
    df = df.drop_duplicates(subset=["engine", "spec"], keep="first")

    # Remove rows with empty spec or value after cleaning
    df = df[df['spec'].str.strip() != '']
    df = df[df['value'].str.strip() != '']

    cleaned_rows = len(df)
    removed = original_rows - cleaned_rows
    print(f"Cleaned rows: {cleaned_rows} (removed {removed} garbage rows)")
    logging.info(f"Cleaner complete: {cleaned_rows} rows, removed {removed}")

    df.to_csv("engine_specs.csv", index=False)
    df.to_excel("engine_specs.xlsx", index=False)
    print("Saved clean CSV")

if __name__ == "__main__":
    run_cleaner()
