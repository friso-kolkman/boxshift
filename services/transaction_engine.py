"""Process transactions into holdings and track realized gains."""

from models import Transaction, Holding
from sqlalchemy.orm import Session


def process_transactions(db: Session, bv_id: int) -> dict:
    """Process all unprocessed transactions for a BV.

    Returns summary: {processed: int, realized_gains: float, errors: []}
    """
    transactions = (
        db.query(Transaction)
        .filter_by(bv_id=bv_id, processed=False)
        .order_by(Transaction.date)
        .all()
    )

    summary = {"processed": 0, "realized_gains": 0.0, "errors": []}

    for tx in transactions:
        try:
            if tx.type == "buy":
                _process_buy(db, tx)
            elif tx.type == "sell":
                gain = _process_sell(db, tx)
                summary["realized_gains"] += gain
            # dividend, interest, cost, deposit, withdrawal don't affect holdings
            tx.processed = True
            summary["processed"] += 1
        except Exception as e:
            summary["errors"].append(f"TX #{tx.id}: {str(e)}")

    db.commit()
    return summary


def _process_buy(db: Session, tx: Transaction):
    """Buy: add to holdings, recalculate weighted average cost price."""
    if not tx.ticker or not tx.quantity:
        return

    holding = db.query(Holding).filter_by(bv_id=tx.bv_id, ticker=tx.ticker).first()

    buy_cost = abs(tx.amount)  # total cost of this buy

    if holding:
        old_total = holding.quantity * holding.avg_cost_price
        new_total = old_total + buy_cost
        new_qty = holding.quantity + tx.quantity
        holding.avg_cost_price = new_total / new_qty if new_qty > 0 else 0
        holding.quantity = new_qty
        holding.total_cost = new_qty * holding.avg_cost_price
    else:
        avg_price = buy_cost / tx.quantity if tx.quantity > 0 else 0
        holding = Holding(
            bv_id=tx.bv_id,
            ticker=tx.ticker,
            name=tx.description,
            quantity=tx.quantity,
            avg_cost_price=avg_price,
            total_cost=buy_cost,
        )
        db.add(holding)


def _process_sell(db: Session, tx: Transaction) -> float:
    """Sell: reduce holdings, calculate realized gain/loss.

    Returns realized gain (positive) or loss (negative).
    """
    if not tx.ticker or not tx.quantity:
        return 0.0

    holding = db.query(Holding).filter_by(bv_id=tx.bv_id, ticker=tx.ticker).first()

    if not holding:
        return 0.0

    sell_qty = tx.quantity
    sell_proceeds = abs(tx.amount)
    cost_basis = sell_qty * holding.avg_cost_price
    realized_gain = sell_proceeds - cost_basis

    # Update holding
    holding.quantity -= sell_qty
    holding.total_cost = holding.quantity * holding.avg_cost_price

    # Remove holding if fully sold
    if holding.quantity <= 0.001:
        db.delete(holding)

    return realized_gain


def get_holdings_summary(db: Session, bv_id: int) -> dict:
    """Get current holdings summary for a BV."""
    holdings = db.query(Holding).filter_by(bv_id=bv_id).all()
    total_cost = sum(h.total_cost for h in holdings)
    return {
        "holdings": [
            {
                "ticker": h.ticker,
                "name": h.name,
                "quantity": h.quantity,
                "avg_cost_price": round(h.avg_cost_price, 2),
                "total_cost": round(h.total_cost, 2),
            }
            for h in holdings
        ],
        "total_portfolio_cost": round(total_cost, 2),
    }
