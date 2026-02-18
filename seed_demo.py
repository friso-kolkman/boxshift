"""Generate realistic demo data for BoxShift testing."""

import os
import sys
from datetime import date, datetime, timedelta
import random

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from models import Base, Lead, User, BV, Transaction, Holding, init_db
from services.transaction_engine import process_transactions

# Init DB
os.makedirs(os.path.join(config.BASE_DIR, "data"), exist_ok=True)
engine, Session = init_db(config.DATABASE_URL)


def seed():
    db = Session()

    # Clean existing data
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()

    print("Seeding demo data...")

    # ── Leads ──
    lead_emails = [
        "jan@voorbeeld.nl", "petra@gmail.com", "mark.devries@outlook.com",
        "sophie@tech-startup.nl", "bas@beleggingen.nl", "lisa@hetnet.nl",
        "tom.jansen@hotmail.com", "anna@investeer.nl", "chris@degiro-user.nl",
        "emma@financieel.nl", "daan@werk.nl", "eva@portfolio.nl",
    ]
    for i, email in enumerate(lead_emails):
        db.add(Lead(
            email=email,
            created_at=datetime(2026, 1, 15) + timedelta(days=i * 2),
            status=random.choice(["new", "new", "new", "contacted"]),
        ))
    db.flush()

    # ── Demo user ──
    user = User(
        email="demo@boxshift.nl",
        name="Jan de Vries",
        github_username="demo",
        phone="+31 6 12345678",
        vermogen_estimate=500_000,
        broker="degiro",
        situation="particulier",
        onboarded=True,
    )
    db.add(user)
    db.flush()

    # Mark demo lead as converted
    demo_lead = Lead(email="demo@boxshift.nl", status="converted",
                     created_at=datetime(2026, 1, 10))
    db.add(demo_lead)

    # ── BV ──
    bv = BV(
        user_id=user.id,
        name="De Vries Beleggingen B.V.",
        kvk_number="12345678",
        oprichtingsdatum=date(2025, 6, 1),
        status="active",
    )
    db.add(bv)
    db.flush()

    # ── Transactions ──
    # Simulate 2 years of investing: 2025 and 2026

    etfs = [
        ("VWRL.AS", "Vanguard FTSE All-World", 95.0, 115.0),
        ("IWDA.AS", "iShares Core MSCI World", 72.0, 88.0),
        ("VWCE.DE", "Vanguard FTSE All-World Acc", 100.0, 125.0),
        ("EMIM.AS", "iShares Core EM IMI", 28.0, 34.0),
    ]

    stocks = [
        ("ASML.AS", "ASML Holding", 680.0, 850.0),
        ("HEIA.AS", "Heineken", 75.0, 92.0),
    ]

    all_instruments = etfs + stocks
    transactions = []

    # Initial deposit — June 2025
    transactions.append({
        "date": date(2025, 6, 15),
        "type": "deposit",
        "ticker": None,
        "description": "Inbreng kapitaal",
        "quantity": None,
        "price": None,
        "amount": 200_000.0,
    })

    # Monthly buys throughout 2025 (Jul - Dec)
    for month in range(7, 13):
        ticker, name, low, high = random.choice(etfs)
        price = round(random.uniform(low, high), 2)
        qty = round(random.uniform(10, 50), 0)
        total = round(qty * price, 2)
        transactions.append({
            "date": date(2025, month, random.randint(1, 28)),
            "type": "buy",
            "ticker": ticker,
            "description": name,
            "quantity": qty,
            "price": price,
            "amount": -total,
        })

    # Some individual stock buys
    for inst in stocks:
        ticker, name, low, high = inst
        price = round(random.uniform(low, (low + high) / 2), 2)
        qty = round(random.uniform(2, 15), 0)
        total = round(qty * price, 2)
        transactions.append({
            "date": date(2025, random.randint(7, 11), random.randint(1, 28)),
            "type": "buy",
            "ticker": ticker,
            "description": name,
            "quantity": qty,
            "price": price,
            "amount": -total,
        })

    # Dividends in 2025
    for _ in range(3):
        ticker, name, _, _ = random.choice(etfs)
        div_amount = round(random.uniform(50, 300), 2)
        transactions.append({
            "date": date(2025, random.choice([9, 11, 12]), random.randint(1, 28)),
            "type": "dividend",
            "ticker": ticker,
            "description": f"Dividend {name}",
            "quantity": None,
            "price": None,
            "amount": div_amount,
        })

    # Transaction costs in 2025
    transactions.append({
        "date": date(2025, 12, 31),
        "type": "cost",
        "ticker": None,
        "description": "DEGIRO transactiekosten 2025",
        "quantity": None,
        "price": None,
        "amount": -45.80,
    })

    # ── 2026 transactions ──
    transactions.append({
        "date": date(2026, 1, 5),
        "type": "deposit",
        "ticker": None,
        "description": "Aanvullende storting",
        "quantity": None,
        "price": None,
        "amount": 50_000.0,
    })

    # More buys in 2026
    for month in range(1, 3):
        ticker, name, low, high = random.choice(all_instruments)
        price = round(random.uniform(low, high), 2)
        qty = round(random.uniform(5, 30), 0)
        total = round(qty * price, 2)
        transactions.append({
            "date": date(2026, month, random.randint(1, 28)),
            "type": "buy",
            "ticker": ticker,
            "description": name,
            "quantity": qty,
            "price": price,
            "amount": -total,
        })

    # A sell (partial profit taking) in 2026
    ticker, name, low, high = random.choice(etfs)
    sell_price = round(random.uniform((low + high) / 2, high), 2)
    sell_qty = round(random.uniform(5, 15), 0)
    # For the sell, the amount represents the realized gain (proceeds - cost)
    # In real data this would be proceeds; for MVP demo we store the gain
    sell_proceeds = round(sell_qty * sell_price, 2)
    transactions.append({
        "date": date(2026, 2, 10),
        "type": "sell",
        "ticker": ticker,
        "description": f"Verkoop {name}",
        "quantity": sell_qty,
        "price": sell_price,
        "amount": sell_proceeds,
    })

    # 2026 dividend
    ticker, name, _, _ = random.choice(etfs)
    transactions.append({
        "date": date(2026, 1, 15),
        "type": "dividend",
        "ticker": ticker,
        "description": f"Dividend {name}",
        "quantity": None,
        "price": None,
        "amount": round(random.uniform(100, 500), 2),
    })

    # Interest income
    transactions.append({
        "date": date(2025, 12, 31),
        "type": "interest",
        "ticker": None,
        "description": "Rente-inkomsten DEGIRO kasrekening",
        "quantity": None,
        "price": None,
        "amount": 125.40,
    })

    # Sort by date and save
    transactions.sort(key=lambda t: t["date"])

    for tx_data in transactions:
        tx = Transaction(
            bv_id=bv.id,
            date=tx_data["date"],
            type=tx_data["type"],
            ticker=tx_data.get("ticker"),
            description=tx_data["description"],
            quantity=tx_data.get("quantity"),
            price=tx_data.get("price"),
            amount=tx_data["amount"],
            currency="EUR",
            broker_ref="",
            category=tx_data["type"],
        )
        db.add(tx)

    db.commit()

    # Process transactions into holdings
    summary = process_transactions(db, bv.id)
    print(f"Processed {summary['processed']} transactions, realized gains: {summary['realized_gains']:.2f}")

    # Generate annual report for 2025
    from services.annual_report import generate_annual_report
    report = generate_annual_report(db, bv.id, 2025)
    print(f"Generated 2025 jaarrekening (status: {report.status})")

    db.close()

    print(f"\nDemo data seeded successfully!")
    print(f"  - {len(lead_emails) + 1} leads")
    print(f"  - 1 user (demo@boxshift.nl)")
    print(f"  - 1 BV (De Vries Beleggingen B.V.)")
    print(f"  - {len(transactions)} transactions")
    print(f"\nStart the app with: python app.py")
    print(f"Dashboard: http://localhost:8080/dashboard/1")


if __name__ == "__main__":
    seed()
