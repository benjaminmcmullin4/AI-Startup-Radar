def fmt_money(value: float, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    if value >= 1000:
        return f"${value / 1000:.{decimals}f}B"
    return f"${value:.{decimals}f}M"


def fmt_pct(value: float, decimals: int = 0) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def fmt_number(value: int) -> str:
    if value is None:
        return "N/A"
    if value >= 1000:
        return f"{value:,.0f}"
    return str(value)


def fmt_score(score: float) -> str:
    if score is None:
        return "N/A"
    return f"{score:.1f}"


def tier_emoji(tier: str) -> str:
    return {"hot": "🔥", "warm": "🟡", "monitor": "🔵", "pass": "⚪"}.get(tier, "⚪")


def stage_emoji(stage: str) -> str:
    return {
        "new": "🆕",
        "screening": "🔍",
        "deep_dive": "🏊",
        "ic_review": "📋",
        "pass": "❌",
        "monitor": "👁️",
    }.get(stage, "❓")
