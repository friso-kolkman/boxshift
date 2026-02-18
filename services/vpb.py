"""VPB (vennootschapsbelasting) calculator for beleggings-BV."""


def calculate_vpb(taxable_profit: float) -> float:
    """Calculate VPB amount.

    Rates (2024/2025):
    - 19% over first €200.000
    - 25.8% over everything above €200.000

    If taxable_profit <= 0, no VPB is due.
    """
    if taxable_profit <= 0:
        return 0.0

    threshold = 200_000
    low_rate = 0.19
    high_rate = 0.258

    if taxable_profit <= threshold:
        return round(taxable_profit * low_rate, 2)
    else:
        return round(
            threshold * low_rate + (taxable_profit - threshold) * high_rate, 2
        )


def vpb_breakdown(taxable_profit: float) -> dict:
    """Return detailed VPB calculation breakdown."""
    if taxable_profit <= 0:
        return {
            "taxable_profit": round(taxable_profit, 2),
            "low_bracket": 0.0,
            "low_bracket_tax": 0.0,
            "high_bracket": 0.0,
            "high_bracket_tax": 0.0,
            "total_vpb": 0.0,
            "effective_rate": 0.0,
        }

    threshold = 200_000

    low_bracket = min(taxable_profit, threshold)
    high_bracket = max(0, taxable_profit - threshold)

    low_tax = low_bracket * 0.19
    high_tax = high_bracket * 0.258
    total = low_tax + high_tax

    return {
        "taxable_profit": round(taxable_profit, 2),
        "low_bracket": round(low_bracket, 2),
        "low_bracket_tax": round(low_tax, 2),
        "high_bracket": round(high_bracket, 2),
        "high_bracket_tax": round(high_tax, 2),
        "total_vpb": round(total, 2),
        "effective_rate": round(total / taxable_profit * 100, 1) if taxable_profit > 0 else 0,
    }
