import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
import re
import json
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

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

def remove_outliers(data, cols):
    for col in cols:
        Q1 = data[col].quantile(0.25)
        Q3 = data[col].quantile(0.75)
        IQR = Q3 - Q1
        data = data[(data[col] >= Q1 - 1.5 * IQR) & (data[col] <= Q3 + 1.5 * IQR)]
    return data

def scatter_plot(x_spec, y_spec, title=None):
    df = load_normalized_data()
    data = df[["engine", x_spec, y_spec]].copy()
    data[x_spec] = data[x_spec].apply(extract_numeric)
    data[y_spec] = data[y_spec].apply(extract_numeric)
    data = data.dropna()

    if len(data) < 3:
        return {"error": "Not enough data"}

    data = remove_outliers(data, [x_spec, y_spec])

    if len(data) < 3:
        return {"error": "Not enough data after outlier removal"}

    fig = px.scatter(
        data, x=x_spec, y=y_spec,
        hover_name="engine",
        title=title or f"{x_spec} vs {y_spec}",
        template="plotly_dark",
        color_discrete_sequence=["#00ff88"],
        trendline="ols"
    )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#111",
        font=dict(color="#e0e0e0", family="Courier New"),
    )

    filename = f"scatter_{x_spec}_{y_spec}.html"
    filepath = os.path.join(CHARTS_DIR, filename)
    fig.write_html(filepath)
    return {"chart": filename, "data_points": len(data)}

def bar_chart(spec, top_n=20, title=None):
    df = load_normalized_data()
    data = df[["engine", spec]].copy()
    data[spec] = data[spec].apply(extract_numeric)
    data = data.dropna()

    data = remove_outliers(data, [spec])
    data = data.nlargest(top_n, spec)

    if len(data) < 2:
        return {"error": "Not enough data"}

    fig = px.bar(
        data, x="engine", y=spec,
        title=title or f"Top {top_n} engines by {spec}",
        template="plotly_dark",
        color=spec,
        color_continuous_scale=["#111", "#00ff88"]
    )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#111",
        font=dict(color="#e0e0e0", family="Courier New"),
        xaxis_tickangle=-45
    )

    filename = f"bar_{spec}_top{top_n}.html"
    filepath = os.path.join(CHARTS_DIR, filename)
    fig.write_html(filepath)
    return {"chart": filename, "data_points": len(data)}

def histogram(spec, title=None):
    df = load_normalized_data()
    data = df[["engine", spec]].copy()
    data[spec] = data[spec].apply(extract_numeric)
    data = data.dropna()

    data = remove_outliers(data, [spec])

    if len(data) < 3:
        return {"error": "Not enough data"}

    fig = px.histogram(
        data, x=spec,
        title=title or f"Distribution of {spec}",
        template="plotly_dark",
        color_discrete_sequence=["#00ff88"],
        nbins=20
    )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#111",
        font=dict(color="#e0e0e0", family="Courier New"),
    )

    filename = f"hist_{spec}.html"
    filepath = os.path.join(CHARTS_DIR, filename)
    fig.write_html(filepath)
    return {"chart": filename, "data_points": len(data)}

def correlation_heatmap():
    df = load_normalized_data()
    numeric_cols = []
    for col in df.columns:
        if col == "engine":
            continue
        numeric = df[col].apply(extract_numeric)
        if numeric.notna().sum() > 10:
            df[col] = numeric
            numeric_cols.append(col)

    if len(numeric_cols) < 2:
        return {"error": "Not enough numeric columns"}

    corr_matrix = df[numeric_cols].corr()

    fig = px.imshow(
        corr_matrix,
        title="Engine Spec Correlation Heatmap",
        template="plotly_dark",
        color_continuous_scale=["#ff4444", "#111", "#00ff88"],
        zmin=-1, zmax=1
    )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        font=dict(color="#e0e0e0", family="Courier New"),
    )

    filename = "heatmap_correlations.html"
    filepath = os.path.join(CHARTS_DIR, filename)
    fig.write_html(filepath)
    return {"chart": filename, "specs": numeric_cols}

def compare_engines(engines, spec):
    df = load_normalized_data()
    data = df[df["engine"].isin(engines)][["engine", spec]].copy()
    data[spec] = data[spec].apply(extract_numeric)
    data = data.dropna()

    if len(data) < 1:
        return {"error": "No data found for these engines"}

    fig = px.bar(
        data, x="engine", y=spec,
        title=f"Engine Comparison: {spec}",
        template="plotly_dark",
        color="engine"
    )
    fig.update_layout(
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#111",
        font=dict(color="#e0e0e0", family="Courier New"),
    )

    filename = f"compare_{spec}.html"
    filepath = os.path.join(CHARTS_DIR, filename)
    fig.write_html(filepath)
    return {"chart": filename, "data_points": len(data)}

if __name__ == "__main__":
    print("Generating test charts...")

    result = scatter_plot("displacement", "power_hp")
    print(f"Scatter plot: {result}")

    result = bar_chart("power_hp", top_n=15)
    print(f"Bar chart: {result}")

    result = histogram("compression_ratio")
    print(f"Histogram: {result}")

    result = correlation_heatmap()
    print(f"Heatmap: {result}")

    print(f"\nCharts saved to {CHARTS_DIR}")
