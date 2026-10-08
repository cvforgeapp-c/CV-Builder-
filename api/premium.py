import os
import sys
import uuid
import json
import hmac
import hashlib
import httpx
import openai
from datetime import datetime
from bs4 import BeautifulSoup

from flask import Flask, request, jsonify, redirect, url_for, render_template, Blueprint, flash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# Handle Path Imports for Vercel
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import shared DB instance and models
from models import db, User, Resume, JobApplication

# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")

premium_app = Flask(__name__, template_folder=TEMPLATE_DIR)

premium_app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "cvforge-premium-key-998877")
premium_app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///:memory:")
premium_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Bind SQLAlchemy to application
db.init_app(premium_app)

login_manager = LoginManager(premium_app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access your account settings."
login_manager.login_message_category = "info"

# ============================================================
# PADDLE CONFIGURATION
# ============================================================

PADDLE_API_KEY = os.getenv("PADDLE_API_KEY")
PADDLE_WEBHOOK_SECRET_KEY = os.getenv("PADDLE_WEBHOOK_SECRET_KEY")
PADDLE_ENV = os.getenv("PADDLE_ENV", "sandbox")
PADDLE_PREMIUM_PRICE_ID = os.getenv("PADDLE_PREMIUM_PRICE_ID", "pri_01hxxxxxxxxx")

# ============================================================
# LOGIN MANAGER USER LOADER
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    return db.session.get(User, user_id)

# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please log in.", "error")
            return redirect(url_for("auth.register"))

        try:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=generate_password_hash(password),
                is_premium=False,
                subscription_status="free",
                monthly_cv_generations=0,
                ai_credits_remaining=3
            )

            db.session.add(user)
            db.session.commit()

            login_user(user)
            return redirect("/dashboard")

        except Exception as e:
            db.session.rollback()
            print(f"Registration DB Error: {str(e)}")
            flash("Registration failed due to a server error. Please try again.", "error")
            return redirect(url_for("auth.register"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect("/dashboard")

        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        if email:
            flash("If an account exists for that email, password recovery instructions have been sent.", "info")
            return redirect(url_for("auth.forgot_password"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


premium_app.register_blueprint(auth_bp)

# ============================================================
# PUBLIC ROOT & SETTINGS ROUTES
# ============================================================

@premium_app.route("/")
def landing():
    try:
        return render_template("landing.html")
    except Exception:
        return render_template("index.html")


@premium_app.route("/settings")
def public_settings():
    if current_user and getattr(current_user, "is_authenticated", False):
        return redirect(url_for("dashboard.account"))
    try:
        return render_template("settings.html", user=None)
    except Exception:
        return render_template("dashboard/account.html", user=None)

# ============================================================
# DASHBOARD ROUTES
# ============================================================

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@dashboard_bp.route("")
@login_required
def home():
    user_resumes = Resume.query.filter_by(user_id=current_user.id).all() if current_user and hasattr(current_user, "id") else []
    return render_template("dashboard/index.html", resumes=user_resumes, user=current_user)


@dashboard_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        new_email = request.form.get("email")
        new_password = request.form.get("password")

        if new_email and new_email != getattr(current_user, "email", None):
            existing_user = User.query.filter_by(email=new_email).first()
            if existing_user:
                flash("This email is already in use.", "error")
            else:
                current_user.email = new_email
                flash("Email updated successfully.", "success")

        if new_password:
            current_user.password_hash = generate_password_hash(new_password)
            flash("Password updated successfully.", "success")

        db.session.commit()
        return redirect(url_for("dashboard.account"))

    try:
        return render_template("settings.html", user=current_user)
    except Exception:
        return render_template("dashboard/account.html", user=current_user)


premium_app.register_blueprint(dashboard_bp)

# ============================================================
# PADDLE WEBHOOK VERIFICATION
# ============================================================

def verify_paddle_webhook(request_data, signature_header):
    if not PADDLE_WEBHOOK_SECRET_KEY or not signature_header or not isinstance(signature_header, str):
        return False

    try:
        components = {}
        items = signature_header.split(";")
        for item in items:
            item = item.strip()
            if "=" in item:
                parts = item.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if key and val:
                        components[key] = val

        ts = components.get("ts")
        h1 = components.get("h1")

        if not ts or not h1:
            return False

        decoded_body = request_data.decode("utf-8") if isinstance(request_data, bytes) else str(request_data)
        signed_payload = f"{ts}:{decoded_body}"

        digest = hmac.new(
            PADDLE_WEBHOOK_SECRET_KEY.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(digest, h1)

    except Exception as e:
        print(f"Paddle HMAC Verification Error: {e}")
        return False

# ============================================================
# PREMIUM API BLUEPRINT
# ============================================================

premium_bp = Blueprint("premium_api", __name__, url_prefix="/api/v1/premium")

@premium_bp.route("/user-status", methods=["GET"])
@login_required
def get_user_status():
    return jsonify({
        "user_id": getattr(current_user, "id", None),
        "email": getattr(current_user, "email", None),
        "is_premium": getattr(current_user, "is_premium", False),
        "subscription_status": getattr(current_user, "subscription_status", "free"),
        "paddle_price_id": PADDLE_PREMIUM_PRICE_ID
    })


@premium_bp.route("/webhook/paddle", methods=["POST"])
def paddle_webhook():
    signature = request.headers.get("Paddle-Signature")
    payload = request.get_data()

    if not verify_paddle_webhook(payload, signature):
        return jsonify({"error": "Invalid signature"}), 400

    data = request.get_json(silent=True) or {}
    event_type = data.get("event_type")
    event_data = data.get("data", {})
    if not isinstance(event_data, dict):
        event_data = {}

    if event_type in ["subscription.created", "subscription.activated"]:
        custom_data = event_data.get("custom_data", {})
        if not isinstance(custom_data, dict):
            custom_data = {}

        user_id = custom_data.get("user_id")
        user = None

        if user_id:
            user = db.session.get(User, user_id)
        else:
            customer_id = event_data.get("customer_id")
            if customer_id:
                user = User.query.filter_by(paddle_customer_id=customer_id).first()

        if user:
            user.is_premium = True
            user.subscription_status = event_data.get("status", "active")
            user.paddle_customer_id = event_data.get("customer_id")
            user.paddle_subscription_id = event_data.get("id")
            db.session.commit()

    elif event_type in ["subscription.canceled", "subscription.past_due"]:
        sub_id = event_data.get("id")
        if sub_id:
            user = User.query.filter_by(paddle_subscription_id=sub_id).first()
            if user:
                user.is_premium = False
                user.subscription_status = event_data.get("status", "canceled")
                db.session.commit()

    return jsonify({"status": "success"}), 200


@premium_bp.route("/analyze-ats", methods=["POST"])
@login_required
def analyze_ats():
    if not getattr(current_user, "is_premium", False):
        return jsonify({"error": "Premium subscription required"}), 403

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}

    cv_data = data.get("cv_data")
    job_desc = data.get("job_description")

    if not cv_data or not job_desc:
        return jsonify({"error": "CV data and job description are required."}), 400

    prompt = f"Provide an ATS Score from 0-100 and list missing keywords.\n\nCV:\n{json.dumps(cv_data)}\n\nJob Description:\n{job_desc}"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )

        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message and hasattr(message, "content"):
                analysis_text = message.content
            elif isinstance(first_choice, dict) and "message" in first_choice:
                analysis_text = first_choice["message"].get("content", "No content returned.")
            else:
                analysis_text = "Analysis completed, but response structure was unrecognized."
        else:
            analysis_text = "No response generated by OpenAI."

        return jsonify({"analysis": analysis_text})

    except Exception as e:
        print(f"ATS analysis error: {e}")
        return jsonify({"error": "Unable to analyze CV at this time."}), 500


premium_app.register_blueprint(premium_bp)

# Vercel Entrypoint
app = premium_app

if __name__ == "__main__":
    with premium_app.app_context():
        db.create_all()
    premium_app.run(debug=True, port=5001)
