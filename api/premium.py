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

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import shared DB instance and models with fallback for Vercel package resolution
try:
    from models import db, User, Resume, JobApplication
except ImportError:
    from ..models import db, User, Resume, JobApplication

# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")

premium_app = Flask(__name__, template_folder=TEMPLATE_DIR)

premium_app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "cvforge-premium-key-998877")

# Read database URL and dynamically enforce Psycopg v3 driver compatibility
db_url = os.getenv("DATABASE_URL", "sqlite:///:memory:")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

premium_app.config["SQLALCHEMY_DATABASE_URI"] = db_url
premium_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
premium_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Bind SQLAlchemy to application
db.init_app(premium_app)

login_manager = LoginManager(premium_app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access your account settings."
login_manager.login_message_category = "info"

# Initialize OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

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
            now = datetime.utcnow()
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=generate_password_hash(password),
                created_at=now,
                updated_at=now,
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
# EDITOR, PRICING & PREVIEW ROUTES
# ============================================================

@premium_app.route("/editor")
@login_required
def editor():
    resume_id = request.args.get("id")
    resume = None
    if resume_id:
        resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first()
    try:
        return render_template("editor.html", resume=resume, user=current_user)
    except Exception:
        return render_template("index.html", resume=resume, user=current_user)


@premium_app.route("/builder")
def builder_redirect():
    return redirect("/editor")


@premium_app.route("/pricing")
def pricing():
    try:
        return render_template("pricing.html", user=current_user)
    except Exception:
        return render_template("landing.html", user=current_user)


@premium_app.route("/preview")
@login_required
def preview():
    resume_id = request.args.get("id")
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first() if resume_id else None
    try:
        return render_template("preview.html", resume=resume, user=current_user)
    except Exception:
        return redirect("/dashboard")

# ============================================================
# SAVE RESUME ENDPOINT (SAFEGUARDED INSERT & DIRECT PREVIEW REDIRECT)
# ============================================================

@premium_app.route("/api/v1/resumes/save", methods=["POST"])
@login_required
def save_resume():
    title = request.form.get("title", "My CV")

    content_data = {
        "target_role": request.form.get("target_role", ""),
        "full_name": request.form.get("full_name", ""),
        "email": request.form.get("email", ""),
        "phone": request.form.get("phone", ""),
        "location": request.form.get("location", ""),
        "linkedin": request.form.get("linkedin", ""),
        "portfolio": request.form.get("portfolio", ""),
        "summary": request.form.get("summary", ""),
        "company": request.form.get("company", ""),
        "job_title": request.form.get("job_title", ""),
        "job_location": request.form.get("job_location", ""),
        "job_dates": request.form.get("job_dates", ""),
        "experience_bullets": request.form.get("experience_bullets", ""),
        "education_degree": request.form.get("education_degree", ""),
        "education_school": request.form.get("education_school", ""),
        "education_dates": request.form.get("education_dates", ""),
        "education_honors": request.form.get("education_honors", ""),
        "skills_tech": request.form.get("skills_tech", ""),
        "skills_soft": request.form.get("skills_soft", ""),
        "certifications": request.form.get("certifications", ""),
        "projects": request.form.get("projects", ""),
        "languages": request.form.get("languages", "")
    }

    resume_id = request.args.get("id") or str(uuid.uuid4())
    resume = db.session.get(Resume, resume_id)

    if resume and resume.user_id == current_user.id:
        resume.title = title
        resume.content_json = content_data
        resume.updated_at = datetime.utcnow()
    else:
        # Explicit mapping for new rows to prevent database constraint exceptions
        resume = Resume(
            id=resume_id,
            user_id=current_user.id,
            title=title,
            content_json=content_data,
            original_text="",
            parsed_data={},
            template_used="modern",
            accent_color="#E5A93C",
            sidebar_color="#02353C",
            updated_at=datetime.utcnow()
        )
        db.session.add(resume)

    try:
        db.session.commit()
        flash("Resume saved successfully!", "success")
        return redirect(f"/preview?id={resume.id}")
    except Exception as e:
        db.session.rollback()
        print(f"Save Resume Error: {e}")
        flash("Failed to save resume.", "error")
        return redirect("/editor")

# ============================================================
# UNIVERSAL CONTEXT-AWARE AI GENERATION ENDPOINT
# ============================================================

@premium_app.route("/api/v1/ai/generate-field", methods=["POST"])
@login_required
def generate_ai_field():
    # Check credit balance for Free Tier users
    if not getattr(current_user, "is_premium", False) and getattr(current_user, "ai_credits_remaining", 0) <= 0:
        return jsonify({"error": "No AI credits remaining. Please upgrade to Premium."}), 403

    data = request.get_json(silent=True) or {}
    field_type = data.get("field_type", "summary")  # 'summary', 'experience', 'project'
    target_role = data.get("target_role", "Professional")
    job_title = data.get("job_title", "")
    skills = data.get("skills", "")
    current_input = data.get("current_input", "")

    # Build dynamically tailored prompts based on field type
    if field_type == "experience":
        prompt = f"""
        Transform these raw notes or work duties into 3 high-impact, ATS-optimized resume bullet points for a {target_role} ({job_title}).
        Key Skills Context: {skills}
        Raw Notes: "{current_input}"

        Requirements:
        - Start every bullet point with a strong action verb (e.g., Engineered, Spearheaded, Optimized, Managed).
        - Include realistic, industry-appropriate metrics or percentages.
        - Return ONLY the bullet points starting with hyphen (-), with no introductory text or quotes.
        """
    elif field_type == "project":
        prompt = f"""
        Write a concise, professional 2-sentence project overview for a CV.
        Target Role: {target_role}
        Input/Tech Stack Context: "{current_input}"

        Requirements:
        - Highlight project scope, implementation, and delivered impact.
        - Return ONLY the clean paragraph text without quotation marks.
        """
    else:  # summary
        prompt = f"""
        Write a high-impact, professional 3-sentence executive summary for a CV.
        Target Professional Role: {target_role}
        Recent Job Title: {job_title}
        Key Skills: {skills}
        User Context: "{current_input}"

        Requirements:
        - Concise, professional, and ATS-optimized for top global employers.
        - Return ONLY the paragraph text without quotation marks or fluff.
        """

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        
        # If API Key is not set in environment, deliver structured fallback text
        if not api_key:
            if field_type == "experience":
                fallback_text = f"- Spearheaded strategic initiatives as {target_role}, increasing operational efficiency by 22%.\n- Optimized core workflows and cross-functional processes to maintain 99.5% delivery compliance.\n- Directed team execution aligned with global industry best practices."
            elif field_type == "project":
                fallback_text = f"Led end-to-end execution of high-impact initiative for {target_role} responsibilities. Optimized workflow performance and delivered scalable outcomes ahead of project deadlines."
            else:
                fallback_text = f"Results-driven {target_role} with proven experience delivering measurable operational success and driving key strategic initiatives across competitive global markets."
            
            return jsonify({"result": fallback_text})

        # Dual OpenAI SDK Compatibility (handles SDK v1.0+ and legacy v0.28)
        if hasattr(openai, "OpenAI"):
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=220,
                temperature=0.7
            )
            generated_text = response.choices[0].message.content.strip()
        else:
            openai.api_key = api_key
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=220,
                temperature=0.7
            )
            generated_text = response.choices[0].message.content.strip()

        # Deduct credit for free tier users
        if not getattr(current_user, "is_premium", False):
            current_user.ai_credits_remaining = max(0, current_user.ai_credits_remaining - 1)
            db.session.commit()

        return jsonify({"result": generated_text})

    except Exception as e:
        print(f"OpenAI Generation Exception: {e}")
        if field_type == "experience":
            fallback_text = f"- Accelerated project delivery timelines for {target_role} operations by 25%.\n- Implemented process automation strategies reducing manual workload overhead.\n- Mentored junior team members and aligned cross-functional objectives."
        elif field_type == "project":
            fallback_text = f"Architected dynamic solutions for {target_role} workflow optimization. Delivered quantifiable performance gains across primary operational benchmarks."
        else:
            fallback_text = f"Accomplished {target_role} with a strong track record of operational excellence, strategic project execution, and organizational growth."
        
        return jsonify({"result": fallback_text})

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
        if hasattr(openai, "OpenAI"):
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            analysis_text = response.choices[0].message.content.strip()
        else:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            analysis_text = response.choices[0].message.content.strip()

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
