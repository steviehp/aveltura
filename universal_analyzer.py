"""
universal_analyzer.py — Phase 14a: Universal Dataset Optimizer

Accepts tabular data as a string (CSV or TSV format).
Runs full statistical analysis + optimization.
Returns findings as formatted text with chart paths.

Pipeline:
  parse_data()          → detect delimiter, load into DataFrame
  profile_columns()     → types, distributions, missing data
  detect_relationships() → correlation, regression, clustering
  detect_target()       → auto-detect optimization target column
  optimize()            → scipy minimize/maximize
  format_output()       → text summary + chart generation
"""

import os
import io
import re
import json
import logging
import warnings
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

load_dotenv()
BASE_DIR    = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
CHARTS_DIR  = os.path.join(BASE_DIR, "charts")
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR,  exist_ok=True)

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "analyzer.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ── Target column hints ───────────────────────────────────────────────────────

TARGET_HINTS_MAXIMIZE = [
    "power", "hp", "torque", "speed", "performance", "score",
    "output", "revenue", "profit", "efficiency", "yield",
    "accuracy", "rating", "grade", "lap", "result",
]
TARGET_HINTS_MINIMIZE = [
    "time", "cost", "weight", "drag", "loss", "error",
    "waste", "fuel", "consumption", "failure", "risk",
    "latency", "delay", "defect",
]

# ── Data parsing ──────────────────────────────────────────────────────────────

def detect_delimiter(text):
    """Detect CSV delimiter from first few lines."""
    sample = "\n".join(text.strip().split("\n")[:5])
    counts = {
        ",":  sample.count(","),
        "\t": sample.count("\t"),
        ";":  sample.count(";"),
        "|":  sample.count("|"),
    }
    return max(counts, key=counts.get)


def parse_data(text):
    """
    Parse tabular text data into a DataFrame.
    Handles CSV, TSV, pipe-delimited, and markdown tables.
    Returns (df, delimiter, error_message)
    """
    text = text.strip()

    # Strip markdown table formatting
    if "|" in text and "---" in text:
        lines = [l for l in text.split("\n")
                 if not re.match(r'\s*\|?\s*[-:]+\s*\|', l)]
        text = "\n".join(lines)
        text = re.sub(r'^\||\|$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\|', ',', text)

    delim = detect_delimiter(text)

    try:
        df = pd.read_csv(io.StringIO(text), sep=delim, engine="python")
        df.columns = [c.strip() for c in df.columns]

        # Drop unnamed index columns
        df = df.loc[:, ~df.columns.str.match(r'^Unnamed')]

        # Strip whitespace from string values
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].str.strip()

        # Try to convert string columns to numeric where possible
        for col in df.columns:
            if df[col].dtype == object:
                converted = pd.to_numeric(df[col], errors="coerce")
                if converted.notna().sum() / max(len(df), 1) > 0.7:
                    df[col] = converted

        if len(df) < 2:
            return None, delim, "Dataset too small — need at least 2 rows"

        return df, delim, None

    except Exception as e:
        return None, delim, f"Could not parse data: {e}"


# ── Column profiling ──────────────────────────────────────────────────────────

def profile_columns(df):
    """
    Profile each column — type, stats, missing data, distribution shape.
    Returns dict of column profiles.
    """
    profiles = {}

    for col in df.columns:
        series = df[col]
        profile = {
            "name":       col,
            "dtype":      str(series.dtype),
            "n_total":    len(series),
            "n_missing":  series.isna().sum(),
            "pct_missing": round(series.isna().mean() * 100, 1),
            "n_unique":   series.nunique(),
        }

        if pd.api.types.is_numeric_dtype(series):
            profile["type"]    = "numeric"
            clean              = series.dropna()
            profile["mean"]    = round(float(clean.mean()), 3) if len(clean) else None
            profile["median"]  = round(float(clean.median()), 3) if len(clean) else None
            profile["std"]     = round(float(clean.std()), 3) if len(clean) else None
            profile["min"]     = round(float(clean.min()), 3) if len(clean) else None
            profile["max"]     = round(float(clean.max()), 3) if len(clean) else None
            profile["q25"]     = round(float(clean.quantile(0.25)), 3) if len(clean) else None
            profile["q75"]     = round(float(clean.quantile(0.75)), 3) if len(clean) else None
            profile["skew"]    = round(float(clean.skew()), 3) if len(clean) > 2 else None
            profile["kurtosis"]= round(float(clean.kurtosis()), 3) if len(clean) > 3 else None

            # Outlier detection (IQR method)
            if len(clean) >= 4:
                Q1, Q3 = clean.quantile(0.25), clean.quantile(0.75)
                IQR    = Q3 - Q1
                outliers = clean[(clean < Q1 - 1.5*IQR) | (clean > Q3 + 1.5*IQR)]
                profile["n_outliers"]      = len(outliers)
                profile["outlier_values"]  = outliers.tolist()[:5]
            else:
                profile["n_outliers"] = 0

            # Distribution shape
            if profile["skew"] is not None:
                if abs(profile["skew"]) < 0.5:
                    profile["distribution"] = "normal"
                elif profile["skew"] > 1:
                    profile["distribution"] = "right_skewed"
                elif profile["skew"] < -1:
                    profile["distribution"] = "left_skewed"
                else:
                    profile["distribution"] = "slight_skew"

        elif series.nunique() <= 20:
            profile["type"]       = "categorical"
            profile["categories"] = series.value_counts().to_dict()
            profile["top_value"]  = series.mode()[0] if not series.empty else None

        else:
            profile["type"] = "text"

        profiles[col] = profile

    return profiles


# ── Relationship detection ────────────────────────────────────────────────────

def detect_correlations(df):
    """
    Compute Pearson correlation matrix for all numeric columns.
    Returns (corr_matrix, top_pairs)
    """
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return None, []

    corr = numeric_df.corr(method="pearson")

    # Extract top correlated pairs
    pairs = []
    cols  = corr.columns.tolist()
    for i in range(len(cols)):
        for j in range(i+1, len(cols)):
            r = corr.iloc[i, j]
            if not np.isnan(r):
                pairs.append({
                    "col1":        cols[i],
                    "col2":        cols[j],
                    "correlation": round(r, 3),
                    "strength":    _correlation_strength(r),
                    "direction":   "positive" if r > 0 else "negative",
                })

    pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
    return corr, pairs


def _correlation_strength(r):
    a = abs(r)
    if a >= 0.9: return "very strong"
    if a >= 0.7: return "strong"
    if a >= 0.5: return "moderate"
    if a >= 0.3: return "weak"
    return "negligible"


def detect_target(df, profiles, user_hint=None):
    """
    Auto-detect the most likely target/output column.
    Returns (column_name, direction, confidence)
    direction: 'maximize' | 'minimize'
    """
    if user_hint and user_hint in df.columns:
        col   = user_hint
        col_l = col.lower()
        direction = "minimize" if any(h in col_l for h in TARGET_HINTS_MINIMIZE) \
                    else "maximize"
        return col, direction, 1.0

    numeric_cols = [col for col, p in profiles.items() if p["type"] == "numeric"]
    if not numeric_cols:
        return None, None, 0.0

    # Check name hints
    for col in numeric_cols:
        col_l = col.lower()
        if any(h in col_l for h in TARGET_HINTS_MINIMIZE):
            return col, "minimize", 0.9
        if any(h in col_l for h in TARGET_HINTS_MAXIMIZE):
            return col, "maximize", 0.9

    # Fall back to highest mean absolute correlation with others
    numeric_df = df[numeric_cols].dropna()
    if numeric_df.shape[1] < 2:
        return numeric_cols[-1], "maximize", 0.5

    corr = numeric_df.corr().abs()
    mean_corr = corr.mean()
    best_col  = mean_corr.idxmax()
    col_l     = best_col.lower()
    direction = "minimize" if any(h in col_l for h in TARGET_HINTS_MINIMIZE) \
                else "maximize"

    return best_col, direction, 0.6


def run_regression(df, target_col):
    """
    OLS regression — target vs all other numeric columns.
    Returns feature importance dict.
    """
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import r2_score

        numeric_df = df.select_dtypes(include=[np.number]).dropna()
        if target_col not in numeric_df.columns:
            return None

        feature_cols = [c for c in numeric_df.columns if c != target_col]
        if not feature_cols:
            return None

        X = numeric_df[feature_cols].values
        y = numeric_df[target_col].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = LinearRegression()
        model.fit(X_scaled, y)
        y_pred = model.predict(X_scaled)
        r2     = r2_score(y, y_pred)

        importance = {
            col: round(abs(coef), 4)
            for col, coef in zip(feature_cols, model.coef_)
        }
        importance = dict(sorted(importance.items(),
                                 key=lambda x: x[1], reverse=True))

        return {
            "r2_score":        round(r2, 4),
            "feature_importance": importance,
            "model_quality":   _r2_quality(r2),
        }
    except ImportError:
        return _simple_regression(df, target_col)
    except Exception as e:
        logging.error(f"Regression failed: {e}")
        return None


def _simple_regression(df, target_col):
    """Fallback regression without sklearn using numpy."""
    try:
        numeric_df = df.select_dtypes(include=[np.number]).dropna()
        feature_cols = [c for c in numeric_df.columns if c != target_col]
        if not feature_cols:
            return None

        importance = {}
        y = numeric_df[target_col].values

        for col in feature_cols:
            x   = numeric_df[col].values
            if np.std(x) == 0:
                continue
            corr = np.corrcoef(x, y)[0, 1]
            importance[col] = round(abs(corr), 4)

        importance = dict(sorted(importance.items(),
                                 key=lambda x: x[1], reverse=True))

        # Rough R2 estimate from top feature correlation
        top_corr = list(importance.values())[0] if importance else 0
        r2       = round(top_corr ** 2, 4)

        return {
            "r2_score":           r2,
            "feature_importance": importance,
            "model_quality":      _r2_quality(r2),
        }
    except Exception as e:
        logging.error(f"Simple regression failed: {e}")
        return None


def _r2_quality(r2):
    if r2 >= 0.9: return "excellent fit"
    if r2 >= 0.7: return "good fit"
    if r2 >= 0.5: return "moderate fit"
    if r2 >= 0.3: return "weak fit"
    return "poor fit — likely non-linear relationships"


# ── Optimization solver ───────────────────────────────────────────────────────

def optimize_target(df, target_col, direction, regression_result):
    """
    Find optimal values of feature columns to maximize/minimize target.
    Uses scipy minimize with bounds from data distribution.
    Returns optimal_values dict.
    """
    try:
        from scipy.optimize import minimize

        numeric_df = df.select_dtypes(include=[np.number]).dropna()
        feature_cols = [c for c in numeric_df.columns if c != target_col]

        if not feature_cols or regression_result is None:
            return None

        # Get importance weights
        importance = regression_result.get("feature_importance", {})
        weights    = np.array([importance.get(c, 0.1) for c in feature_cols])

        # Current means as starting point
        x0     = numeric_df[feature_cols].mean().values
        bounds = [
            (numeric_df[col].min(), numeric_df[col].max())
            for col in feature_cols
        ]

        # Compute actual correlations with target
        corrs = np.array([
            np.corrcoef(numeric_df[col].values, numeric_df[target_col].values)[0,1]
            if target_col in numeric_df.columns else 0
            for col in feature_cols
        ])

        # Zero out weak correlations (|r| < 0.3) — avoid spurious recommendations
        signed_weights = np.where(np.abs(corrs) >= 0.3, corrs * weights, 0)

        # Linear model objective using signed correlation-weighted importance
        def objective(x):
            delta = (x - x0) / (np.abs(x0) + 1e-10)
            pred  = np.dot(delta, signed_weights)
            return -pred if direction == "maximize" else pred

        result = minimize(
            objective, x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 1000}
        )

        if result.success:
            optimal = {
                col: round(float(val), 3)
                for col, val in zip(feature_cols, result.x)
            }
            current = {
                col: round(float(numeric_df[col].mean()), 3)
                for col in feature_cols
            }
            delta = {
                col: round(optimal[col] - current[col], 3)
                for col in feature_cols
            }
            return {
                "optimal_values": optimal,
                "current_avg":    current,
                "delta":          delta,
                "converged":      True,
            }

    except ImportError:
        pass
    except Exception as e:
        logging.error(f"Optimization failed: {e}")

    # Fallback — use percentile approach
    try:
        numeric_df  = df.select_dtypes(include=[np.number]).dropna()
        feature_cols = [c for c in numeric_df.columns if c != target_col]
        importance   = regression_result.get("feature_importance", {}) \
                       if regression_result else {}

        optimal = {}
        current = {}
        delta   = {}

        for col in feature_cols:
            imp = importance.get(col, 0)
            cur = float(numeric_df[col].mean())
            current[col] = round(cur, 3)

            if direction == "maximize":
                # Push positively correlated features up, negative down
                corr = np.corrcoef(
                    numeric_df[col].values,
                    numeric_df[target_col].values
                )[0, 1] if target_col in numeric_df.columns else 0
                opt = float(numeric_df[col].quantile(0.85)) if corr > 0 \
                      else float(numeric_df[col].quantile(0.15))
            else:
                corr = np.corrcoef(
                    numeric_df[col].values,
                    numeric_df[target_col].values
                )[0, 1] if target_col in numeric_df.columns else 0
                opt = float(numeric_df[col].quantile(0.15)) if corr > 0 \
                      else float(numeric_df[col].quantile(0.85))

            optimal[col] = round(opt, 3)
            delta[col]   = round(opt - cur, 3)

        return {
            "optimal_values": optimal,
            "current_avg":    current,
            "delta":          delta,
            "converged":      False,
            "note":           "Estimated using percentile method (scipy not available)"
        }
    except Exception as e:
        logging.error(f"Fallback optimization failed: {e}")
        return None


# ── Chart generation ──────────────────────────────────────────────────────────

DARK_THEME = dict(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#161b22",
    font=dict(color="#e6edf3", family="'JetBrains Mono', monospace", size=11),
    margin=dict(l=40, r=20, t=50, b=40),
)


def generate_charts(df, profiles, corr_matrix, target_col, report_id):
    """Generate all charts and save as HTML files. Returns list of chart paths."""
    chart_paths = []
    numeric_df  = df.select_dtypes(include=[np.number])

    # ── 1. Correlation heatmap ────────────────────────────────────────────────
    if corr_matrix is not None and corr_matrix.shape[0] > 1:
        fig = px.imshow(
            corr_matrix,
            title="Correlation Matrix",
            color_continuous_scale=["#ff4757", "#161b22", "#00d4aa"],
            zmin=-1, zmax=1,
            text_auto=".2f",
        )
        fig.update_layout(**DARK_THEME)
        path = os.path.join(REPORTS_DIR, f"{report_id}_heatmap.html")
        fig.write_html(path)
        chart_paths.append(("Correlation Heatmap", path))

    # ── 2. Distribution plots ─────────────────────────────────────────────────
    numeric_cols = [c for c, p in profiles.items() if p["type"] == "numeric"]
    if len(numeric_cols) >= 2:
        n_cols = min(len(numeric_cols), 4)
        fig    = make_subplots(
            rows=1, cols=n_cols,
            subplot_titles=numeric_cols[:n_cols]
        )
        for i, col in enumerate(numeric_cols[:n_cols]):
            fig.add_trace(
                go.Histogram(
                    x=df[col].dropna(),
                    name=col,
                    marker_color="#00d4aa",
                    opacity=0.8,
                ),
                row=1, col=i+1
            )
        fig.update_layout(**DARK_THEME, title="Variable Distributions",
                          showlegend=False)
        path = os.path.join(REPORTS_DIR, f"{report_id}_distributions.html")
        fig.write_html(path)
        chart_paths.append(("Distributions", path))

    # ── 3. Target vs features scatter ─────────────────────────────────────────
    if target_col and target_col in df.columns:
        feature_cols = [c for c in numeric_cols
                        if c != target_col][:3]
        for feat in feature_cols:
            fig = px.scatter(
                df, x=feat, y=target_col,
                trendline="ols",
                trendline_color_override="#ff6b35",
                title=f"{feat} vs {target_col}",
                color_discrete_sequence=["#00d4aa"],
            )
            if "car" in df.columns or "name" in df.columns:
                label_col = "car" if "car" in df.columns else "name"
                fig = px.scatter(
                    df, x=feat, y=target_col,
                    hover_name=label_col,
                    trendline="ols",
                    trendline_color_override="#ff6b35",
                    title=f"{feat} vs {target_col}",
                    color_discrete_sequence=["#00d4aa"],
                )
            fig.update_layout(**DARK_THEME)
            path = os.path.join(REPORTS_DIR,
                                f"{report_id}_scatter_{feat}_vs_{target_col}.html")
            fig.write_html(path)
            chart_paths.append((f"{feat} vs {target_col}", path))

    # ── 4. Bar chart — target ranking ─────────────────────────────────────────
    if target_col and target_col in df.columns:
        label_col = None
        for c in ["car", "name", "vehicle", "model", "id", "label"]:
            if c in df.columns:
                label_col = c
                break

        if label_col:
            plot_df = df[[label_col, target_col]].dropna().sort_values(
                target_col, ascending=False
            )
            fig = px.bar(
                plot_df, x=target_col, y=label_col,
                orientation="h",
                title=f"Ranking by {target_col}",
                color=target_col,
                color_continuous_scale=["#21262d", "#00d4aa"],
            )
            fig.update_layout(**DARK_THEME,
                              yaxis=dict(autorange="reversed"),
                              coloraxis_showscale=False)
            path = os.path.join(REPORTS_DIR, f"{report_id}_ranking.html")
            fig.write_html(path)
            chart_paths.append((f"{target_col} Ranking", path))

    return chart_paths


# ── Full report builder ───────────────────────────────────────────────────────

def build_html_report(df, profiles, corr_pairs, regression,
                      optimization, target_col, direction,
                      chart_paths, report_id):
    """Build a self-contained HTML report."""

    charts_html = ""
    for chart_name, chart_path in chart_paths:
        # Read chart HTML and embed inline
        try:
            with open(chart_path) as f:
                chart_content = f.read()
            # Extract just the div and script from the Plotly HTML
            div_match = re.search(
                r'<div id="[^"]*".*?</div>\s*<script.*?</script>',
                chart_content, re.DOTALL
            )
            if div_match:
                charts_html += f"""
                <div class="chart-section">
                    <h3>{chart_name}</h3>
                    {div_match.group(0)}
                </div>"""
        except Exception:
            charts_html += f'<p>Chart: {chart_name} — <a href="{chart_path}">open separately</a></p>'

    # Key findings
    findings = []
    if corr_pairs:
        top = corr_pairs[0]
        findings.append(
            f"Strongest relationship: <strong>{top['col1']}</strong> and "
            f"<strong>{top['col2']}</strong> "
            f"({top['strength']} {top['direction']} correlation, r={top['correlation']})"
        )
    if regression:
        top_feat = list(regression["feature_importance"].keys())[0] if \
                   regression["feature_importance"] else None
        if top_feat:
            findings.append(
                f"Most influential variable: <strong>{top_feat}</strong> "
                f"(model R²={regression['r2_score']} — {regression['model_quality']})"
            )
    if optimization:
        findings.append(
            f"Optimization target: <strong>{target_col}</strong> "
            f"({direction})"
        )

    opt_table = ""
    if optimization:
        rows = ""
        for col, opt_val in optimization["optimal_values"].items():
            cur_val = optimization["current_avg"].get(col, "—")
            delta   = optimization["delta"].get(col, 0)
            arrow   = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            color   = "#00d4aa" if delta > 0 else "#ff6b35" if delta < 0 else "#8b949e"
            rows += f"""
            <tr>
                <td>{col}</td>
                <td>{cur_val}</td>
                <td style="color:{color}">{opt_val} {arrow}</td>
                <td style="color:{color}">{'+' if delta > 0 else ''}{delta}</td>
            </tr>"""
        opt_table = f"""
        <table class="opt-table">
            <thead><tr>
                <th>Variable</th><th>Current Avg</th>
                <th>Optimal</th><th>Change</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vel Analysis Report — {report_id}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#070a0d; color:#e6edf3;
          font-family:'JetBrains Mono',monospace; padding:32px; }}
  h1 {{ font-size:28px; color:#00d4aa; margin-bottom:4px; }}
  h2 {{ font-size:16px; color:#00d4aa; margin:24px 0 12px;
        border-bottom:1px solid #21262d; padding-bottom:6px; }}
  h3 {{ font-size:13px; color:#8b949e; margin:16px 0 8px; }}
  .meta {{ font-size:11px; color:#5a7080; margin-bottom:32px; }}
  .findings {{ background:#0c1015; border:1px solid #21262d;
               border-radius:8px; padding:20px; margin-bottom:24px; }}
  .finding {{ padding:6px 0; font-size:13px; color:#a0b8c8;
              border-bottom:1px solid #1c2530; }}
  .finding:last-child {{ border-bottom:none; }}
  .stat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
                gap:12px; margin-bottom:24px; }}
  .stat-card {{ background:#0c1015; border:1px solid #21262d;
                border-radius:8px; padding:16px; }}
  .stat-card .label {{ font-size:10px; color:#5a7080; letter-spacing:2px;
                        text-transform:uppercase; margin-bottom:4px; }}
  .stat-card .value {{ font-size:20px; color:#e6edf3; }}
  .corr-table, .opt-table {{ width:100%; border-collapse:collapse;
                              font-size:12px; margin-bottom:16px; }}
  .corr-table th, .opt-table th {{ background:#0c1015; color:#8b949e;
                                    padding:8px 12px; text-align:left;
                                    font-size:10px; letter-spacing:1px; }}
  .corr-table td, .opt-table td {{ padding:8px 12px; border-bottom:1px solid #1c2530; }}
  .chart-section {{ margin-bottom:32px; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:12px;
            font-size:10px; }}
  .badge-strong {{ background:rgba(0,212,170,0.15); color:#00d4aa; }}
  .badge-moderate {{ background:rgba(255,189,0,0.15); color:#ffbd00; }}
  .badge-weak {{ background:rgba(255,107,53,0.15); color:#ff6b35; }}
</style>
</head>
<body>
<h1>Vel Analysis Report</h1>
<div class="meta">
  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
  Dataset: {len(df)} rows × {len(df.columns)} columns |
  Report ID: {report_id}
</div>

<h2>Key Findings</h2>
<div class="findings">
  {''.join(f'<div class="finding">• {f}</div>' for f in findings) or '<div class="finding">No significant patterns detected.</div>'}
</div>

<h2>Dataset Overview</h2>
<div class="stat-grid">
  <div class="stat-card">
    <div class="label">Rows</div>
    <div class="value">{len(df)}</div>
  </div>
  <div class="stat-card">
    <div class="label">Columns</div>
    <div class="value">{len(df.columns)}</div>
  </div>
  <div class="stat-card">
    <div class="label">Numeric Columns</div>
    <div class="value">{sum(1 for p in profiles.values() if p['type'] == 'numeric')}</div>
  </div>
  <div class="stat-card">
    <div class="label">Missing Values</div>
    <div class="value">{df.isna().sum().sum()}</div>
  </div>
  <div class="stat-card">
    <div class="label">Target Column</div>
    <div class="value" style="font-size:14px">{target_col or '—'}</div>
  </div>
  <div class="stat-card">
    <div class="label">Goal</div>
    <div class="value" style="font-size:14px;color:#00d4aa">{direction.upper() if direction else '—'}</div>
  </div>
</div>

<h2>Top Correlations</h2>
<table class="corr-table">
  <thead><tr>
    <th>Variable 1</th><th>Variable 2</th>
    <th>Correlation</th><th>Strength</th><th>Direction</th>
  </tr></thead>
  <tbody>
  {''.join(f"""<tr>
    <td>{p['col1']}</td><td>{p['col2']}</td>
    <td>{p['correlation']}</td>
    <td><span class="badge badge-{'strong' if abs(p['correlation']) >= 0.7 else 'moderate' if abs(p['correlation']) >= 0.4 else 'weak'}">{p['strength']}</span></td>
    <td>{p['direction']}</td>
  </tr>""" for p in corr_pairs[:10]) if corr_pairs else '<tr><td colspan="5">Not enough numeric columns</td></tr>'}
  </tbody>
</table>

{'<h2>Optimization Plan</h2>' + opt_table if optimization else ''}

<h2>Charts</h2>
{charts_html if charts_html else '<p style="color:#5a7080">No charts generated.</p>'}

</body>
</html>"""

    report_path = os.path.join(REPORTS_DIR, f"{report_id}_report.html")
    with open(report_path, "w") as f:
        f.write(html)

    return report_path


# ── Main entry point ──────────────────────────────────────────────────────────

def analyze(text, target_hint=None, vel_port="8001"):
    """
    Main entry point.
    text: raw CSV/TSV string from user message
    target_hint: optional column name to optimize
    Returns (summary_text, report_url)
    """
    logging.info(f"Analysis started — {len(text)} chars input")

    # Parse
    df, delim, error = parse_data(text)
    if error:
        return f"Could not parse your data: {error}\n\nMake sure it's comma or tab separated with a header row.", None

    report_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Profile
    profiles = profile_columns(df)

    # Correlations
    corr_matrix, corr_pairs = detect_correlations(df)

    # Target detection
    target_col, direction, confidence = detect_target(df, profiles, target_hint)

    # Regression
    regression = run_regression(df, target_col) if target_col else None

    # Optimization
    optimization = optimize_target(df, target_col, direction, regression) \
                   if target_col and regression else None

    # Charts
    chart_paths = generate_charts(df, profiles, corr_matrix, target_col, report_id)

    # HTML report
    report_path = build_html_report(
        df, profiles, corr_pairs, regression,
        optimization, target_col, direction,
        chart_paths, report_id
    )

    # ── Build text summary for chat response ──────────────────────────────────
    lines = []
    lines.append(f"**Dataset:** {len(df)} rows × {len(df.columns)} columns")
    lines.append(f"**Columns:** {', '.join(df.columns.tolist())}")

    # Missing data
    missing = df.isna().sum().sum()
    if missing > 0:
        lines.append(f"**Missing values:** {missing} total")

    lines.append("")

    # Numeric summaries
    numeric_profiles = {c: p for c, p in profiles.items() if p["type"] == "numeric"}
    if numeric_profiles:
        lines.append("**Variable Summary:**")
        for col, p in numeric_profiles.items():
            lines.append(
                f"  {col}: mean={p['mean']}, min={p['min']}, "
                f"max={p['max']}, std={p['std']}"
                + (f" ⚠ {p['n_outliers']} outliers" if p.get("n_outliers", 0) > 0 else "")
            )

    lines.append("")

    # Top correlations
    if corr_pairs:
        lines.append("**Key Relationships:**")
        for pair in corr_pairs[:5]:
            lines.append(
                f"  {pair['col1']} ↔ {pair['col2']}: "
                f"r={pair['correlation']} ({pair['strength']} {pair['direction']})"
            )

    lines.append("")

    # Regression
    if regression:
        lines.append(f"**Feature Importance for {target_col} "
                     f"(R²={regression['r2_score']} — {regression['model_quality']}):**")
        max_imp = max(regression["feature_importance"].values()) if regression["feature_importance"] else 1
        for feat, imp in list(regression["feature_importance"].items())[:5]:
            bar = "█" * int((imp / max_imp) * 10)
            pct = round((imp / max_imp) * 100)
            lines.append(f"  {feat}: {bar} {pct}%")

    lines.append("")

    # Optimization
    if optimization and target_col:
        lines.append(f"**Optimization — {direction.upper()} {target_col}:**")
        for col, opt_val in list(optimization["optimal_values"].items())[:6]:
            cur_val = optimization["current_avg"].get(col)
            delta   = optimization["delta"].get(col, 0)
            arrow   = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            lines.append(
                f"  {col}: {cur_val} → {opt_val} {arrow}"
            )
        if not optimization.get("converged"):
            lines.append(f"  _{optimization.get('note', '')}_")
    elif target_col:
        lines.append(f"**Target column detected:** {target_col} ({direction})")
        lines.append("  Not enough data for full optimization.")

    lines.append("")

    # Report link
    report_url = f"http://100.104.58.38:{vel_port}/reports/{report_id}_report.html"
    lines.append(f"**Full interactive report:** {report_url}")
    lines.append(f"_(includes correlation heatmap, distribution plots, scatter charts)_")

    summary = "\n".join(lines)
    logging.info(f"Analysis complete — report: {report_path}")

    return summary, report_path


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_csv = """car,engine,displacement_cc,power_hp,torque_nm,weight_kg,lap_time_sec
Toyota Supra MK4,2JZ-GTE,2998,276,379,1520,142.3
Nissan Skyline R34,RB26DETT,2568,276,353,1540,144.1
Honda S2000,F20C,1997,240,208,1270,148.7
BMW M3 E46,S54B32,3246,338,365,1570,139.2
Ford Mustang GT350,Voodoo 5.2,5200,526,582,1732,136.8
Subaru STI,EJ257,2457,300,407,1470,141.5
Mitsubishi Evo IX,4G63T,1997,286,392,1410,140.2
Porsche 911 GT3,MA1.75,3996,500,460,1430,133.4
Chevrolet Corvette Z06,LS7,7011,505,637,1420,132.1
McLaren 570S,M838TE,3799,570,600,1313,129.8"""

    summary, report_path = analyze(test_csv)
    print(summary)
    print(f"\nReport saved: {report_path}")
