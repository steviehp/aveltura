"""
dashboard.py — AVELTURA / VEL Engine Analysis Dashboard (Vehicle-First)
Port 8003, open access.
Pulls from export_vehicle_engine.csv (primary) and Vel API (live stats).
"""

import os
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

import dash
from dash import dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go

load_dotenv()

BASE_DIR    = os.getenv("BASE_DIR",   "/home/_homeos/engine-analysis")
EXPORT_DIR  = os.path.join(BASE_DIR,  "exports")
VEL_API_KEY = os.getenv("VEL_API_KEY", "")
VEL_PORT    = os.getenv("VEL_PORT",   "8001")
VEL_BASE    = f"http://localhost:{VEL_PORT}"

# ── Colors ────────────────────────────────────────────────────────────────────
C = {
    "bg":       "#080c10",
    "surface":  "#0d1117",
    "surface2": "#161b22",
    "border":   "#21262d",
    "accent":   "#00d4aa",
    "accent2":  "#ff6b35",
    "accent3":  "#7c4dff",
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
REGION_COLORS = {"JDM": C["jdm"], "American": C["american"],
                 "European": C["european"], "Other": C["other"]}
ASPIRATION_COLORS = {"Turbocharged": C["turbo"], "Supercharged": C["sc"],
                     "Naturally Aspirated": C["na"]}

FONT         = "'JetBrains Mono', 'Fira Code', monospace"
FONT_DISPLAY = "'Rajdhani', 'Orbitron', sans-serif"

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=C["surface"],
    font=dict(color=C["text"], family=FONT, size=11),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=C["border"]),
)

ERA_ORDER = ["Classic (pre-1970)", "70s", "80s", "90s",
             "2000s", "2010s", "2020s+", "Unknown"]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_vehicle_data():
    for path in [
        os.path.join(EXPORT_DIR, "export_vehicle_engine.csv"),
        os.path.join(BASE_DIR,   "engine_applications.csv"),
    ]:
        if os.path.exists(path):
            return pd.read_csv(path)
    return pd.DataFrame()


def load_engine_data():
    for path in [
        os.path.join(EXPORT_DIR, "export_engine_specs.csv"),
        os.path.join(BASE_DIR,   "engine_normalized.csv"),
    ]:
        if os.path.exists(path):
            return pd.read_csv(path)
    return pd.DataFrame()


def get_vel_health():
    try:
        r = requests.get(f"{VEL_BASE}/health", timeout=3)
        return r.json()
    except Exception:
        return {"status": "unreachable", "index_loaded": False}


def get_vel_stats():
    try:
        r = requests.get(f"{VEL_BASE}/stats", timeout=3)
        return r.json()
    except Exception:
        return {"total_queries": "—", "last_query": "—"}


def get_recent_queries(n=6):
    log_path = os.path.join(BASE_DIR, "query.log")
    try:
        with open(log_path) as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        return lines[-n:]
    except Exception:
        return []


def label_col(df):
    for col in ["vehicle", "engine_variant", "engine"]:
        if col in df.columns:
            return col
    return df.columns[0] if len(df.columns) else "vehicle"


# ── UI helpers ────────────────────────────────────────────────────────────────

def stat_card(label, value, accent=False):
    return html.Div([
        html.Div(label, style={
            "fontSize": "9px", "letterSpacing": "2px",
            "textTransform": "uppercase", "color": C["muted"],
            "marginBottom": "4px", "fontFamily": FONT,
        }),
        html.Div(str(value), style={
            "fontSize": "26px", "fontWeight": "700",
            "fontFamily": FONT_DISPLAY,
            "color": C["accent"] if accent else C["text"],
        }),
    ], style={
        "background": C["surface2"],
        "border": f"1px solid {C['accent'] if accent else C['border']}",
        "borderRadius": "8px", "padding": "16px 20px", "minWidth": "130px",
        "boxShadow": f"0 0 20px {C['accent']}22" if accent else "none",
    })


def section_header(title):
    return html.Div(title, style={
        "fontFamily": FONT_DISPLAY, "fontSize": "11px", "letterSpacing": "3px",
        "textTransform": "uppercase", "color": C["accent"],
        "borderBottom": f"1px solid {C['border']}",
        "paddingBottom": "6px", "marginBottom": "14px", "marginTop": "6px",
    })


def card(children, flex=1):
    return html.Div(children, style={
        "flex": str(flex), "background": C["surface2"],
        "border": f"1px solid {C['border']}",
        "borderRadius": "8px", "padding": "20px",
    })


def row(*children, gap="16px", mb="16px"):
    return html.Div(list(children), style={
        "display": "flex", "gap": gap, "marginBottom": mb,
    })


# ── Dropdown options ──────────────────────────────────────────────────────────

REGION_OPTIONS = [
    {"label": "All regions",  "value": "All"},
    {"label": "JDM",          "value": "JDM"},
    {"label": "American",     "value": "American"},
    {"label": "European",     "value": "European"},
    {"label": "Other",        "value": "Other"},
]
COLOR_OPTIONS = [
    {"label": "Region",      "value": "region"},
    {"label": "Aspiration",  "value": "aspiration"},
    {"label": "Confidence",  "value": "confidence"},
    {"label": "Manufacturer","value": "manufacturer"},
]
BAR_FILTER_OPTIONS = [
    {"label": "All",          "value": "All"},
    {"label": "JDM",          "value": "JDM"},
    {"label": "American",     "value": "American"},
    {"label": "European",     "value": "European"},
    {"label": "Turbocharged", "value": "Turbocharged"},
    {"label": "Supercharged", "value": "Supercharged"},
    {"label": "Verified only","value": "verified"},
]

DD_STYLE = {"background": C["surface2"], "color": C["text"], "border": f"1px solid {C['border']}"}


# ── App ───────────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="AVELTURA — Vel Dashboard",
    update_title=None,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

app.layout = html.Div([
    dcc.Interval(id="live-interval", interval=30_000, n_intervals=0),

    html.Link(rel="preconnect", href="https://fonts.googleapis.com"),
    html.Link(rel="stylesheet", href=(
        "https://fonts.googleapis.com/css2?"
        "family=Rajdhani:wght@400;600;700"
        "&family=JetBrains+Mono:wght@400;500&display=swap"
    )),

    # ── Header ────────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Span("AVELTURA", style={
                "fontFamily": FONT_DISPLAY, "fontSize": "24px",
                "fontWeight": "700", "color": C["accent"], "letterSpacing": "4px",
            }),
            html.Span(" / VEL", style={
                "fontFamily": FONT_DISPLAY, "fontSize": "24px",
                "color": C["muted"], "letterSpacing": "4px",
            }),
            html.Div("ENGINE ANALYSIS PLATFORM", style={
                "fontFamily": FONT, "fontSize": "9px",
                "letterSpacing": "4px", "color": C["muted"], "marginTop": "2px",
            }),
        ]),
        html.Div(id="live-status",
                 style={"display": "flex", "gap": "12px", "alignItems": "center"}),
    ], style={
        "display": "flex", "justifyContent": "space-between",
        "alignItems": "center", "padding": "18px 32px",
        "borderBottom": f"1px solid {C['border']}",
        "background": C["surface"],
    }),

    # ── Content ───────────────────────────────────────────────────────────────
    html.Div([

        # Stat cards
        html.Div(id="stat-cards",
                 style={"display": "flex", "gap": "14px",
                        "flexWrap": "wrap", "marginBottom": "24px"}),

        # Row 1: Scatter + Pies
        row(
            card([
                section_header("Displacement vs Power"),
                html.Div([
                    html.Div([
                        html.Label("Color by", style={"color": C["muted"], "fontSize": "10px", "fontFamily": FONT}),
                        dcc.Dropdown(id="scatter-color", options=COLOR_OPTIONS,
                                     value="region", clearable=False, style=DD_STYLE),
                    ], style={"width": "150px"}),
                    html.Div([
                        html.Label("Region filter", style={"color": C["muted"], "fontSize": "10px", "fontFamily": FONT}),
                        dcc.Dropdown(id="scatter-region", options=REGION_OPTIONS,
                                     value="All", clearable=False, style=DD_STYLE),
                    ], style={"width": "150px"}),
                ], style={"display": "flex", "gap": "14px", "marginBottom": "10px"}),
                dcc.Graph(id="scatter-chart", style={"height": "370px"}),
            ], flex=2),

            card([
                section_header("Region Breakdown"),
                dcc.Graph(id="region-pie", style={"height": "190px"}),
                section_header("Aspiration Split"),
                dcc.Graph(id="aspiration-pie", style={"height": "190px"}),
            ], flex=1),
        ),

        # Row 2: Top power bar + HP/litre
        row(
            card([
                section_header("Top Vehicles by Power"),
                html.Div([
                    html.Label("Filter", style={"color": C["muted"], "fontSize": "10px", "fontFamily": FONT}),
                    dcc.Dropdown(id="bar-filter", options=BAR_FILTER_OPTIONS,
                                 value="All", clearable=False,
                                 style={**DD_STYLE, "width": "180px"}),
                ], style={"marginBottom": "10px"}),
                dcc.Graph(id="bar-chart", style={"height": "340px"}),
            ], flex=1),

            card([
                section_header("HP per Litre — Top 15"),
                dcc.Graph(id="hpl-chart", style={"height": "380px"}),
            ], flex=1),
        ),

        # Row 3: Era chart + Vel query
        row(
            card([
                section_header("Vehicles by Era"),
                dcc.Graph(id="era-chart", style={"height": "270px"}),
            ], flex=1),

            card([
                section_header("Query Vel"),
                dcc.Textarea(
                    id="vel-query-input",
                    placeholder="Ask Vel anything...\ne.g. What engine does the BMW M3 E46 use?",
                    style={
                        "width": "100%", "height": "80px", "resize": "none",
                        "background": C["surface"], "color": C["text"],
                        "border": f"1px solid {C['border']}", "borderRadius": "6px",
                        "padding": "10px", "fontFamily": FONT, "fontSize": "12px",
                        "outline": "none", "boxSizing": "border-box",
                    },
                ),
                html.Button("QUERY VEL →", id="vel-query-btn", n_clicks=0, style={
                    "marginTop": "10px", "padding": "10px 20px",
                    "background": "transparent", "color": C["accent"],
                    "border": f"1px solid {C['accent']}", "borderRadius": "6px",
                    "fontFamily": FONT_DISPLAY, "fontSize": "12px",
                    "letterSpacing": "2px", "cursor": "pointer", "width": "100%",
                }),
                html.Div(id="vel-query-output", style={
                    "marginTop": "12px", "padding": "12px",
                    "background": C["surface"],
                    "border": f"1px solid {C['border']}",
                    "borderRadius": "6px", "fontFamily": FONT, "fontSize": "11px",
                    "color": C["text"], "minHeight": "70px",
                    "lineHeight": "1.6", "whiteSpace": "pre-wrap",
                }),
                section_header("Recent Queries"),
                html.Div(id="recent-queries", style={
                    "fontFamily": FONT, "fontSize": "10px",
                    "color": C["muted"], "lineHeight": "1.8",
                }),
            ], flex=1),
        ),

    ], style={"padding": "24px 32px", "maxWidth": "1600px", "margin": "0 auto"}),

], style={"background": C["bg"], "minHeight": "100vh",
          "fontFamily": FONT, "color": C["text"]})


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("live-status",   "children"),
    Output("stat-cards",    "children"),
    Output("recent-queries","children"),
    Input("live-interval",  "n_intervals"),
)
def update_live(_):
    health = get_vel_health()
    stats  = get_vel_stats()
    vdf    = load_vehicle_data()
    edf    = load_engine_data()

    is_up   = health.get("status") == "ok"
    dot_col = C["accent"] if is_up else C["accent2"]
    status_el = html.Div([
        html.Div(style={"width": "8px", "height": "8px", "borderRadius": "50%",
                        "background": dot_col, "boxShadow": f"0 0 8px {dot_col}"}),
        html.Span("VEL ONLINE" if is_up else "VEL OFFLINE", style={
            "fontFamily": FONT, "fontSize": "9px",
            "letterSpacing": "2px", "color": dot_col,
        }),
    ], style={"display": "flex", "gap": "8px", "alignItems": "center"})

    timestamp = html.Div(datetime.now().strftime("%H:%M:%S"), style={
        "fontFamily": FONT, "fontSize": "9px", "color": C["muted"],
    })

    n_vehicles = vdf["vehicle"].nunique() if not vdf.empty and "vehicle" in vdf.columns else "—"
    n_engines  = edf["engine"].nunique()  if not edf.empty and "engine"  in edf.columns else "—"
    n_apps     = len(vdf) if not vdf.empty else "—"
    n_queries  = stats.get("total_queries", "—")

    cards = [
        stat_card("Vehicles",     n_vehicles, accent=True),
        stat_card("Engines",      n_engines),
        stat_card("Applications", n_apps),
        stat_card("Queries",      n_queries),
        stat_card("Index", "LOADED" if health.get("index_loaded") else "—"),
    ]

    recent = get_recent_queries(6)
    q_els  = [html.Div(f"› {q[-100:]}", style={"marginBottom": "3px"})
              for q in reversed(recent)] if recent else \
             [html.Div("No queries yet", style={"color": C["muted"]})]

    return [status_el, timestamp], cards, q_els


@app.callback(
    Output("scatter-chart", "figure"),
    Input("scatter-color",  "value"),
    Input("scatter-region", "value"),
    Input("live-interval",  "n_intervals"),
)
def update_scatter(color_by, region_filter, _):
    df = load_vehicle_data()
    if df.empty:
        return go.Figure()

    disp_col = "displacement_cc" if "displacement_cc" in df.columns else \
               "displacement"    if "displacement"    in df.columns else None
    if not disp_col or "power_hp" not in df.columns:
        return go.Figure()

    df = df.rename(columns={disp_col: "_disp"})
    df = df.dropna(subset=["_disp", "power_hp"])

    if region_filter != "All" and "region" in df.columns:
        df = df[df["region"] == region_filter]

    lbl       = label_col(df)
    color_map = REGION_COLORS if color_by == "region" else \
                ASPIRATION_COLORS if color_by == "aspiration" else None

    fig = px.scatter(
        df, x="_disp", y="power_hp",
        color=color_by if color_by in df.columns else None,
        color_discrete_map=color_map,
        hover_name=lbl,
        hover_data={c: True for c in ["generation", "trim", "confidence", "manufacturer"]
                    if c in df.columns},
        trendline="ols",
        trendline_color_override=C["accent"],
        labels={"_disp": "Displacement (cc)", "power_hp": "Power (hp)"},
        title="Vehicle Displacement vs Power Output",
    )
    fig.update_traces(marker=dict(size=7, opacity=0.85))
    fig.update_layout(**PLOT_LAYOUT)
    return fig


@app.callback(
    Output("region-pie",    "figure"),
    Output("aspiration-pie","figure"),
    Input("live-interval",  "n_intervals"),
)
def update_pies(_):
    df = load_vehicle_data()
    if df.empty:
        return go.Figure(), go.Figure()

    def _pie(col, color_map):
        if col not in df.columns:
            return go.Figure()
        counts = df[col].value_counts()
        fig = go.Figure(go.Pie(
            labels=counts.index, values=counts.values,
            marker_colors=[color_map.get(r, C["muted"]) for r in counts.index],
            hole=0.5, textfont=dict(family=FONT, size=9),
        ))
        fig.update_layout(**PLOT_LAYOUT, showlegend=True,
                          margin=dict(l=5, r=5, t=5, b=5))
        return fig

    return _pie("region", REGION_COLORS), _pie("aspiration", ASPIRATION_COLORS)


@app.callback(
    Output("bar-chart",    "figure"),
    Input("bar-filter",    "value"),
    Input("live-interval", "n_intervals"),
)
def update_bar(filter_val, _):
    df = load_vehicle_data()
    if df.empty or "power_hp" not in df.columns:
        return go.Figure()

    df = df.dropna(subset=["power_hp"])
    if filter_val in ("JDM", "American", "European", "Other") and "region" in df.columns:
        df = df[df["region"] == filter_val]
    elif filter_val in ("Turbocharged", "Supercharged") and "aspiration" in df.columns:
        df = df[df["aspiration"] == filter_val]
    elif filter_val == "verified" and "confidence" in df.columns:
        df = df[df["confidence"] == "verified_manual"]

    lbl = label_col(df)
    if "generation" in df.columns and "trim" in df.columns:
        df["_display"] = (df[lbl].astype(str) + " " +
                          df["generation"].fillna("").astype(str) + " " +
                          df["trim"].fillna("").astype(str)).str.strip()
    else:
        df["_display"] = df[lbl]

    top = df.nlargest(15, "power_hp")

    fig = px.bar(
        top, x="power_hp", y="_display", orientation="h",
        color="region" if "region" in top.columns else None,
        color_discrete_map=REGION_COLORS,
        labels={"power_hp": "Power (hp)", "_display": ""},
        title="Top 15 Vehicles by Power",
    )
    fig.update_layout(**PLOT_LAYOUT, yaxis=dict(autorange="reversed"), showlegend=False)
    return fig


@app.callback(
    Output("hpl-chart",    "figure"),
    Input("live-interval", "n_intervals"),
)
def update_hpl(_):
    df = load_vehicle_data()
    if df.empty:
        return go.Figure()

    if "hp_per_litre" not in df.columns:
        disp_col = "displacement_cc" if "displacement_cc" in df.columns else \
                   "displacement"    if "displacement"    in df.columns else None
        if disp_col and "power_hp" in df.columns:
            df["hp_per_litre"] = df.apply(
                lambda r: round(float(r["power_hp"]) / (float(r[disp_col]) / 1000), 1)
                if pd.notna(r.get("power_hp")) and pd.notna(r.get(disp_col))
                and float(r.get(disp_col, 0)) > 0 else None,
                axis=1
            )
        else:
            return go.Figure()

    lbl = label_col(df)
    if "generation" in df.columns and "trim" in df.columns:
        df["_display"] = (df[lbl].astype(str) + " " +
                          df["generation"].fillna("").astype(str) + " " +
                          df["trim"].fillna("").astype(str)).str.strip()
    else:
        df["_display"] = df[lbl]

    top = df.dropna(subset=["hp_per_litre"]).nlargest(15, "hp_per_litre")

    fig = px.bar(
        top, x="hp_per_litre", y="_display", orientation="h",
        color="aspiration" if "aspiration" in top.columns else None,
        color_discrete_map=ASPIRATION_COLORS,
        labels={"hp_per_litre": "HP / Litre", "_display": ""},
        title="Specific Power Output (HP/L)",
    )
    fig.update_layout(**PLOT_LAYOUT, yaxis=dict(autorange="reversed"))
    return fig


@app.callback(
    Output("era-chart",    "figure"),
    Input("live-interval", "n_intervals"),
)
def update_era(_):
    df = load_vehicle_data()
    if df.empty:
        return go.Figure()

    if "era" not in df.columns and "year_start" in df.columns:
        def classify_era(y):
            if pd.isna(y): return "Unknown"
            y = int(y)
            if y < 1970: return "Classic (pre-1970)"
            if y < 1980: return "70s"
            if y < 1990: return "80s"
            if y < 2000: return "90s"
            if y < 2010: return "2000s"
            if y < 2020: return "2010s"
            return "2020s+"
        df["era"] = df["year_start"].apply(classify_era)

    if "era" not in df.columns:
        return go.Figure()

    lbl = label_col(df)
    if "region" in df.columns:
        grouped = df.groupby(["era", "region"]).size().reset_index(name="count")
    else:
        grouped = df.groupby("era").size().reset_index(name="count")
        grouped["region"] = "All"

    fig = px.bar(
        grouped, x="era", y="count",
        color="region" if "region" in grouped.columns else None,
        color_discrete_map=REGION_COLORS,
        category_orders={"era": ERA_ORDER},
        labels={"era": "Era", "count": "Vehicles"},
        title="Vehicles by Era",
    )
    fig.update_layout(**PLOT_LAYOUT)
    return fig


@app.callback(
    Output("vel-query-output", "children"),
    Input("vel-query-btn",     "n_clicks"),
    State("vel-query-input",   "value"),
    prevent_initial_call=True,
)
def query_vel(n_clicks, query_text):
    if not query_text or not query_text.strip():
        return "Enter a query above."
    if not VEL_API_KEY:
        return "VEL_API_KEY not configured."
    try:
        r = requests.post(
            f"{VEL_BASE}/query",
            json={"message": query_text.strip()},
            headers={"Authorization": f"Bearer {VEL_API_KEY}",
                     "Content-Type": "application/json"},
            timeout=60,
        )
        data    = r.json()
        response = data.get("response", "No response")
        elapsed  = data.get("response_time", "—")
        return f"{response}\n\n[{elapsed}s]"
    except Exception as e:
        return f"Error: {e}"


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Aveltura Dashboard on http://0.0.0.0:8003")
    app.run(host="0.0.0.0", port=8003, debug=False)
