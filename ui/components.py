"""Shared UI components: score badges, charts, formatters."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from config.settings import TIER_COLORS, STAGE_LABELS


def tier_badge(tier: str):
    color = TIER_COLORS.get(tier, "#6b7280")
    label = tier.upper() if tier else "N/A"
    st.markdown(
        f'<span style="background-color:{color};color:white;padding:2px 10px;'
        f'border-radius:12px;font-size:0.85em;font-weight:600">{label}</span>',
        unsafe_allow_html=True,
    )


def score_gauge(score: float, title: str = "Composite Score"):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score or 0,
        title={"text": title, "font": {"size": 14}},
        number={"font": {"size": 28}},
        gauge={
            "axis": {"range": [0, 10], "tickwidth": 1},
            "bar": {"color": "#c8a86e"},
            "steps": [
                {"range": [0, 4], "color": "#f3f4f6"},
                {"range": [4, 6], "color": "#dbeafe"},
                {"range": [6, 8], "color": "#fef3c7"},
                {"range": [8, 10], "color": "#fecaca"},
            ],
            "threshold": {"line": {"color": "#ef4444", "width": 2}, "thickness": 0.75, "value": 8},
        },
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def radar_chart(scores: dict, title: str = "Score Breakdown"):
    categories = ["Financial", "Team", "Market", "Product", "Momentum"]
    values = [
        scores.get("financial_score", 0) or 0,
        scores.get("team_score", 0) or 0,
        scores.get("market_score", 0) or 0,
        scores.get("product_score", 0) or 0,
        scores.get("momentum_score", 0) or 0,
    ]
    values.append(values[0])  # close the polygon
    categories.append(categories[0])

    fig = go.Figure(go.Scatterpolar(
        r=values, theta=categories, fill="toself",
        line=dict(color="#c8a86e"), fillcolor="rgba(200,168,110,0.2)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        showlegend=False, height=300, margin=dict(l=40, r=40, t=40, b=40),
        title=dict(text=title, font=dict(size=14)),
    )
    return fig


def pipeline_funnel(stage_counts: dict):
    stages = ["new", "screening", "deep_dive", "ic_review", "monitor", "pass"]
    labels = [STAGE_LABELS.get(s, s) for s in stages]
    values = [stage_counts.get(s, 0) for s in stages]
    colors = ["#c8a86e", "#b8956a", "#a08060", "#887050", "#6b7280", "#4b5563"]

    fig = go.Figure(go.Funnel(
        y=labels, x=values,
        marker=dict(color=colors),
        textinfo="value+percent initial",
    ))
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10), title="Pipeline Funnel")
    return fig


def sector_distribution_chart(sector_counts: dict):
    if not sector_counts:
        return None
    sectors = list(sector_counts.keys())
    counts = list(sector_counts.values())
    fig = px.bar(x=counts, y=sectors, orientation="h", color=counts,
                 color_continuous_scale="Viridis", labels={"x": "Companies", "y": "Sector"})
    fig.update_layout(height=max(250, len(sectors) * 30), margin=dict(l=10, r=10, t=30, b=10),
                      title="Sector Distribution", showlegend=False, coloraxis_showscale=False)
    return fig


def thesis_fit_bar(fit_pct: float):
    color = "#22c55e" if fit_pct >= 70 else "#f59e0b" if fit_pct >= 40 else "#ef4444"
    st.markdown(
        f'<div style="background:#e5e7eb;border-radius:8px;height:24px;width:100%;position:relative">'
        f'<div style="background:{color};border-radius:8px;height:24px;width:{fit_pct}%;'
        f'display:flex;align-items:center;justify-content:center;color:white;font-weight:600;font-size:0.8em">'
        f'{fit_pct:.0f}%</div></div>',
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, delta: str = None):
    delta_html = ""
    if delta:
        color = "#22c55e" if not delta.startswith("-") else "#ef4444"
        delta_html = f'<div style="color:{color};font-size:0.85em">{delta}</div>'
    st.markdown(
        f'<div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:12px;padding:16px;text-align:center">'
        f'<div style="color:#9ca3af;font-size:0.85em;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:1.8em;font-weight:700;color:#fafafa">{value}</div>'
        f'{delta_html}</div>',
        unsafe_allow_html=True,
    )
