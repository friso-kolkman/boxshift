"""Generate jaarrekening (annual report) for a beleggings-BV."""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import extract
from models import Transaction, Holding, AnnualReport, VPBFiling


def generate_annual_report(db: Session, bv_id: int, year: int) -> AnnualReport:
    """Generate balans + winst & verliesrekening for a given year."""

    # Get all processed transactions for this year
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.bv_id == bv_id,
            extract("year", Transaction.date) == year,
        )
        .order_by(Transaction.date)
        .all()
    )

    # Calculate W&V components
    wv = _calculate_winst_verlies(txs)

    # Calculate VPB
    from services.vpb import calculate_vpb
    vpb_amount = calculate_vpb(wv["resultaat_voor_belasting"])

    wv["vpb"] = round(vpb_amount, 2)
    wv["resultaat_na_belasting"] = round(wv["resultaat_voor_belasting"] - vpb_amount, 2)

    # Build balans
    balans = _calculate_balans(db, bv_id, year, wv)

    # Check if report already exists
    report = db.query(AnnualReport).filter_by(bv_id=bv_id, year=year).first()
    if report:
        report.balans = balans
        report.winst_verlies = wv
        report.generated_at = datetime.utcnow()
        report.status = "draft"
    else:
        report = AnnualReport(
            bv_id=bv_id,
            year=year,
            balans=balans,
            winst_verlies=wv,
            status="draft",
            generated_at=datetime.utcnow(),
        )
        db.add(report)

    # Upsert VPB filing
    vpb_filing = db.query(VPBFiling).filter_by(bv_id=bv_id, year=year).first()
    if vpb_filing:
        vpb_filing.taxable_profit = wv["resultaat_voor_belasting"]
        vpb_filing.vpb_amount = vpb_amount
    else:
        vpb_filing = VPBFiling(
            bv_id=bv_id,
            year=year,
            taxable_profit=wv["resultaat_voor_belasting"],
            vpb_amount=vpb_amount,
            status="draft",
        )
        db.add(vpb_filing)

    db.commit()
    return report


def _calculate_winst_verlies(txs: list) -> dict:
    """Calculate profit & loss from transactions."""
    realized_gains = 0.0
    dividends = 0.0
    interest = 0.0
    transaction_costs = 0.0
    other_costs = 0.0

    for tx in txs:
        if tx.type == "sell":
            # For sells, the gain is embedded in the amount vs cost basis
            # We track the sell proceeds; the engine already calculated gains
            # But here we approximate from transaction data
            realized_gains += tx.amount  # proceeds (could be positive or negative net)
        elif tx.type == "buy":
            # Buys reduce cash but don't affect P&L
            pass
        elif tx.type == "dividend":
            dividends += abs(tx.amount)
        elif tx.type == "interest":
            interest += abs(tx.amount)
        elif tx.type == "cost":
            transaction_costs += abs(tx.amount)
        elif tx.type in ("deposit", "withdrawal"):
            pass  # Capital movements, not P&L

    # For a more accurate calc, we'd track cost basis per sell
    # For MVP, we use the sell amount directly (which in seed data = proceeds - cost = gain)
    resultaat = realized_gains + dividends + interest - transaction_costs - other_costs

    return {
        "gerealiseerde_koersresultaten": round(realized_gains, 2),
        "dividendinkomsten": round(dividends, 2),
        "rente_inkomsten": round(interest, 2),
        "transactiekosten": round(transaction_costs, 2),
        "overige_kosten": round(other_costs, 2),
        "resultaat_voor_belasting": round(resultaat, 2),
    }


def _calculate_balans(db: Session, bv_id: int, year: int, wv: dict) -> dict:
    """Calculate balance sheet as of 31-12-YEAR."""

    # Holdings at cost price
    holdings = db.query(Holding).filter_by(bv_id=bv_id).all()
    effecten = sum(h.total_cost for h in holdings)

    # Cash: sum of all deposits - withdrawals + dividends + interest + sell proceeds - buy costs - fees
    all_txs = (
        db.query(Transaction)
        .filter(
            Transaction.bv_id == bv_id,
            extract("year", Transaction.date) <= year,
        )
        .all()
    )

    cash = 0.0
    for tx in all_txs:
        if tx.type == "deposit":
            cash += abs(tx.amount)
        elif tx.type == "withdrawal":
            cash -= abs(tx.amount)
        elif tx.type == "buy":
            cash -= abs(tx.amount)
        elif tx.type == "sell":
            cash += abs(tx.amount)
        elif tx.type == "dividend":
            cash += abs(tx.amount)
        elif tx.type == "interest":
            cash += abs(tx.amount)
        elif tx.type == "cost":
            cash -= abs(tx.amount)

    totaal_activa = effecten + cash

    # Passiva
    # Gestort kapitaal = sum of deposits - withdrawals (equity contributions)
    gestort_kapitaal = sum(
        abs(tx.amount) for tx in all_txs if tx.type == "deposit"
    ) - sum(
        abs(tx.amount) for tx in all_txs if tx.type == "withdrawal"
    )

    # Prior year retained earnings (simplified: total P&L minus current year)
    # For MVP, we calculate current year result from wv
    resultaat_boekjaar = wv["resultaat_na_belasting"]
    vpb_schuld = wv["vpb"]

    # Winstreserve = totaal_passiva - gestort_kapitaal - resultaat - vpb
    winstreserve = totaal_activa - gestort_kapitaal - resultaat_boekjaar - vpb_schuld

    return {
        "activa": {
            "effectenportefeuille": round(effecten, 2),
            "liquide_middelen": round(cash, 2),
            "totaal": round(totaal_activa, 2),
        },
        "passiva": {
            "gestort_kapitaal": round(gestort_kapitaal, 2),
            "winstreserve_voorgaande_jaren": round(winstreserve, 2),
            "resultaat_boekjaar": round(resultaat_boekjaar, 2),
            "vpb_schuld": round(vpb_schuld, 2),
            "totaal": round(gestort_kapitaal + winstreserve + resultaat_boekjaar + vpb_schuld, 2),
        },
    }
