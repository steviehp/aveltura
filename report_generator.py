"""
report_generator.py — Phase 13: PDF Report Generation

Generates professional PDF engineering reports from:
  1. Universal analyzer results (any dataset)
  2. Optimization engine results (mod plans)
  3. Engine/vehicle spec summaries

Uses ReportLab for PDF generation — no system dependencies.
Output saved to reports/ directory, served via /reports endpoint.
"""

import os
import io
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
BASE_DIR    = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "reports.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ── Colors ────────────────────────────────────────────────────────────────────

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, inch
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics import renderPDF
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    logging.warning("ReportLab not installed — PDF generation unavailable")


# ── Brand colors ──────────────────────────────────────────────────────────────

if REPORTLAB_OK:
    ACCENT   = colors.HexColor("#00d4aa")
    ACCENT2  = colors.HexColor("#ff6b35")
    BG_DARK  = colors.HexColor("#0d1117")
    BG_MID   = colors.HexColor("#161b22")
    BG_LIGHT = colors.HexColor("#21262d")
    TEXT     = colors.HexColor("#e6edf3")
    MUTED    = colors.HexColor("#8b949e")
    WHITE    = colors.white
    BLACK    = colors.black


# ── Style builder ─────────────────────────────────────────────────────────────

def build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="VelTitle",
        fontSize=28,
        fontName="Helvetica-Bold",
        textColor=ACCENT,
        spaceAfter=4,
        leading=34,
    ))
    styles.add(ParagraphStyle(
        name="VelSubtitle",
        fontSize=11,
        fontName="Helvetica",
        textColor=MUTED,
        spaceAfter=20,
        leading=16,
    ))
    styles.add(ParagraphStyle(
        name="VelH2",
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=ACCENT,
        spaceBefore=16,
        spaceAfter=6,
        leading=18,
    ))
    styles.add(ParagraphStyle(
        name="VelH3",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=TEXT,
        spaceBefore=10,
        spaceAfter=4,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name="VelBody",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#c0ccd8"),
        spaceAfter=4,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name="VelMono",
        fontSize=8,
        fontName="Courier",
        textColor=TEXT,
        spaceAfter=2,
        leading=12,
        backColor=BG_MID,
        leftIndent=8,
        rightIndent=8,
        borderPad=4,
    ))
    styles.add(ParagraphStyle(
        name="VelWarning",
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=ACCENT2,
        spaceAfter=4,
        leading=14,
        leftIndent=12,
    ))
    styles.add(ParagraphStyle(
        name="VelCaption",
        fontSize=8,
        fontName="Helvetica",
        textColor=MUTED,
        spaceAfter=6,
        leading=12,
        alignment=TA_CENTER,
    ))

    return styles


# ── Table styles ──────────────────────────────────────────────────────────────

def header_table_style():
    return TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  BG_MID),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  ACCENT),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("BOTTOMPADDING",(0, 0), (-1, 0),  6),
        ("TOPPADDING",   (0, 0), (-1, 0),  6),
        ("BACKGROUND",   (0, 1), (-1, -1), BG_DARK),
        ("TEXTCOLOR",    (0, 1), (-1, -1), TEXT),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1),(-1, -1), [BG_DARK, BG_MID]),
        ("GRID",         (0, 0), (-1, -1), 0.5, BG_LIGHT),
        ("TOPPADDING",   (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 1), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ])


def stat_card_style():
    return TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), BG_MID),
        ("TEXTCOLOR",    (0, 0), (-1, -1), TEXT),
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 14),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 12),
        ("BOX",          (0, 0), (-1, -1), 1, BG_LIGHT),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, BG_LIGHT),
    ])


# ── Page template ─────────────────────────────────────────────────────────────

def on_page(canvas, doc):
    """Draw header and footer on every page."""
    canvas.saveState()
    w, h = A4

    # Header bar
    canvas.setFillColor(BG_DARK)
    canvas.rect(0, h - 28*mm, w, 28*mm, fill=1, stroke=0)

    # Logo text
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(20*mm, h - 16*mm, "AVELTURA")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(20*mm + 82, h - 16*mm, "/ VEL")

    # Report label
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(w - 20*mm, h - 12*mm, "ENGINE ANALYSIS REPORT")
    canvas.drawRightString(w - 20*mm, h - 18*mm,
                           datetime.now().strftime("%Y-%m-%d %H:%M"))

    # Accent line under header
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1.5)
    canvas.line(0, h - 28*mm, w, h - 28*mm)

    # Footer
    canvas.setFillColor(BG_MID)
    canvas.rect(0, 0, w, 14*mm, fill=1, stroke=0)
    canvas.setStrokeColor(BG_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(0, 14*mm, w, 14*mm)

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(20*mm, 5*mm, "Generated by Vel — Aveltura Engine Analysis Platform")
    canvas.drawRightString(w - 20*mm, 5*mm, f"Page {doc.page}")

    canvas.restoreState()


# ── Section builders ──────────────────────────────────────────────────────────

def build_stat_cards(stats_dict, styles):
    """Build a row of stat cards from a dict of label: value pairs."""
    items = list(stats_dict.items())
    # Pad to multiple of 4
    while len(items) % 4 != 0:
        items.append(("", ""))

    rows = []
    for i in range(0, len(items), 4):
        chunk = items[i:i+4]
        label_row = [
            Paragraph(f'<font size="7" color="#8b949e">{k.upper()}</font>', styles["VelBody"])
            for k, v in chunk
        ]
        value_row = [
            Paragraph(f'<font size="16" color="#e6edf3"><b>{v}</b></font>', styles["VelBody"])
            for k, v in chunk
        ]
        t = Table(
            [label_row, value_row],
            colWidths=[42*mm] * 4,
        )
        t.setStyle(stat_card_style())
        rows.append(t)
        rows.append(Spacer(1, 6))

    return rows


def build_correlation_table(corr_pairs, styles, top_n=10):
    """Build correlation pairs table."""
    data = [["Variable 1", "Variable 2", "r", "Strength", "Direction"]]
    for pair in corr_pairs[:top_n]:
        r     = pair["correlation"]
        color = "#00d4aa" if abs(r) >= 0.7 else "#ffbd00" if abs(r) >= 0.4 else "#ff6b35"
        data.append([
            pair["col1"],
            pair["col2"],
            f'<font color="{color}"><b>{r}</b></font>',
            pair["strength"],
            pair["direction"],
        ])

    # Convert cells with markup to Paragraphs
    table_data = []
    for row in data:
        table_data.append([
            Paragraph(str(cell), styles["VelBody"]) for cell in row
        ])

    t = Table(table_data, colWidths=[40*mm, 40*mm, 20*mm, 35*mm, 30*mm])
    t.setStyle(header_table_style())
    return t


def build_optimization_table(optimization, styles):
    """Build optimization results table."""
    if not optimization:
        return Paragraph("Optimization not available.", styles["VelBody"])

    data = [["Variable", "Current Average", "Optimal Value", "Change"]]
    for col, opt_val in optimization["optimal_values"].items():
        cur   = optimization["current_avg"].get(col, "—")
        delta = optimization["delta"].get(col, 0)
        if delta > 0:
            arrow = "↑"
            color = "#00d4aa"
        elif delta < 0:
            arrow = "↓"
            color = "#ff6b35"
        else:
            arrow = "→"
            color = "#8b949e"

        data.append([
            col,
            str(cur),
            f'<font color="{color}"><b>{opt_val} {arrow}</b></font>',
            f'<font color="{color}">{("+" if delta > 0 else "")}{delta}</font>',
        ])

    table_data = []
    for row in data:
        table_data.append([
            Paragraph(str(cell), styles["VelBody"]) for cell in row
        ])

    t = Table(table_data, colWidths=[55*mm, 40*mm, 40*mm, 30*mm])
    t.setStyle(header_table_style())
    return t


def build_mod_plan_table(mod_list, styles):
    """Build mod plan table from optimization engine output."""
    data = [["#", "Modification", "Category", "Est. Cost", "Confidence"]]
    for mod in sorted(mod_list, key=lambda m: m.get("rank", 99)):
        if mod.get("rank", 99) == 99:
            continue
        data.append([
            str(mod.get("rank", "")),
            mod.get("name", ""),
            mod.get("category", "").replace("_", " ").title(),
            f"${mod.get('cost_low', 0):,} – ${mod.get('cost_high', 0):,}",
            f"{mod.get('confidence_pct', '')}%",
        ])

    table_data = []
    for row in data:
        table_data.append([
            Paragraph(str(cell), styles["VelBody"]) for cell in row
        ])

    t = Table(table_data, colWidths=[10*mm, 65*mm, 35*mm, 35*mm, 20*mm])
    t.setStyle(header_table_style())
    return t


# ── Main report builders ──────────────────────────────────────────────────────

def generate_analysis_report(analysis_result, dataset_name="Dataset"):
    """
    Generate PDF report from universal_analyzer results.
    analysis_result: dict with keys from analyze() function
    Returns: path to generated PDF
    """
    if not REPORTLAB_OK:
        return None, "ReportLab not installed. Run: pip install reportlab --break-system-packages"

    report_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path   = os.path.join(REPORTS_DIR, f"{report_id}_analysis.pdf")
    styles     = build_styles()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=32*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("Dataset Analysis Report", styles["VelTitle"]))
    story.append(Paragraph(
        f"{dataset_name} — Generated {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        styles["VelSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=12))

    # ── Overview stat cards ───────────────────────────────────────────────────
    story.append(Paragraph("Dataset Overview", styles["VelH2"]))

    df        = analysis_result.get("df")
    profiles  = analysis_result.get("profiles", {})
    n_rows    = len(df) if df is not None else "—"
    n_cols    = len(df.columns) if df is not None else "—"
    n_numeric = sum(1 for p in profiles.values() if p.get("type") == "numeric")
    n_missing = df.isna().sum().sum() if df is not None else "—"
    target    = analysis_result.get("target_col", "—")
    direction = analysis_result.get("direction", "—")

    stat_cards = build_stat_cards({
        "Rows":         n_rows,
        "Columns":      n_cols,
        "Numeric":      n_numeric,
        "Missing":      n_missing,
        "Target":       target or "—",
        "Goal":         direction.upper() if direction else "—",
        "Model R²":     analysis_result.get("r2_score", "—"),
        "Report ID":    report_id,
    }, styles)
    story.extend(stat_cards)
    story.append(Spacer(1, 8*mm))

    # ── Variable summary ──────────────────────────────────────────────────────
    story.append(Paragraph("Variable Summary", styles["VelH2"]))

    numeric_profiles = {c: p for c, p in profiles.items()
                        if p.get("type") == "numeric"}
    if numeric_profiles:
        data = [["Column", "Mean", "Std Dev", "Min", "Max", "Outliers"]]
        for col, p in numeric_profiles.items():
            data.append([
                col,
                str(p.get("mean", "—")),
                str(p.get("std", "—")),
                str(p.get("min", "—")),
                str(p.get("max", "—")),
                str(p.get("n_outliers", 0)),
            ])
        table_data = [[Paragraph(str(c), styles["VelBody"]) for c in row]
                      for row in data]
        t = Table(table_data,
                  colWidths=[45*mm, 25*mm, 25*mm, 25*mm, 25*mm, 20*mm])
        t.setStyle(header_table_style())
        story.append(t)
    story.append(Spacer(1, 8*mm))

    # ── Correlations ──────────────────────────────────────────────────────────
    corr_pairs = analysis_result.get("corr_pairs", [])
    if corr_pairs:
        story.append(Paragraph("Key Relationships", styles["VelH2"]))
        story.append(Paragraph(
            "Pearson correlation coefficients between all numeric variable pairs. "
            "Values closer to ±1 indicate stronger relationships.",
            styles["VelBody"]
        ))
        story.append(Spacer(1, 4))
        story.append(build_correlation_table(corr_pairs, styles))
        story.append(Spacer(1, 8*mm))

    # ── Feature importance ────────────────────────────────────────────────────
    regression = analysis_result.get("regression")
    if regression and target:
        story.append(Paragraph(
            f"Feature Importance — Predicting {target}", styles["VelH2"]
        ))
        story.append(Paragraph(
            f"Linear regression model. R² = {regression.get('r2_score', '—')} "
            f"({regression.get('model_quality', '')}). "
            f"Higher importance = stronger predictor of {target}.",
            styles["VelBody"]
        ))
        story.append(Spacer(1, 4))

        imp = regression.get("feature_importance", {})
        max_imp = max(imp.values()) if imp else 1
        data = [["Feature", "Importance", "Relative"]]
        for feat, val in list(imp.items())[:8]:
            pct  = int((val / max_imp) * 100)
            bar  = "█" * (pct // 10) + "░" * (10 - pct // 10)
            data.append([feat, str(val), f"{bar} {pct}%"])

        table_data = [[Paragraph(str(c), styles["VelBody"]) for c in row]
                      for row in data]
        t = Table(table_data, colWidths=[55*mm, 30*mm, 80*mm])
        t.setStyle(header_table_style())
        story.append(t)
        story.append(Spacer(1, 8*mm))

    # ── Optimization ──────────────────────────────────────────────────────────
    optimization = analysis_result.get("optimization")
    if optimization and target:
        story.append(Paragraph(
            f"Optimization Results — {direction.upper() if direction else ''} {target}",
            styles["VelH2"]
        ))
        story.append(Paragraph(
            "Recommended variable values to achieve the optimization goal. "
            "Based on correlation analysis and constrained optimization solver.",
            styles["VelBody"]
        ))
        story.append(Spacer(1, 4))
        story.append(build_optimization_table(optimization, styles))

        if not optimization.get("converged"):
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"⚠  {optimization.get('note', 'Estimated using percentile method')}",
                styles["VelWarning"]
            ))
        story.append(Spacer(1, 8*mm))

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BG_LIGHT))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "This report was generated automatically by the Vel Engine Analysis Platform. "
        "Statistical recommendations are based on the provided dataset only. "
        "Always validate findings with domain expertise before making decisions.",
        styles["VelBody"]
    ))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    logging.info(f"Analysis PDF generated: {pdf_path}")
    return pdf_path, None


def generate_optimization_report(plan, car_name=""):
    """
    Generate PDF report from optimization_engine results.
    plan: dict returned by solve_performance_build / solve_efficiency_build
    Returns: path to generated PDF
    """
    if not REPORTLAB_OK:
        return None, "ReportLab not installed."

    report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path  = os.path.join(REPORTS_DIR, f"{report_id}_modplan.pdf")
    styles    = build_styles()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=32*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("Modification Plan Report", styles["VelTitle"]))
    story.append(Paragraph(
        f"{plan.get('car', car_name)} ({plan.get('engine', '')}) — "
        f"Generated {datetime.now().strftime('%B %d, %Y')}",
        styles["VelSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=12))

    # ── Summary cards ─────────────────────────────────────────────────────────
    gap = plan.get("gap", {})
    story.append(Paragraph("Build Summary", styles["VelH2"]))
    stat_cards = build_stat_cards({
        "Goal":          plan.get("goal", "—"),
        "Stock Power":   f"{gap.get('stock_hp', '—')}hp",
        "Target (crank)":f"{gap.get('target_crank', '—')}hp",
        "Power Gap":     f"+{gap.get('hp_gap', '—')}hp",
        "Drivetrain":    plan.get("drivetrain", "—").upper(),
        "Est. Min Cost": f"${plan.get('total_cost_low', 0):,}",
        "Est. Max Cost": f"${plan.get('total_cost_high', 0):,}",
        "Confidence":    f"{plan.get('confidence', '—')}%",
    }, styles)
    story.extend(stat_cards)
    story.append(Spacer(1, 8*mm))

    # ── Warnings ──────────────────────────────────────────────────────────────
    if plan.get("warnings"):
        story.append(Paragraph("⚠  Warnings", styles["VelH2"]))
        for w in plan["warnings"]:
            story.append(Paragraph(f"• {w}", styles["VelWarning"]))
        story.append(Spacer(1, 6*mm))

    # ── Mod plan table ────────────────────────────────────────────────────────
    mods = plan.get("mods", [])
    if mods:
        story.append(Paragraph("Modification Plan", styles["VelH2"]))
        story.append(build_mod_plan_table(mods, styles))
        story.append(Spacer(1, 6*mm))

    # ── Mod details ───────────────────────────────────────────────────────────
    story.append(Paragraph("Modification Details", styles["VelH2"]))
    for mod in sorted(mods, key=lambda m: m.get("rank", 99)):
        if mod.get("rank", 99) == 99:
            continue
        block = []
        block.append(Paragraph(
            f"{mod.get('rank')}. {mod.get('name', '')}",
            styles["VelH3"]
        ))
        block.append(Paragraph(
            f"<b>Install location:</b> {mod.get('install_location', '—')}",
            styles["VelBody"]
        ))
        block.append(Paragraph(
            f"<b>Expected gain:</b> {mod.get('hp_gain') or mod.get('benefit', '—')}",
            styles["VelBody"]
        ))
        block.append(Paragraph(
            f"<b>Estimated cost:</b> ${mod.get('cost_low', 0):,} – "
            f"${mod.get('cost_high', 0):,}",
            styles["VelBody"]
        ))
        issues = mod.get("known_issues", [])
        if issues:
            block.append(Paragraph("<b>Known issues:</b>", styles["VelBody"]))
            for issue in issues[:3]:
                block.append(Paragraph(f"  • {issue}", styles["VelBody"]))
        block.append(Spacer(1, 4))
        story.append(KeepTogether(block))

    # ── Supporting mods ───────────────────────────────────────────────────────
    supporting = plan.get("supporting_mods", [])
    if supporting:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("Supporting Hardware Required", styles["VelH2"]))
        for s in supporting:
            story.append(Paragraph(f"• {s}", styles["VelBody"]))
        story.append(Spacer(1, 6*mm))

    # ── Phased timeline ───────────────────────────────────────────────────────
    phases = plan.get("phases", [])
    if phases:
        story.append(PageBreak())
        story.append(Paragraph("Phased Build Timeline", styles["VelH2"]))
        story.append(Paragraph(
            "Recommended build order based on dependency and budget at ~$1,500/month.",
            styles["VelBody"]
        ))
        story.append(Spacer(1, 4))

        data = [["Month", "Modifications", "Est. Cost"]]
        for phase in phases:
            data.append([
                f"Month {phase['month']}",
                "\n".join(f"• {m}" for m in phase["mods"]),
                f"${phase['cost']:,}",
            ])

        table_data = [[Paragraph(str(c), styles["VelBody"]) for c in row]
                      for row in data]
        t = Table(table_data, colWidths=[25*mm, 115*mm, 25*mm])
        t.setStyle(header_table_style())
        story.append(t)

    # ── Cost breakdown ────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Cost Summary", styles["VelH2"]))
    data = [["Item", "Low Estimate", "High Estimate"]]
    for mod in sorted(mods, key=lambda m: m.get("rank", 99)):
        data.append([
            mod.get("name", ""),
            f"${mod.get('cost_low', 0):,}",
            f"${mod.get('cost_high', 0):,}",
        ])
    data.append([
        "TOTAL",
        f"${plan.get('total_cost_low', 0):,}",
        f"${plan.get('total_cost_high', 0):,}",
    ])

    table_data = []
    for i, row in enumerate(data):
        if i == len(data) - 1:
            # Total row — bold
            table_data.append([
                Paragraph(f"<b>{c}</b>", styles["VelBody"]) for c in row
            ])
        else:
            table_data.append([
                Paragraph(str(c), styles["VelBody"]) for c in row
            ])

    t = Table(table_data, colWidths=[105*mm, 30*mm, 30*mm])
    ts = header_table_style()
    ts.add("BACKGROUND", (0, len(data)-1), (-1, len(data)-1), BG_MID)
    ts.add("TEXTCOLOR",  (0, len(data)-1), (-1, len(data)-1), ACCENT)
    t.setStyle(ts)
    story.append(t)

    # ── Disclaimer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BG_LIGHT))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Modification recommendations are generated using physics models and the Vel knowledge base. "
        "Cost estimates are approximate and vary by region and supplier. "
        "Always consult a qualified mechanic before performing modifications. "
        "Improper modifications can cause engine failure or safety hazards.",
        styles["VelBody"]
    ))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    logging.info(f"Mod plan PDF generated: {pdf_path}")
    return pdf_path, None


def generate_vehicle_spec_report(car_name, engine_name, specs_dict, apps_list=None):
    """
    Generate a clean PDF spec sheet for a single vehicle/engine.
    specs_dict: dict of spec_name: value
    apps_list: list of vehicle application dicts
    Returns: path to generated PDF
    """
    if not REPORTLAB_OK:
        return None, "ReportLab not installed."

    report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path  = os.path.join(REPORTS_DIR, f"{report_id}_spec.pdf")
    styles    = build_styles()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=32*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    story = []

    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(car_name or engine_name, styles["VelTitle"]))
    story.append(Paragraph(
        f"Engine: {engine_name} — Vel Specification Report",
        styles["VelSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=12))

    # Specs table
    story.append(Paragraph("Technical Specifications", styles["VelH2"]))
    data = [["Specification", "Value"]]
    for k, v in specs_dict.items():
        if v and str(v) not in ("None", "nan", ""):
            data.append([k.replace("_", " ").title(), str(v)])

    table_data = [[Paragraph(str(c), styles["VelBody"]) for c in row]
                  for row in data]
    t = Table(table_data, colWidths=[80*mm, 85*mm])
    t.setStyle(header_table_style())
    story.append(t)

    # Applications
    if apps_list:
        story.append(Spacer(1, 8*mm))
        story.append(Paragraph("Vehicle Applications", styles["VelH2"]))
        data = [["Vehicle", "Years", "Power", "Torque", "Notes"]]
        for app in apps_list:
            data.append([
                app.get("vehicle", "—"),
                f"{app.get('year_start','?')}–{app.get('year_end','?')}",
                f"{app.get('power_hp','—')}hp" if app.get("power_hp") else "—",
                f"{app.get('torque_nm','—')}Nm" if app.get("torque_nm") else "—",
                app.get("notes", ""),
            ])
        table_data = [[Paragraph(str(c), styles["VelBody"]) for c in row]
                      for row in data]
        t = Table(table_data, colWidths=[50*mm, 25*mm, 20*mm, 20*mm, 50*mm])
        t.setStyle(header_table_style())
        story.append(t)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    logging.info(f"Spec PDF generated: {pdf_path}")
    return pdf_path, None


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not REPORTLAB_OK:
        print("ReportLab not installed.")
        print("Run: pip install reportlab --break-system-packages")
        exit(1)

    print("Testing PDF generation...")

    # Test spec report
    pdf, err = generate_vehicle_spec_report(
        car_name="Toyota Supra A80",
        engine_name="Toyota 2JZ-GTE",
        specs_dict={
            "displacement": "2998cc (3.0L)",
            "power_hp":     "276hp",
            "torque_nm":    "379Nm",
            "configuration": "Inline-6",
            "aspiration":   "Twin Turbocharged",
            "compression_ratio": "8.5:1",
            "bore_mm":      "86mm",
            "stroke_mm":    "86mm",
            "valvetrain":   "DOHC 24v",
            "fuel_system":  "Sequential fuel injection",
            "production":   "1991–2002",
            "confidence":   "verified_manual",
        },
        apps_list=[
            {"vehicle": "Toyota Supra A80", "year_start": 1993, "year_end": 1998,
             "power_hp": 276, "torque_nm": 379, "notes": "JDM twin turbo"},
            {"vehicle": "Toyota Aristo", "year_start": 1991, "year_end": 2004,
             "power_hp": 276, "torque_nm": 379, "notes": "JDM"},
        ]
    )

    if err:
        print(f"Error: {err}")
    else:
        print(f"Spec report: {pdf}")

    # Test mod plan report
    from optimization_engine import optimize, load_car_specs, solve_performance_build
    specs = load_car_specs("Toyota Supra MK4", "2JZ-GTE")
    plan  = solve_performance_build(specs, 500)

    pdf2, err2 = generate_optimization_report(plan, "Toyota Supra MK4")
    if err2:
        print(f"Error: {err2}")
    else:
        print(f"Mod plan report: {pdf2}")

    print("Done — check reports/ directory")
