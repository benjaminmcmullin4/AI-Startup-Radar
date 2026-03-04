"""Chart and visualization functions for the Startup Radar dashboard.

All charts use the light theme with the COLORS design system:
teal (#1ABC9C) as primary accent, navy (#0A0A0A) for text,
white backgrounds with light gray borders.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from config import COLORS, STAGE_LABELS


def score_gauge(score: float, title: str = "Composite Score") -> go.Figure:
    """Radial gauge for composite score. White bg, teal bar, navy text."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score or 0,
        title={"text": title, "font": {"size": 14, "color": COLORS["navy"]}},
        number={"font": {"size": 28, "color": COLORS["navy"]}},
        gauge={
            "axis": {"range": [0, 10], "tickwidth": 1, "tickcolor": COLORS["muted"]},
            "bar": {"color": COLORS["teal"]},
            "bgcolor": COLORS["white"],
            "borderwidth": 1,
            "bordercolor": COLORS["light_gray"],
            "steps": [
                {"range": [0, 4], "color": "#F0F4F8"},
                {"range": [4, 6], "color": "#E8F6F3"},
                {"range": [6, 8], "color": "#FEF9E7"},
                {"range": [8, 10], "color": "#FDEDEC"},
            ],
            "threshold": {
                "line": {"color": COLORS["red_accent"], "width": 2},
                "thickness": 0.75,
                "value": 8,
            },
        },
    ))
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor=COLORS["white"],
        plot_bgcolor=COLORS["white"],
        font=dict(family="Inter, sans-serif", color=COLORS["navy"]),
    )
    return fig


def radar_chart(scores: dict, title: str = "Score Breakdown") -> go.Figure:
    """Radar/spider chart for dimension scores. White bg, teal line."""
    categories = ["Financial", "Team", "Market", "Product", "Momentum"]
    values = [
        scores.get("financial_score", 0) or 0,
        scores.get("team_score", 0) or 0,
        scores.get("market_score", 0) or 0,
        scores.get("product_score", 0) or 0,
        scores.get("momentum_score", 0) or 0,
    ]
    # Close the polygon
    values.append(values[0])
    categories.append(categories[0])

    fig = go.Figure(go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        line=dict(color=COLORS["teal"], width=2),
        fillcolor="rgba(26, 188, 156, 0.15)",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                gridcolor=COLORS["light_gray"],
                linecolor=COLORS["light_gray"],
                tickfont=dict(color=COLORS["muted"], size=10),
            ),
            angularaxis=dict(
                gridcolor=COLORS["light_gray"],
                linecolor=COLORS["light_gray"],
                tickfont=dict(color=COLORS["navy"], size=11),
            ),
            bgcolor=COLORS["white"],
        ),
        showlegend=False,
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        title=dict(text=title, font=dict(size=14, color=COLORS["navy"])),
        paper_bgcolor=COLORS["white"],
        plot_bgcolor=COLORS["white"],
        font=dict(family="Inter, sans-serif", color=COLORS["navy"]),
    )
    return fig


def pipeline_funnel(stage_counts: dict) -> go.Figure:
    """Funnel chart for pipeline stages. Teal/navy gradient."""
    stages = ["new", "screening", "deep_dive", "ic_review", "monitor", "pass"]
    labels = [STAGE_LABELS.get(s, s) for s in stages]
    values = [stage_counts.get(s, 0) for s in stages]

    # Teal-to-navy gradient
    gradient_colors = [
        COLORS["teal"],       # new
        "#17A589",            # screening (slightly darker teal)
        "#148F77",            # deep_dive
        "#117864",            # ic_review
        COLORS["steel_blue"], # monitor
        COLORS["navy"],       # pass
    ]

    fig = go.Figure(go.Funnel(
        y=labels,
        x=values,
        marker=dict(color=gradient_colors),
        textinfo="value+percent initial",
        textfont=dict(color=COLORS["white"], size=12),
    ))
    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text="Pipeline Funnel", font=dict(size=14, color=COLORS["navy"])),
        paper_bgcolor=COLORS["white"],
        plot_bgcolor=COLORS["white"],
        font=dict(family="Inter, sans-serif", color=COLORS["navy"]),
    )
    return fig


def sector_distribution_chart(sector_counts: dict) -> go.Figure | None:
    """Horizontal bar chart for sector distribution. Teal color scale."""
    if not sector_counts:
        return None

    sectors = list(sector_counts.keys())
    counts = list(sector_counts.values())

    fig = px.bar(
        x=counts,
        y=sectors,
        orientation="h",
        color=counts,
        color_continuous_scale=[
            [0, "#E8F6F3"],
            [0.5, COLORS["teal"]],
            [1, "#0E6655"],
        ],
        labels={"x": "Companies", "y": "Sector"},
    )
    fig.update_layout(
        height=max(250, len(sectors) * 30),
        margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text="Sector Distribution", font=dict(size=14, color=COLORS["navy"])),
        showlegend=False,
        coloraxis_showscale=False,
        paper_bgcolor=COLORS["white"],
        plot_bgcolor=COLORS["white"],
        font=dict(family="Inter, sans-serif", color=COLORS["navy"]),
        xaxis=dict(gridcolor=COLORS["light_gray"], zerolinecolor=COLORS["light_gray"]),
        yaxis=dict(gridcolor=COLORS["light_gray"]),
    )
    return fig
