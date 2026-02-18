"""Parse broker CSV exports into normalized transaction dicts."""

import csv
import io
from datetime import datetime


def parse_degiro_csv(file_content: str) -> list[dict]:
    """Parse DEGIRO CSV export.

    Expected columns: Datum, Tijd, Product, ISIN, Beurs, Uitvoeringsplaats,
    Aantal, Koers, Waarde lokale valuta, Waarde, Wisselkoers, Transactiekosten en/of,
    Totaal, Order Id
    """
    reader = csv.DictReader(io.StringIO(file_content))
    transactions = []

    for row in reader:
        # Skip empty rows
        if not row.get("Datum"):
            continue

        # Parse date (DD-MM-YYYY format)
        try:
            tx_date = datetime.strptime(row["Datum"].strip(), "%d-%m-%Y").date()
        except (ValueError, KeyError):
            continue

        # Parse amounts — DEGIRO uses comma as decimal separator
        def parse_num(val):
            if not val or not val.strip():
                return None
            return float(val.strip().replace(",", "."))

        quantity = parse_num(row.get("Aantal"))
        price = parse_num(row.get("Koers"))
        total = parse_num(row.get("Totaal"))
        costs = parse_num(row.get("Transactiekosten en/of", ""))

        # Determine transaction type from context
        product = row.get("Product", "").strip()
        isin = row.get("ISIN", "").strip()

        if quantity and quantity > 0 and price:
            tx_type = "buy"
        elif quantity and quantity < 0 and price:
            tx_type = "sell"
        elif "dividend" in product.lower() or "dividend" in row.get("Omschrijving", "").lower():
            tx_type = "dividend"
        elif costs and not quantity:
            tx_type = "cost"
        else:
            tx_type = "other"

        # Build ticker from ISIN + exchange
        exchange = row.get("Beurs", "").strip()
        ticker = _isin_to_ticker(isin, exchange) if isin else None

        transactions.append({
            "date": tx_date,
            "type": tx_type,
            "ticker": ticker,
            "description": product or f"DEGIRO transaction",
            "quantity": abs(quantity) if quantity else None,
            "price": price,
            "amount": total if total else 0,
            "currency": "EUR",
            "broker_ref": row.get("Order Id", "").strip(),
        })

    return transactions


def parse_ib_csv(file_content: str) -> list[dict]:
    """Parse Interactive Brokers CSV export (Trades section).

    IB exports are more complex with multiple sections.
    We focus on the Trades section.
    """
    reader = csv.reader(io.StringIO(file_content))
    transactions = []
    in_trades = False
    headers = []

    for row in reader:
        if not row:
            continue

        # Find the Trades section
        if row[0] == "Trades" and row[1] == "Header":
            headers = row[2:]
            in_trades = True
            continue
        elif row[0] == "Trades" and row[1] == "Data" and in_trades:
            data = dict(zip(headers, row[2:]))

            try:
                tx_date = datetime.strptime(data.get("Date/Time", "").split(",")[0].strip(), "%Y-%m-%d").date()
            except (ValueError, KeyError):
                continue

            quantity = float(data.get("Quantity", 0))
            price = float(data.get("T. Price", 0))
            proceeds = float(data.get("Proceeds", 0))
            commission = float(data.get("Comm/Fee", 0))

            tx_type = "buy" if quantity > 0 else "sell"

            transactions.append({
                "date": tx_date,
                "type": tx_type,
                "ticker": data.get("Symbol", ""),
                "description": data.get("Symbol", "") + " " + data.get("Date/Time", ""),
                "quantity": abs(quantity),
                "price": price,
                "amount": proceeds + commission,
                "currency": data.get("Currency", "EUR"),
                "broker_ref": data.get("Code", ""),
            })
        elif row[0] != "Trades" and in_trades:
            in_trades = False

    return transactions


def _isin_to_ticker(isin: str, exchange: str) -> str:
    """Best-effort ISIN to ticker mapping.

    For a real product you'd use a lookup table or API.
    This handles common ETFs that DEGIRO users trade.
    """
    common = {
        "IE00B4L5Y983": "IWDA",
        "IE00B3RBWM25": "VWRL",
        "IE00BK5BQT80": "VWCE",
        "IE00BKM4GZ66": "EMIM",
        "LU0392494562": "DBXW",
        "IE00B0M62Q58": "IUSQ",
        "NL0000009165": "HEIA",
        "NL0010273215": "ASML",
        "NL0000235190": "AIR",
        "US0378331005": "AAPL",
        "US5949181045": "MSFT",
    }

    suffix_map = {
        "XET": ".DE",
        "EPA": ".PA",
        "AMS": ".AS",
        "LSE": ".L",
        "EAM": ".AS",
    }

    ticker = common.get(isin, isin[:6])
    suffix = suffix_map.get(exchange, "")
    return ticker + suffix
