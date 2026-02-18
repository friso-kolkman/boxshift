"""BoxShift Flask application — beleggings-BV automation platform."""

import os
import sys
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

import config
from models import Base, Lead, User, BV, Transaction, Holding, AnnualReport, VPBFiling, init_db

# Ensure data directory exists
os.makedirs(os.path.join(config.BASE_DIR, "data"), exist_ok=True)

app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static",
    template_folder="templates",
)
app.secret_key = config.SECRET_KEY

# Database setup
engine, Session = init_db(config.DATABASE_URL)


def get_db():
    return Session()


# ─── Landing page (static files) ──────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/<path:filename>.html")
def static_pages(filename):
    """Serve landing page HTML files."""
    return send_from_directory("static", f"{filename}.html")


# ─── Waitlist API ──────────────────────────────────────────────────────────

@app.route("/api/waitlist", methods=["POST"])
def waitlist_signup():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Geldig e-mailadres vereist"}), 400

    db = get_db()
    try:
        existing = db.query(Lead).filter_by(email=email).first()
        if existing:
            count = db.query(Lead).count()
            return jsonify({"message": "Je staat al op de lijst!", "position": count})

        lead = Lead(email=email)
        db.add(lead)
        db.commit()

        count = db.query(Lead).count()
        return jsonify({
            "message": f"Je bent nummer #{count}!",
            "position": count,
        })
    finally:
        db.close()


# ─── Admin: Leads overview ───────────────────────────────────────────────

@app.route("/admin/leads")
def admin_leads():
    db = get_db()
    try:
        leads = db.query(Lead).order_by(Lead.created_at.desc()).all()
        return render_template("admin_leads.html", leads=leads)
    finally:
        db.close()


# ─── Onboarding ──────────────────────────────────────────────────────────

@app.route("/onboarding")
def onboarding():
    return render_template("onboarding.html")


@app.route("/api/onboard", methods=["POST"])
def api_onboard():
    data = request.form

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip() or None
    vermogen = int(data.get("vermogen_estimate", 0) or 0)
    broker = data.get("broker", "degiro")
    situation = data.get("situation", "particulier")

    if not name or not email:
        return render_template("onboarding.html", error="Naam en e-mail zijn verplicht")

    db = get_db()
    try:
        # Check if user already exists
        user = db.query(User).filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                name=name,
                phone=phone,
                vermogen_estimate=vermogen,
                broker=broker,
                situation=situation,
            )
            db.add(user)
            db.flush()

            # Create empty BV
            bv_name = f"{name.split()[0]} Beleggingen B.V." if name else "Mijn Beleggingen B.V."
            bv = BV(user_id=user.id, name=bv_name)
            db.add(bv)

            # Convert lead if exists
            lead = db.query(Lead).filter_by(email=email).first()
            if lead:
                lead.status = "converted"

            db.commit()

        return redirect(url_for("dashboard", user_id=user.id))
    finally:
        db.close()


# ─── Dashboard ───────────────────────────────────────────────────────────

@app.route("/dashboard/<int:user_id>")
def dashboard(user_id):
    db = get_db()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return redirect(url_for("onboarding"))

        bv = db.query(BV).filter_by(user_id=user_id).first()
        holdings = []
        total_cost = 0
        tx_count = 0
        ytd_pl = 0

        if bv:
            holdings = db.query(Holding).filter_by(bv_id=bv.id).all()
            total_cost = sum(h.total_cost for h in holdings)
            tx_count = db.query(Transaction).filter_by(bv_id=bv.id).count()

            # YTD P&L: sum of dividends + interest + sell amounts - costs for current year
            current_year = datetime.now().year
            from sqlalchemy import extract
            year_txs = (
                db.query(Transaction)
                .filter(
                    Transaction.bv_id == bv.id,
                    extract("year", Transaction.date) == current_year,
                )
                .all()
            )
            for tx in year_txs:
                if tx.type in ("sell", "dividend", "interest"):
                    ytd_pl += tx.amount
                elif tx.type == "cost":
                    ytd_pl -= abs(tx.amount)

        return render_template(
            "dashboard.html",
            user=user,
            bv=bv,
            holdings=holdings,
            total_cost=round(total_cost, 2),
            tx_count=tx_count,
            ytd_pl=round(ytd_pl, 2),
        )
    finally:
        db.close()


# ─── CSV Import ──────────────────────────────────────────────────────────

@app.route("/api/import", methods=["POST"])
def import_csv():
    user_id = request.form.get("user_id", type=int)
    broker_type = request.form.get("broker", "degiro")
    file = request.files.get("csv_file")

    if not file or not user_id:
        return jsonify({"error": "Bestand en user_id vereist"}), 400

    db = get_db()
    try:
        bv = db.query(BV).filter_by(user_id=user_id).first()
        if not bv:
            return jsonify({"error": "Geen BV gevonden"}), 404

        content = file.read().decode("utf-8-sig")

        from services.broker_import import parse_degiro_csv, parse_ib_csv
        if broker_type == "ib":
            parsed = parse_ib_csv(content)
        else:
            parsed = parse_degiro_csv(content)

        # Optionally classify with AI
        from services.ai_classifier import classify_transactions
        parsed = classify_transactions(parsed)

        # Save transactions
        count = 0
        for tx_data in parsed:
            tx = Transaction(
                bv_id=bv.id,
                date=tx_data["date"],
                type=tx_data.get("type", "other"),
                ticker=tx_data.get("ticker"),
                description=tx_data["description"],
                quantity=tx_data.get("quantity"),
                price=tx_data.get("price"),
                amount=tx_data["amount"],
                currency=tx_data.get("currency", "EUR"),
                broker_ref=tx_data.get("broker_ref", ""),
                category=tx_data.get("type"),
            )
            db.add(tx)
            count += 1

        db.commit()

        # Process transactions into holdings
        from services.transaction_engine import process_transactions
        summary = process_transactions(db, bv.id)

        return redirect(url_for("dashboard", user_id=user_id))
    finally:
        db.close()


# ─── Transactions view ───────────────────────────────────────────────────

@app.route("/transactions/<int:user_id>")
def transactions_view(user_id):
    db = get_db()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return redirect(url_for("onboarding"))

        bv = db.query(BV).filter_by(user_id=user_id).first()
        txs = []
        filter_type = request.args.get("type", "")
        filter_year = request.args.get("year", "")

        if bv:
            query = db.query(Transaction).filter_by(bv_id=bv.id)
            if filter_type:
                query = query.filter_by(type=filter_type)
            if filter_year:
                from sqlalchemy import extract
                query = query.filter(extract("year", Transaction.date) == int(filter_year))
            txs = query.order_by(Transaction.date.desc()).all()

        # Get available years
        years = set()
        if bv:
            all_txs = db.query(Transaction.date).filter_by(bv_id=bv.id).all()
            years = sorted(set(tx.date.year for tx in all_txs), reverse=True)

        return render_template(
            "transactions.html",
            user=user,
            bv=bv,
            transactions=txs,
            filter_type=filter_type,
            filter_year=filter_year,
            years=years,
        )
    finally:
        db.close()


# ─── Annual Report ────────────────────────────────────────────────────────

@app.route("/annual-report/<int:user_id>")
def annual_report_view(user_id):
    year = request.args.get("year", datetime.now().year - 1, type=int)

    db = get_db()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return redirect(url_for("onboarding"))

        bv = db.query(BV).filter_by(user_id=user_id).first()
        report = None

        if bv:
            report = db.query(AnnualReport).filter_by(bv_id=bv.id, year=year).first()

        return render_template(
            "annual_report.html",
            user=user,
            bv=bv,
            report=report,
            year=year,
        )
    finally:
        db.close()


@app.route("/api/generate-report", methods=["POST"])
def generate_report():
    user_id = request.form.get("user_id", type=int)
    year = request.form.get("year", type=int)

    db = get_db()
    try:
        bv = db.query(BV).filter_by(user_id=user_id).first()
        if not bv:
            return jsonify({"error": "Geen BV gevonden"}), 404

        from services.annual_report import generate_annual_report
        report = generate_annual_report(db, bv.id, year)

        return redirect(url_for("annual_report_view", user_id=user_id, year=year))
    finally:
        db.close()


# ─── VPB view ─────────────────────────────────────────────────────────────

@app.route("/vpb/<int:user_id>")
def vpb_view(user_id):
    year = request.args.get("year", datetime.now().year - 1, type=int)

    db = get_db()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return redirect(url_for("onboarding"))

        bv = db.query(BV).filter_by(user_id=user_id).first()
        filing = None
        breakdown = None

        if bv:
            filing = db.query(VPBFiling).filter_by(bv_id=bv.id, year=year).first()
            if filing:
                from services.vpb import vpb_breakdown
                breakdown = vpb_breakdown(filing.taxable_profit)

        return render_template(
            "vpb.html",
            user=user,
            bv=bv,
            filing=filing,
            breakdown=breakdown,
            year=year,
        )
    finally:
        db.close()


@app.route("/api/calculate-vpb", methods=["POST"])
def calculate_vpb_route():
    user_id = request.form.get("user_id", type=int)
    year = request.form.get("year", type=int)

    db = get_db()
    try:
        bv = db.query(BV).filter_by(user_id=user_id).first()
        if not bv:
            return jsonify({"error": "Geen BV gevonden"}), 404

        # Generate report first (which also creates VPB filing)
        from services.annual_report import generate_annual_report
        generate_annual_report(db, bv.id, year)

        return redirect(url_for("vpb_view", user_id=user_id, year=year))
    finally:
        db.close()


# ─── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("BoxShift running on http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)
