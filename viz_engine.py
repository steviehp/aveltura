"""
viz_engine.py — Vehicle-first Plotly chart generation

Reads export_vehicle_engine.csv (primary) and export_engine_specs.csv (secondary).
Generates interactive HTML charts saved to charts/ directory.
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
import re
from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

COLORS = {
    "bg":       "#080c10",
    "surface":  "#0d1117",
    "border":   "#21262d",
    "accent":   "#00d4aa",
    "text":     "#e6edf3",
    "muted":    "#8b949e",
    "jdm":      "#00d4aa",
    "american": "#ff6b35",
    "european": "#7c4dff",
    "other":    "#f0a500",
    "turbo":    "#ff4757",
    "sc":       "#ffa502",
    "na":       "#2ed573",
}

REGION_COLORS = {
    "JDM":      COLORS["jdm"],
    "American": COLORS["american"],
    "European": COLORS["european"],
    "Other":    COLORS["other"],
}

ASPIRATION_COLORS = {
    "Turbocharged":        COLORS["turbo"],
    "Supercharged":        COLORS["sc"],
    "Naturally Aspirated": COLORS["na"],
}

LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=COLORS["surface"],
    font=dict(color=COLORS["text"], family="'JetBrains Mono', monospace", size=11),
    margin=dict(l=50, r=20, t=60, b=50),
)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_vehicle_data():
    path = os.path.join(EXPORT_DIR, "export_vehicle_engine.csv")
    if not os.path.exists(path):
        # Fall back to engine_applications.csv
        path = os.path.join(BASE_DIR, "engine_applications.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def load_engine_data():
    path = os.path.join(EXPORT_DIR, "export_engine_specs.csv")
    if not os.path.exists(path):
        path = os.path.join(BASE_DIR, "engine_normalized.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def remove_outliers(data, cols):
    for col in cols:
        if col not in data.columns:
            continue
        Q1  = data[col].quantile(0.25)
        Q3  = data[col].quantile(0.75)
        IQR = Q3 - Q1
        data = data[
            (data[col] >= Q1 - 2.0 * IQR) &
            (data[col] <= Q3 + 2.0 * IQR)
        ]
    return data


def label_col(df):
    """Return the best label column available."""
    for col in ["vehicle", "engine_variant", "engine"]:
        if col in df.columns:
            return col
    return df.columns[0]


# ── Chart generators ──────────────────────────────────────────────────────────

def scatter_displacement_power():
    """Displacement vs Power — one dot per vehicle/trim, colored by region."""
    df = load_vehicle_data()
    if df.empty:
        return {"error": "No vehicle data"}

    disp_col = "displacement_cc" if "displacement_cc" in df.columns else \
               "displacement"    if "displacement"    in df.columns else None
    if not disp_col or "power_hp" not in df.columns:
        return {"error": "Missing displacement or power_hp"}

    data = df[[label_col(df), disp_col, "power_hp"] +
              (["region"] if "region" in df.columns else []) +
              (["aspiration"] if "aspiration" in df.columns else []) +
              (["generation"] if "generation" in df.columns else [])
              ].copy()
    data = data.rename(columns={disp_col: "displacement_cc"})
    data = data.dropna(subset=["displacement_cc", "power_hp"])
    data = remove_outliers(data, ["displacement_cc", "power_hp"])

    if len(data) < 3:
        return {"error": "Not enough data"}

    hover_label = label_col(data)
    color_col   = "region" if "region" in data.columns else None

    fig = px.scatter(
        data,
        x="displacement_cc",
        y="power_hp",
        color=color_col,
        color_discrete_map=REGION_COLORS if color_col else None,
        hover_name=hover_label,
        hover_data={c: True for c in ["generation", "aspiration"]
                    if c in data.columns},
        trendline="ols",
        trendline_color_override=COLORS["accent"],
        labels={"displacement_cc": "Displacement (cc)", "power_hp": "Power (hp)"},
        title="Vehicle Displacement vs Power Output",
        template="plotly_dark",
    )
    fig.update_traces(marker=dict(size=7, opacity=0.85))
    fig.update_layout(**LAYOUT)

    path = os.path.join(CHARTS_DIR, "scatter_displacement_power_hp.html")
    fig.write_html(path)
    return {"chart": "scatter_displacement_power_hp.html", "data_points": len(data)}


def bar_top_power(top_n=20):
    """Top N vehicles by power output."""
    df = load_vehicle_data()
    if df.empty or "power_hp" not in df.columns:
        return {"error": "No data"}

    lbl  = label_col(df)
    cols = [lbl, "power_hp"] + \
           (["region"] if "region" in df.columns else []) + \
           (["generation"] if "generation" in df.columns else []) + \
           (["trim"] if "trim" in df.columns else [])
    data = df[cols].dropna(subset=["power_hp"])
    data = remove_outliers(data, ["power_hp"])

    # Build display label
    if "generation" in data.columns and "trim" in data.columns:
        data["display"] = data[lbl].astype(str) + " " + \
                          data["generation"].fillna("").astype(str) + " " + \
                          data["trim"].fillna("").astype(str)
        data["display"] = data["display"].str.strip()
    else:
        data["display"] = data[lbl]

    data = data.nlargest(top_n, "power_hp")

    fig = px.bar(
        data,
        x="power_hp",
        y="display",
        orientation="h",
        color="region" if "region" in data.columns else None,
        color_discrete_map=REGION_COLORS,
        labels={"power_hp": "Power (hp)", "display": ""},
        title=f"Top {top_n} Vehicles by Power Output",
        template="plotly_dark",
    )
    fig.update_layout(**LAYOUT, yaxis=dict(autorange="reversed"), showlegend=True)

    path = os.path.join(CHARTS_DIR, f"bar_power_hp_top{top_n}.html")
    fig.write_html(path)
    return {"chart": f"bar_power_hp_top{top_n}.html", "data_points": len(data)}


def histogram_compression():
    """Distribution of compression ratios from engine specs."""
    df = load_engine_data()
    if df.empty or "compression_ratio" not in df.columns:
        return {"error": "No compression ratio data"}

    data = df[["compression_ratio"]].dropna()
    data = remove_outliers(data, ["compression_ratio"])

    if len(data) < 3:
        return {"error": "Not enough data"}

    fig = px.histogram(
        data,
        x="compression_ratio",
        nbins=20,
        title="Distribution of Engine Compression Ratios",
        template="plotly_dark",
        color_discrete_sequence=[COLORS["accent"]],
        labels={"compression_ratio": "Compression Ratio"},
    )
    fig.update_layout(**LAYOUT)

    path = os.path.join(CHARTS_DIR, "hist_compression_ratio.html")
    fig.write_html(path)
    return {"chart": "hist_compression_ratio.html", "data_points": len(data)}


def bar_hp_per_litre(top_n=15):
    """Top N vehicles by specific power output (HP per litre)."""
    df = load_vehicle_data()
    if df.empty:
        return {"error": "No vehicle data"}

    if "hp_per_litre" not in df.columns:
        # Calculate it
        disp_col = "displacement_cc" if "displacement_cc" in df.columns else \
                   "displacement"    if "displacement"    in df.columns else None
        if disp_col and "power_hp" in df.columns:
            df["hp_per_litre"] = df.apply(
                lambda r: round(float(r["power_hp"]) / (float(r[disp_col]) / 1000), 1)
                if pd.notna(r.get("power_hp")) and pd.notna(r.get(disp_col))
                and float(r.get(disp_col, 0)) > 0
                else None,
                axis=1
            )
        else:
            return {"error": "Cannot calculate hp_per_litre"}

    lbl  = label_col(df)
    cols = [lbl, "hp_per_litre"] + \
           (["aspiration"] if "aspiration" in df.columns else []) + \
           (["generation"]  if "generation"  in df.columns else []) + \
           (["trim"]        if "trim"        in df.columns else [])
    data = df[cols].dropna(subset=["hp_per_litre"])
    data = remove_outliers(data, ["hp_per_litre"])

    if "generation" in data.columns and "trim" in data.columns:
        data["display"] = data[lbl].astype(str) + " " + \
                          data["generation"].fillna("").astype(str) + " " + \
                          data["trim"].fillna("").astype(str)
        data["display"] = data["display"].str.strip()
    else:
        data["display"] = data[lbl]

    data = data.nlargest(top_n, "hp_per_litre")

    fig = px.bar(
        data,
        x="hp_per_litre",
        y="display",
        orientation="h",
        color="aspiration" if "aspiration" in data.columns else None,
        color_discrete_map=ASPIRATION_COLORS,
        labels={"hp_per_litre": "HP / Litre", "display": ""},
        title=f"Top {top_n} Vehicles by Specific Power (HP/L)",
        template="plotly_dark",
    )
    fig.update_layout(**LAYOUT, yaxis=dict(autorange="reversed"))

    path = os.path.join(CHARTS_DIR, "bar_hp_per_litre.html")
    fig.write_html(path)
    return {"chart": "bar_hp_per_litre.html", "data_points": len(data)}


def correlation_heatmap():
    """Correlation heatmap of numeric engine specs."""
    df = load_engine_data()
    if df.empty:
        return {"error": "No engine data"}

    numeric_cols = []
    for col in ["displacement", "power_hp", "torque_nm", "bore_mm",
                "stroke_mm", "compression_ratio", "redline_rpm", "hp_per_litre"]:
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            if series.notna().sum() > 10:
                df[col] = series
                numeric_cols.append(col)

    if len(numeric_cols) < 2:
        return {"error": "Not enough numeric columns"}

    corr_matrix = df[numeric_cols].corr()

    fig = px.imshow(
        corr_matrix,
        title="Engine Spec Correlation Heatmap",
        template="plotly_dark",
        color_continuous_scale=["#ff4444", "#111", "#00ff88"],
        zmin=-1, zmax=1,
    )
    fig.update_layout(**LAYOUT)

    path = os.path.join(CHARTS_DIR, "heatmap_correlations.html")
    fig.write_html(path)
    return {"chart": "heatmap_correlations.html", "specs": numeric_cols}


def bar_vehicles_by_era():
    """Stacked bar — vehicle count by era and region."""
    df = load_vehicle_data()
    if df.empty or "era" not in df.columns:
        return {"error": "No era data"}

    lbl  = label_col(df)
    cols = [lbl, "era"] + (["region"] if "region" in df.columns else [])
    data = df[cols].dropna(subset=["era"])

    era_order = ["Classic (pre-1970)", "70s", "80s", "90s",
                 "2000s", "2010s", "2020s+", "Unknown"]

    if "region" in data.columns:
        grouped = data.groupby(["era", "region"]).size().reset_index(name="count")
    else:
        grouped = data.groupby("era").size().reset_index(name="count")
        grouped["region"] = "All"

    fig = px.bar(
        grouped,
        x="era",
        y="count",
        color="region" if "region" in grouped.columns else None,
        color_discrete_map=REGION_COLORS,
        category_orders={"era": era_order},
        labels={"era": "Era", "count": "Vehicle Count"},
        title="Vehicles by Era and Region",
        template="plotly_dark",
    )
    fig.update_layout(**LAYOUT)

    path = os.path.join(CHARTS_DIR, "bar_vehicles_by_era.html")
    fig.write_html(path)
    return {"chart": "bar_vehicles_by_era.html", "data_points": len(data)}


def scatter_plot(x_spec, y_spec, title=None):
    """Generic scatter for server.py /viz/scatter endpoint."""
    df = load_vehicle_data()
    if df.empty:
        df = load_engine_data()
    if df.empty:
        return {"error": "No data"}

    if x_spec not in df.columns or y_spec not in df.columns:
        return {"error": f"Columns not found: {x_spec}, {y_spec}"}

    lbl  = label_col(df)
    data = df[[lbl, x_spec, y_spec]].dropna()
    data = remove_outliers(data, [x_spec, y_spec])

    if len(data) < 3:
        return {"error": "Not enough data"}

    fig = px.scatter(
        data, x=x_spec, y=y_spec,
        hover_name=lbl,
        title=title or f"{x_spec} vs {y_spec}",
        template="plotly_dark",
        color_discrete_sequence=[COLORS["accent"]],
        trendline="ols",
    )
    fig.update_layout(**LAYOUT)

    filename = f"scatter_{x_spec}_{y_spec}.html"
    fig.write_html(os.path.join(CHARTS_DIR, filename))
    return {"chart": filename, "data_points": len(data)}


def bar_chart(spec, top_n=20, title=None):
    """Generic bar for server.py /viz/bar endpoint."""
    df = load_vehicle_data()
    if df.empty:
        df = load_engine_data()
    if df.empty or spec not in df.columns:
        return {"error": f"Spec {spec} not found"}

    lbl  = label_col(df)
    data = df[[lbl, spec]].dropna()
    data = remove_outliers(data, [spec])
    data = data.nlargest(top_n, spec)

    fig = px.bar(
        data, x=spec, y=lbl,
        orientation="h",
        title=title or f"Top {top_n} by {spec}",
        template="plotly_dark",
        color_discrete_sequence=[COLORS["accent"]],
    )
    fig.update_layout(**LAYOUT, yaxis=dict(autorange="reversed"))

    filename = f"bar_{spec}_top{top_n}.html"
    fig.write_html(os.path.join(CHARTS_DIR, filename))
    return {"chart": filename, "data_points": len(data)}


def histogram(spec, title=None):
    """Generic histogram for server.py /viz/histogram endpoint."""
    df = load_vehicle_data()
    if df.empty:
        df = load_engine_data()
    if df.empty or spec not in df.columns:
        return {"error": f"Spec {spec} not found"}

    data = df[[spec]].dropna()
    data = remove_outliers(data, [spec])

    if len(data) < 3:
        return {"error": "Not enough data"}

    fig = px.histogram(
        data, x=spec, nbins=20,
        title=title or f"Distribution of {spec}",
        template="plotly_dark",
        color_discrete_sequence=[COLORS["accent"]],
    )
    fig.update_layout(**LAYOUT)

    filename = f"hist_{spec}.html"
    fig.write_html(os.path.join(CHARTS_DIR, filename))
    return {"chart": filename, "data_points": len(data)}


def compare_engines(engines, spec):
    """Compare specific vehicles/engines — for server.py /viz/compare endpoint."""
    df = load_vehicle_data()
    if df.empty:
        df = load_engine_data()
    if df.empty:
        return {"error": "No data"}

    lbl  = label_col(df)
    data = df[df[lbl].isin(engines)][[lbl, spec]].dropna()

    if data.empty:
        return {"error": "No data found for these vehicles/engines"}

    fig = px.bar(
        data, x=lbl, y=spec,
        title=f"Comparison: {spec}",
        template="plotly_dark",
        color=lbl,
    )
    fig.update_layout(**LAYOUT)

    filename = f"compare_{spec}.html"
    fig.write_html(os.path.join(CHARTS_DIR, filename))
    return {"chart": filename, "data_points": len(data)}


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating charts...")

    results = [
        ("Scatter displacement vs power",  scatter_displacement_power()),
        ("Bar top 20 by power",            bar_top_power(top_n=20)),
        ("Bar top 15 HP/litre",            bar_hp_per_litre(top_n=15)),
        ("Histogram compression ratio",    histogram_compression()),
        ("Correlation heatmap",            correlation_heatmap()),
        ("Bar vehicles by era",            bar_vehicles_by_era()),
    ]

    for name, result in results:
        if "error" in result:
            print(f"  {name}: ERROR — {result['error']}")
        else:
            print(f"  {name}: {result.get('chart')} ({result.get('data_points','?')} pts)")

    print(f"\nCharts saved to {CHARTS_DIR}")
