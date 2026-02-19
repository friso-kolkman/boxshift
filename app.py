"""BoxShift Flask application — beleggings-BV automation platform."""

import os
import functools
from datetime import datetime
import requests as http_requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, session
from sqlalchemy import create_engine, extract
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


# ─── Auth helpers ─────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user(db):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


# ─── GitHub OAuth ─────────────────────────────────────────────────────────

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


@app.route("/login")
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    # If no GitHub OAuth configured, show setup instructions
    if not config.GITHUB_CLIENT_ID:
        return render_template("login.html", no_oauth=True)

    return render_template("login.html", no_oauth=False)


@app.route("/auth/github")
def github_login():
    """Redirect to GitHub OAuth."""
    if not config.GITHUB_CLIENT_ID:
        return redirect(url_for("login"))

    redirect_uri = config.APP_URL + "/auth/github/callback"
    url = f"{GITHUB_AUTHORIZE_URL}?client_id={config.GITHUB_CLIENT_ID}&redirect_uri={redirect_uri}&scope=user:email"
    return redirect(url)


@app.route("/auth/github/callback")
def github_callback():
    """Handle GitHub OAuth callback."""
    if not config.GITHUB_CLIENT_ID:
        return redirect(url_for("login"))

    code = request.args.get("code")
    if not code:
        return redirect(url_for("login"))

    # Exchange code for token
    token_resp = http_requests.post(
        GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data={
            "client_id": config.GITHUB_CLIENT_ID,
            "client_secret": config.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": config.APP_URL + "/auth/github/callback",
        },
    )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return render_template("login.html", error="GitHub login mislukt. Probeer opnieuw.")

    # Get user info from GitHub
    resp = http_requests.get(
        GITHUB_API_URL + "/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    gh_user = resp.json()

    github_username = gh_user.get("login", "")
    github_id = gh_user.get("id")
    name = gh_user.get("name") or github_username
    email = gh_user.get("email") or f"{github_username}@github.com"
    avatar_url = gh_user.get("avatar_url", "")

    # Check if user is allowed
    if config.ALLOWED_GITHUB_USERS and github_username not in config.ALLOWED_GITHUB_USERS:
        return render_template("login.html", error=f"@{github_username} heeft geen toegang. Neem contact op met de beheerder.")

    db = get_db()
    try:
        # Find or create user
        user = db.query(User).filter_by(github_id=github_id).first()
        if not user:
            # Check by email
            user = db.query(User).filter_by(email=email).first()
            if user:
                user.github_id = github_id
                user.github_username = github_username
                user.avatar_url = avatar_url
            else:
                user = User(
                    email=email,
                    name=name,
                    github_id=github_id,
                    github_username=github_username,
                    avatar_url=avatar_url,
                )
                db.add(user)
                db.flush()
        else:
            # Update avatar
            user.avatar_url = avatar_url

        db.commit()

        # Set session
        session["user_id"] = user.id
        session["github_username"] = github_username
        session["avatar_url"] = avatar_url

        # Redirect: if not onboarded, go to onboarding
        if not user.onboarded:
            return redirect(url_for("onboarding"))

        return redirect(url_for("dashboard"))
    finally:
        db.close()


@app.route("/auth/demo")
def demo_login():
    """Quick demo login."""
    if not app.debug and not config.ALLOW_DEMO_LOGIN:
        return redirect(url_for("login"))

    db = get_db()
    try:
        user = db.query(User).filter_by(email="demo@boxshift.nl").first()
        if user:
            session["user_id"] = user.id
            session["github_username"] = "demo"
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))
    finally:
        db.close()


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


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
@login_required
def admin_leads():
    db = get_db()
    try:
        user = get_current_user(db)
        leads = db.query(Lead).order_by(Lead.created_at.desc()).all()
        return render_template("admin_leads.html", leads=leads, user=user)
    finally:
        db.close()


# ─── Onboarding ──────────────────────────────────────────────────────────

@app.route("/onboarding")
@login_required
def onboarding():
    db = get_db()
    try:
        user = get_current_user(db)
        return render_template("onboarding.html", user=user)
    finally:
        db.close()


@app.route("/api/onboard", methods=["POST"])
@login_required
def api_onboard():
    data = request.form
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return redirect(url_for("login"))

        user.name = data.get("name", user.name).strip()
        user.phone = data.get("phone", "").strip() or None
        user.vermogen_estimate = int(data.get("vermogen_estimate", 0) or 0)
        user.broker = data.get("broker", "degiro")
        user.situation = data.get("situation", "particulier")
        user.onboarded = True

        # Create BV if none exists
        bv = db.query(BV).filter_by(user_id=user.id).first()
        if not bv:
            bv_name = f"{user.name.split()[0]} Beleggingen B.V." if user.name else "Mijn Beleggingen B.V."
            bv = BV(user_id=user.id, name=bv_name)
            db.add(bv)

        # Convert lead if exists
        lead = db.query(Lead).filter_by(email=user.email).first()
        if lead:
            lead.status = "converted"

        db.commit()
        return redirect(url_for("dashboard"))
    finally:
        db.close()


# ─── Dashboard ───────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return redirect(url_for("login"))

        bv = db.query(BV).filter_by(user_id=user.id).first()
        holdings = []
        total_cost = 0
        tx_count = 0
        ytd_pl = 0

        if bv:
            holdings = db.query(Holding).filter_by(bv_id=bv.id).all()
            total_cost = sum(h.total_cost for h in holdings)
            tx_count = db.query(Transaction).filter_by(bv_id=bv.id).count()

            current_year = datetime.now().year
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
@login_required
def import_csv():
    broker_type = request.form.get("broker", "degiro")
    file = request.files.get("csv_file")

    if not file:
        return jsonify({"error": "Bestand vereist"}), 400

    db = get_db()
    try:
        user = get_current_user(db)
        bv = db.query(BV).filter_by(user_id=user.id).first()
        if not bv:
            return jsonify({"error": "Geen BV gevonden"}), 404

        content = file.read().decode("utf-8-sig")

        from services.broker_import import parse_degiro_csv, parse_ib_csv
        if broker_type == "ib":
            parsed = parse_ib_csv(content)
        else:
            parsed = parse_degiro_csv(content)

        from services.ai_classifier import classify_transactions
        parsed = classify_transactions(parsed)

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

        db.commit()

        from services.transaction_engine import process_transactions
        process_transactions(db, bv.id)

        return redirect(url_for("dashboard"))
    finally:
        db.close()


# ─── Transactions view ───────────────────────────────────────────────────

@app.route("/transactions")
@login_required
def transactions_view():
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return redirect(url_for("login"))

        bv = db.query(BV).filter_by(user_id=user.id).first()
        txs = []
        filter_type = request.args.get("type", "")
        filter_year = request.args.get("year", "")

        if bv:
            query = db.query(Transaction).filter_by(bv_id=bv.id)
            if filter_type:
                query = query.filter_by(type=filter_type)
            if filter_year:
                query = query.filter(extract("year", Transaction.date) == int(filter_year))
            txs = query.order_by(Transaction.date.desc()).all()

        years = []
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

@app.route("/annual-report")
@login_required
def annual_report_view():
    year = request.args.get("year", datetime.now().year - 1, type=int)

    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return redirect(url_for("login"))

        bv = db.query(BV).filter_by(user_id=user.id).first()
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
@login_required
def generate_report():
    year = request.form.get("year", type=int)

    db = get_db()
    try:
        user = get_current_user(db)
        bv = db.query(BV).filter_by(user_id=user.id).first()
        if not bv:
            return jsonify({"error": "Geen BV gevonden"}), 404

        from services.annual_report import generate_annual_report
        generate_annual_report(db, bv.id, year)

        return redirect(url_for("annual_report_view", year=year))
    finally:
        db.close()


# ─── VPB view ─────────────────────────────────────────────────────────────

@app.route("/vpb")
@login_required
def vpb_view():
    year = request.args.get("year", datetime.now().year - 1, type=int)

    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return redirect(url_for("login"))

        bv = db.query(BV).filter_by(user_id=user.id).first()
        filing = None
        breakdown = None
        aangifte = None

        if bv:
            filing = db.query(VPBFiling).filter_by(bv_id=bv.id, year=year).first()
            if filing:
                from services.vpb import vpb_breakdown, generate_vpb_aangifte
                breakdown = vpb_breakdown(filing.taxable_profit)
                aangifte = generate_vpb_aangifte(db, bv.id, year)

        return render_template(
            "vpb.html",
            user=user,
            bv=bv,
            filing=filing,
            breakdown=breakdown,
            aangifte=aangifte,
            year=year,
            now=datetime.now(),
        )
    finally:
        db.close()


@app.route("/api/calculate-vpb", methods=["POST"])
@login_required
def calculate_vpb_route():
    year = request.form.get("year", type=int)

    db = get_db()
    try:
        user = get_current_user(db)
        bv = db.query(BV).filter_by(user_id=user.id).first()
        if not bv:
            return jsonify({"error": "Geen BV gevonden"}), 404

        from services.annual_report import generate_annual_report
        generate_annual_report(db, bv.id, year)

        return redirect(url_for("vpb_view", year=year))
    finally:
        db.close()


# ─── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("BoxShift running on http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)
