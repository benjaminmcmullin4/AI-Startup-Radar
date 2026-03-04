def validate_company_data(data: dict) -> list[str]:
    errors = []
    if not data.get("name"):
        errors.append("Company name is required")
    if data.get("arr_millions") is not None and data["arr_millions"] < 0:
        errors.append("ARR cannot be negative")
    if data.get("revenue_growth_pct") is not None and data["revenue_growth_pct"] < -100:
        errors.append("Revenue growth cannot be less than -100%")
    if data.get("gross_margin_pct") is not None and not (0 <= data["gross_margin_pct"] <= 100):
        errors.append("Gross margin must be between 0% and 100%")
    if data.get("net_retention_pct") is not None and data["net_retention_pct"] < 0:
        errors.append("Net retention cannot be negative")
    if data.get("founded_year") is not None and not (1990 <= data["founded_year"] <= 2026):
        errors.append("Founded year must be between 1990 and 2026")
    return errors


def validate_thesis_weights(weights: dict) -> list[str]:
    errors = []
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        errors.append(f"Weights must sum to 1.0 (currently {total:.2f})")
    for k, v in weights.items():
        if v < 0 or v > 1:
            errors.append(f"Weight '{k}' must be between 0 and 1")
    return errors
