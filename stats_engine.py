import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

def load_normalized_data():
    path = os.path.join(BASE_DIR, "engine_normalized.csv")
    if not os.path.exists(path):
        from normalizer import run_normalizer
        return run_normalizer()
    return pd.read_csv(path)

def extract_numeric(value):
    if pd.isna(value):
        return None
    val = str(value)
    range_match = re.findall(r'(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', val)
    if range_match:
        low, high = float(range_match[0][0]), float(range_match[0][1])
        return (low + high) / 2
    nums = re.findall(r'\d+\.?\d*', val)
    if nums:
        return float(nums[0])
    return None

def available_specs():
    df = load_normalized_data()
    numeric_specs = []
    for col in df.columns:
        if col == "engine":
            continue
        numeric = df[col].apply(extract_numeric)
        if numeric.notna().sum() > 3:
            numeric_specs.append(col)
    return sorted(numeric_specs)

def interpret_correlation(corr, pvalue):
    if pvalue > 0.05:
        return "No statistically significant correlation"
    strength = abs(corr)
    if strength > 0.7:
        strength_str = "strong"
    elif strength > 0.4:
        strength_str = "moderate"
    else:
        strength_str = "weak"
    direction = "positive" if corr > 0 else "negative"
    return f"{strength_str.capitalize()} {direction} correlation (statistically significant)"

def correlation_analysis(spec1, spec2):
    df = load_normalized_data()

    if spec1 not in df.columns or spec2 not in df.columns:
        return {"error": f"Could not find specs: {spec1}, {spec2}"}

    col1 = df[spec1].apply(extract_numeric)
    col2 = df[spec2].apply(extract_numeric)

    combined = pd.DataFrame({"x": col1, "y": col2}).dropna()

    if len(combined) < 3:
        return {"error": "Not enough data points for correlation"}

    corr, pvalue = stats.pearsonr(combined["x"], combined["y"])

    return {
        "spec1": spec1,
        "spec2": spec2,
        "correlation": round(float(corr), 4),
        "pvalue": round(float(pvalue), 4),
        "data_points": len(combined),
        "interpretation": interpret_correlation(corr, pvalue)
    }

def outlier_detection(spec):
    df = load_normalized_data()

    if spec not in df.columns:
        return {"error": f"Spec not found: {spec}"}

    data = df[["engine", spec]].copy()
    data["value"] = data[spec].apply(extract_numeric)
    data = data.dropna()

    if len(data) < 3:
        return {"error": "Not enough data"}

    mean = data["value"].mean()
    std = data["value"].std()
    data["zscore"] = (data["value"] - mean) / std
    outliers = data[abs(data["zscore"]) > 2]

    return {
        "spec": spec,
        "mean": round(float(mean), 2),
        "std": round(float(std), 2),
        "outliers": outliers[["engine", "value", "zscore"]].round(2).to_dict("records"),
        "total_engines": len(data)
    }

def regression_analysis(target_spec, predictor_specs):
    df = load_normalized_data()

    if target_spec not in df.columns:
        return {"error": f"Target spec not found: {target_spec}"}

    y = df[target_spec].apply(extract_numeric)

    X_data = {}
    for spec in predictor_specs:
        if spec in df.columns:
            X_data[spec] = df[spec].apply(extract_numeric)

    if not X_data:
        return {"error": "No valid predictor specs found"}

    combined = pd.DataFrame(X_data)
    combined["target"] = y
    combined = combined.dropna()

    if len(combined) < 5:
        return {"error": f"Not enough data for regression, only {len(combined)} complete rows"}

    X = add_constant(combined[list(X_data.keys())])
    y_clean = combined["target"]

    model = OLS(y_clean, X).fit()

    return {
        "target": target_spec,
        "predictors": predictor_specs,
        "r_squared": round(float(model.rsquared), 4),
        "coefficients": {k: round(float(v), 4) for k, v in model.params.items()},
        "pvalues": {k: round(float(v), 4) for k, v in model.pvalues.items()},
        "data_points": len(combined),
        "interpretation": f"Model explains {round(model.rsquared * 100, 1)}% of variance in {target_spec}"
    }

def summary_stats(spec):
    df = load_normalized_data()

    if spec not in df.columns:
        return {"error": f"Spec not found: {spec}"}

    data = df[["engine", spec]].copy()
    data["value"] = data[spec].apply(extract_numeric)
    data = data.dropna()

    if len(data) < 2:
        return {"error": "Not enough data"}

    return {
        "spec": spec,
        "count": len(data),
        "mean": round(float(data["value"].mean()), 2),
        "median": round(float(data["value"].median()), 2),
        "std": round(float(data["value"].std()), 2),
        "min": round(float(data["value"].min()), 2),
        "max": round(float(data["value"].max()), 2),
        "top_engines": data.nlargest(3, "value")[["engine", "value"]].round(2).to_dict("records"),
        "bottom_engines": data.nsmallest(3, "value")[["engine", "value"]].round(2).to_dict("records")
    }

if __name__ == "__main__":
    print("Available numeric specs:")
    specs = available_specs()
    for s in specs:
        print(f"  - {s}")

    print("\nCorrelation: displacement vs power_hp")
    result = correlation_analysis("displacement", "power_hp")
    print(json.dumps(result, indent=2))

    print("\nSummary stats: compression_ratio")
    result = summary_stats("compression_ratio")
    print(json.dumps(result, indent=2))

    print("\nOutlier detection: displacement")
    result = outlier_detection("displacement")
    print(json.dumps(result, indent=2))
