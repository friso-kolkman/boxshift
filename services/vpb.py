"""VPB (vennootschapsbelasting) calculator and aangifte generator for beleggings-BV."""

from datetime import date


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


def generate_vpb_aangifte(db, bv_id: int, year: int) -> dict:
    """Generate complete VPB-aangifte data for a beleggings-BV.

    Returns a dict with all fields needed to file via Mijn Belastingdienst Zakelijk.
    """
    from models import BV, AnnualReport, VPBFiling, Transaction, Holding
    from sqlalchemy import extract

    bv = db.query(BV).get(bv_id)
    report = db.query(AnnualReport).filter_by(bv_id=bv_id, year=year).first()
    filing = db.query(VPBFiling).filter_by(bv_id=bv_id, year=year).first()

    if not report or not filing:
        return None

    balans = report.balans
    wv = report.winst_verlies
    breakdown = vpb_breakdown(filing.taxable_profit)

    # Boekjaar
    boekjaar_start = date(year, 1, 1)
    boekjaar_eind = date(year, 12, 31)

    # Holdings detail for effectenspecificatie
    holdings = db.query(Holding).filter_by(bv_id=bv_id).all()
    effecten_detail = []
    for h in holdings:
        if h.quantity > 0:
            effecten_detail.append({
                "ticker": h.ticker,
                "naam": h.name,
                "aantal": h.quantity,
                "kostprijs_per_stuk": round(h.avg_cost_price, 2),
                "totale_kostprijs": round(h.total_cost, 2),
            })

    # Transaction summary per type for the year
    year_txs = (
        db.query(Transaction)
        .filter(Transaction.bv_id == bv_id, extract("year", Transaction.date) == year)
        .all()
    )

    tx_summary = {
        "aankopen": 0.0,
        "verkopen": 0.0,
        "dividend": 0.0,
        "rente": 0.0,
        "kosten": 0.0,
        "stortingen": 0.0,
        "onttrekkingen": 0.0,
    }
    for tx in year_txs:
        if tx.type == "buy":
            tx_summary["aankopen"] += abs(tx.amount)
        elif tx.type == "sell":
            tx_summary["verkopen"] += abs(tx.amount)
        elif tx.type == "dividend":
            tx_summary["dividend"] += abs(tx.amount)
        elif tx.type == "interest":
            tx_summary["rente"] += abs(tx.amount)
        elif tx.type == "cost":
            tx_summary["kosten"] += abs(tx.amount)
        elif tx.type == "deposit":
            tx_summary["stortingen"] += abs(tx.amount)
        elif tx.type == "withdrawal":
            tx_summary["onttrekkingen"] += abs(tx.amount)

    tx_summary = {k: round(v, 2) for k, v in tx_summary.items()}

    # Deadline
    deadline = date(year + 1, 6, 1)

    return {
        # Identificatie
        "bv_naam": bv.name,
        "kvk_nummer": bv.kvk_number or "Nog invullen",
        "boekjaar_start": boekjaar_start.strftime("%d-%m-%Y"),
        "boekjaar_eind": boekjaar_eind.strftime("%d-%m-%Y"),
        "jaar": year,
        "deadline": deadline.strftime("%d-%m-%Y"),

        # Balans
        "balans": balans,

        # W&V
        "winst_verlies": wv,

        # Fiscale winstberekening
        "fiscale_winst": {
            "gerealiseerde_koersresultaten": wv.get("gerealiseerde_koersresultaten", 0),
            "dividendinkomsten": wv.get("dividendinkomsten", 0),
            "rente_inkomsten": wv.get("rente_inkomsten", 0),
            "aftrekbare_kosten": round(
                wv.get("transactiekosten", 0) + wv.get("overige_kosten", 0), 2
            ),
            "belastbare_winst": round(filing.taxable_profit, 2),
        },

        # VPB berekening
        "vpb": breakdown,

        # Effectenspecificatie
        "effecten": effecten_detail,

        # Transactie-overzicht
        "transacties": tx_summary,

        # Status
        "status": filing.status,
    }
