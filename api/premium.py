import os
import sys
import uuid
import json
import hmac
import hashlib
import httpx

from datetime import datetime
from bs4 import BeautifulSoup

# ============================================================
# GOOGLE GENAI SDK: MODERN SDK WITH LEGACY FALLBACK
# ============================================================

try:
    from google import genai as new_genai
except ImportError:
    new_genai = None

try:
    import google.generativeai as legacy_genai
except ImportError:
    legacy_genai = None

# ============================================================
# FLASK IMPORTS
# ============================================================

from flask import (
    Flask,
    request,
    jsonify,
    redirect,
    url_for,
    render_template,
    Blueprint,
    flash,
)

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

# ============================================================
# PATH CONFIGURATION FOR VERCEL
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# DATABASE MODELS
# ============================================================

try:
    from models import db, User, Resume, JobApplication
except ImportError:
    from ..models import db, User, Resume, JobApplication

# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")

premium_app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
)

premium_app.config["SECRET_KEY"] = (
    os.getenv("SECRET_KEY")
    or os.getenv("secret_key")
    or "cvforge-premium-key-998877"
)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

db_url = (
    os.getenv("DATABASE_URL")
    or os.getenv("database_url")
    or "sqlite:///:memory:"
)

if db_url.startswith("postgres://"):
    db_url = db_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1,
    )

elif (
    db_url.startswith("postgresql://")
    and not db_url.startswith("postgresql+psycopg://")
):
    db_url = db_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

premium_app.config["SQLALCHEMY_DATABASE_URI"] = db_url
premium_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

premium_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db.init_app(premium_app)

# ============================================================
# LOGIN MANAGER
# ============================================================

login_manager = LoginManager(premium_app)

login_manager.login_view = "auth.login"
login_manager.login_message = (
    "Please log in to access your account settings."
)
login_manager.login_message_category = "info"

# ============================================================
# AI API CONFIGURATION
# ============================================================

def get_gemini_api_key():
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("gemini_api_key")
    )


gemini_api_key = get_gemini_api_key()

if gemini_api_key and legacy_genai:
    try:
        legacy_genai.configure(api_key=gemini_api_key)
    except Exception as exc:
        print(f"Gemini legacy configuration warning: {exc}")


# ============================================================
# SHARED AI GENERATION HELPERS (GEMINI EXCLUSIVE)
# ============================================================

AI_SYSTEM_INSTRUCTIONS = """
You are CVForge AI, a professional resume-writing assistant.

FACTUAL ACCURACY RULES:

1. Use only facts supplied in the user's provided information.
2. Never invent employment history, employers, job titles, dates,
   degrees, certifications, licenses, skills, projects, or achievements.
3. Never invent percentages, revenue figures, patient outcomes,
   performance improvements, or other numerical metrics.
4. Do not claim that a candidate performed a responsibility unless
   the supplied information supports that claim.
5. Do not treat a target job title or job description as proof that
   the candidate possesses the required qualifications.
6. You may improve grammar, clarity, structure, and professional tone.
7. If information is insufficient, request more details or state
   that there is insufficient information to generate the requested
   content accurately.
8. Never insert placeholder text or fabricated examples into a
   resume intended for the user.
9. Follow the requested output format.
"""


def generate_with_gemini(prompt, api_key=None):
    api_key = api_key or get_gemini_api_key()

    if not api_key:
        raise RuntimeError("Gemini API key is not configured.")

    full_prompt = (
        AI_SYSTEM_INSTRUCTIONS
        + "\n\nUser request:\n"
        + prompt
    )

    # 1. Modern Google GenAI SDK (google.genai)
    if new_genai:
        try:
            client = new_genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=full_prompt,
            )

            generated_text = getattr(response, "text", None)
            if generated_text and generated_text.strip():
                return generated_text.strip()
        except Exception as exc:
            print(f"Modern GenAI SDK failed: {exc}. Trying legacy SDK...")

    # 2. Legacy Google Generative AI SDK (google.generativeai)
    if legacy_genai:
        legacy_genai.configure(api_key=api_key)

        model = legacy_genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(
            full_prompt,
            request_options={"timeout": 30},
        )

        generated_text = getattr(response, "text", None)

        if generated_text and generated_text.strip():
            return generated_text.strip()

        raise RuntimeError("Legacy Gemini returned an empty response.")

    raise RuntimeError("Neither modern nor legacy Gemini SDK produced a result.")


def generate_ai_text(prompt):
    """
    Generate text exclusively using Google Gemini to avoid OpenAI limits.
    """
    gemini_key = get_gemini_api_key()

    if not gemini_key:
        raise RuntimeError("Gemini API key is not configured in environment variables.")

    try:
        result = generate_with_gemini(prompt, gemini_key)
        print("SUCCESS: Generated using Gemini.")
        return result
    except Exception as exc:
        print(f"GEMINI FAILED: {type(exc).__name__}: {exc}")
        raise RuntimeError(f"Gemini generation failed: {type(exc).__name__}: {exc}")


# ============================================================
# PADDLE CONFIGURATION
# ============================================================

PADDLE_API_KEY = (
    os.getenv("PADDLE_API_KEY")
    or os.getenv("paddle_api_key")
)

PADDLE_WEBHOOK_SECRET_KEY = (
    os.getenv("PADDLE_WEBHOOK_SECRET_KEY")
    or os.getenv("paddle_webhook_secret_key")
)

PADDLE_ENV = os.getenv("PADDLE_ENV", "sandbox")
PADDLE_PREMIUM_PRICE_ID = os.getenv("PADDLE_PREMIUM_PRICE_ID", "pri_01hxxxxxxxxx")

domain_fallbacks = {
    "healthcare": "Pediatric Care, Neonatal Intensive Care (NICU), Clinical Pharmacology, WHO Growth Standards, Patient Diagnostics, Emergency Triage, Biostatistics, Medical Research, Patient Advocacy, Cross-Functional Leadership",
    "tech": "Python, Flask, Next.js, React, TypeScript, PostgreSQL, REST APIs, Docker, Vercel Serverless, Tailwind CSS, System Architecture, Agile Methodologies",
    "finance": "Financial Modeling, Risk Assessment, Quantitative Analysis, Portfolio Management, Budgeting & Forecasting, Regulatory Compliance, Financial Reporting, Valuation, Excel (VBA)",
    "marketing": "Search Engine Optimization (SEO), Content Strategy, Digital Advertising (Meta/Google Ads), Marketing Automation, Brand Positioning, Social Media Analytics, Conversion Rate Optimization, Market Research",
    "sales": "B2B Sales, CRM Management, Lead Generation, Account Management, Consultative Selling, Pipeline Management, Contract Negotiation, Revenue Forecasting",
    "product": "Product Lifecycle Management, User Stories & Roadmapping, A/B Testing, Feature Prioritization, Customer Discovery, Agile/Scrum, Product Analytics, Competitive Analysis",
    "hr": "Talent Acquisition, Employee Relations, HRIS, Performance Management, Compensation & Benefits, Onboarding Strategy, Labor Compliance, Organizational Development",
    "general": "Strategic Planning, Process Optimization, Project Management, Data Analysis, Stakeholder Engagement, Quality Assurance, Workflow Automation",
}

# ============================================================
# LOGIN MANAGER USER LOADER
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None

    try:
        return db.session.get(User, user_id)
    except Exception as exc:
        print(f"User loader error: {exc}")
        return None


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
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
                ai_credits_remaining=3,
            )

            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect("/dashboard")

        except Exception as exc:
            db.session.rollback()
            print(f"Registration DB Error: {exc}")
            flash("Registration failed due to a server error. Please try again.", "error")
            return redirect(url_for("auth.register"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()

        if user and user.password_hash and check_password_hash(user.password_hash, password):
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
# SAVE RESUME ENDPOINT
# ============================================================

@premium_app.route("/api/v1/resumes/save", methods=["POST"])
@login_required
def save_resume():
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid resume data."}), 400

    title = (data.get("title") or "My CV").strip() or "My CV"

    content_data = {
        "target_role": data.get("target_role", ""),
        "full_name": data.get("full_name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "location": data.get("location", ""),
        "linkedin": data.get("linkedin", ""),
        "portfolio": data.get("portfolio", ""),
        "summary": data.get("summary", ""),
        "company": data.get("company", ""),
        "job_title": data.get("job_title", ""),
        "job_location": data.get("job_location", ""),
        "job_dates": data.get("job_dates", ""),
        "experience_bullets": data.get("experience_bullets", ""),
        "education_degree": data.get("education_degree", ""),
        "education_school": data.get("education_school", ""),
        "education_dates": data.get("education_dates", ""),
        "education_honors": data.get("education_honors", ""),
        "skills_tech": data.get("skills_tech", ""),
        "skills_soft": data.get("skills_soft", ""),
        "certifications": data.get("certifications", ""),
        "projects": data.get("projects", ""),
        "languages": data.get("languages", ""),
    }

    resume_id = request.args.get("id") or data.get("id") or str(uuid.uuid4())
    resume = db.session.get(Resume, resume_id)

    if resume and str(resume.user_id) == str(current_user.id):
        resume.title = title
        resume.content_json = content_data
        resume.template_used = "ats"
        resume.updated_at = datetime.utcnow()
    else:
        if resume:
            return jsonify({"error": "You do not have permission to update this resume."}), 403

        resume = Resume(
            id=resume_id,
            user_id=current_user.id,
            title=title,
            content_json=content_data,
            optimized_json={},
            original_text="",
            template_used="ats",
            accent_color="#000000",
            sidebar_color="#000000",
            updated_at=datetime.utcnow(),
        )
        db.session.add(resume)

    try:
        db.session.commit()
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "status": "success",
                "redirect_url": f"/preview?id={resume.id}",
                "resume_id": resume.id,
            }), 200

        flash("Resume saved successfully!", "success")
        return redirect(f"/preview?id={resume.id}")

    except Exception as exc:
        db.session.rollback()
        print(f"Save Resume Error: {exc}")
        if request.is_json:
            return jsonify({"error": "Failed to save resume."}), 500

        flash("Failed to save resume.", "error")
        return redirect(f"/editor?id={resume_id}")


# ============================================================
# AI FIELD GENERATION ENDPOINT
# ============================================================

DEVELOPER_EMAILS = ["subhnllha@gmail.com"]


@premium_app.route("/api/v1/ai/generate-field", methods=["POST"])
@login_required
def generate_ai_field():
    user_email = (getattr(current_user, "email", "") or "").lower().strip()
    is_developer = user_email in DEVELOPER_EMAILS
    is_premium_user = bool(getattr(current_user, "is_premium", False)) or is_developer
    credits_remaining = int(getattr(current_user, "ai_credits_remaining", 0) or 0)

    if not is_premium_user and credits_remaining <= 0:
        return jsonify({"error": "No AI credits remaining. Please upgrade to Premium."}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON request is required."}), 400

    field_type = (data.get("field_type") or "summary").strip().lower()
    supported_fields = {"summary", "experience", "project", "skills"}

    if field_type not in supported_fields:
        return jsonify({
            "error": "Unsupported field type.",
            "supported_fields": sorted(supported_fields),
        }), 400

    target_role = (data.get("target_role") or "").strip()
    job_title = (data.get("job_title") or "").strip()
    full_name = (data.get("full_name") or "").strip()
    skills = (data.get("skills") or "").strip()
    current_input = (data.get("current_input") or "").strip()
    source_cv = (data.get("source_cv") or "").strip()
    job_description = (data.get("job_description") or "").strip()

    has_candidate_content = any([full_name, skills, current_input, source_cv])
    if not has_candidate_content:
        return jsonify({
            "error": "Please provide your CV information, existing draft, or skills before generating this field.",
        }), 400

    context_details = []
    if full_name: context_details.append(f"Candidate name supplied by user: {full_name}")
    if target_role: context_details.append(f"Target role: {target_role}")
    if job_title: context_details.append(f"Job title supplied by user: {job_title}")
    if skills: context_details.append(f"Skills explicitly supplied by user: {skills}")
    if current_input: context_details.append(f"Existing user draft or notes:\n{current_input}")
    if source_cv: context_details.append(f"Extracted source CV content:\n{source_cv}")
    if job_description: context_details.append(f"Target job description:\n{job_description}")

    context_str = "\n\n".join(context_details)

    if field_type == "summary":
        prompt = f"""Write a concise, professional resume summary using only the candidate information supplied below.\n\nCandidate information:\n{context_str}\n\nRequirements:\n- Use only facts supported by the supplied candidate information.\n- Do not assume the candidate has held the target role.\n- Do not invent years of experience, qualifications, or achievements.\n- Use the target job description only to understand relevance.\n- Do not claim the candidate has a skill unless the source supports it.\n- If the supplied information is insufficient for a reliable summary, explain what additional information is needed.\n- Return only the summary text."""
    elif field_type == "experience":
        prompt = f"""Improve the candidate's existing employment experience for a resume.\n\nCandidate information:\n{context_str}\n\nRequirements:\n- Use only employment facts and responsibilities supported by the source.\n- Preserve supplied employers, roles, and dates.\n- Do not invent duties, results, metrics, promotions, or achievements.\n- Do not turn the target job description into past experience.\n- Improve wording and ATS readability without changing factual meaning.\n- If there are no employment details, request them instead of inventing experience.\n- Return bullet points beginning with '-'."""
    elif field_type == "project":
        prompt = f"""Improve the candidate's project description for a resume.\n\nCandidate information:\n{context_str}\n\nRequirements:\n- Use only supplied project details.\n- Do not invent project names, technologies, team sizes, metrics, or results.\n- Do not claim implementation work that the source does not support.\n- If project details are missing, ask the user to provide them.\n- Return a concise paragraph or factual bullet points."""
    else:
        prompt = f"""Organize and improve the candidate's explicitly supplied skills for a professional resume.\n\nCandidate information:\n{context_str}\n\nRequirements:\n- Include only skills explicitly supported by the supplied information.\n- Do not add skills merely because they are common for the target role.\n- Do not assume a job requirement is a candidate qualification.\n- Remove duplicates and improve naming where appropriate.\n- If no actual skills are provided, ask the user to provide them.\n- Return a comma-separated list without introductory text."""

    try:
        generated_text = generate_ai_text(prompt)
    except Exception as exc:
        print(f"AI generation unavailable: {type(exc).__name__}: {exc}")
        return jsonify({
            "error": "AI generation is temporarily unavailable. Your credit has not been deducted. Please try again.",
            "code": "AI_PROVIDERS_UNAVAILABLE",
        }), 503

    if not is_premium_user:
        try:
            current_credits = int(getattr(current_user, "ai_credits_remaining", 0) or 0)
            if current_credits <= 0:
                return jsonify({"error": "No AI credits remaining. Please upgrade to Premium."}), 403

            current_user.ai_credits_remaining = current_credits - 1
            db.session.commit()
            credits_remaining = current_user.ai_credits_remaining
        except Exception as exc:
            db.session.rollback()
            print(f"AI credit deduction error: {exc}")
            return jsonify({
                "error": "The result was generated, but your credit could not be updated. Please refresh and check your account before retrying.",
                "result": generated_text,
            }), 500
    else:
        credits_remaining = int(getattr(current_user, "ai_credits_remaining", 0) or 0)

    return jsonify({
        "result": generated_text,
        "field_type": field_type,
        "credits_remaining": credits_remaining,
        "premium": is_premium_user,
    }), 200


# ============================================================
# DASHBOARD ROUTES
# ============================================================

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("")
@login_required
def home():
    try:
        user_resumes = Resume.query.filter_by(user_id=current_user.id).all()
        for resume in user_resumes:
            if isinstance(resume.content_json, str):
                try:
                    resume.content_json = json.loads(resume.content_json)
                except Exception:
                    resume.content_json = {}
            elif resume.content_json is None:
                resume.content_json = {}

        return render_template("dashboard/index.html", resumes=user_resumes, user=current_user)
    except Exception as exc:
        print(f"Dashboard Route Error: {exc}")
        return render_template("dashboard/index.html", resumes=[], user=current_user)


@dashboard_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        new_email = (request.form.get("email") or "").strip().lower()
        new_password = request.form.get("password") or ""

        if new_email and new_email != getattr(current_user, "email", None):
            existing_user = User.query.filter_by(email=new_email).first()
            if existing_user:
                flash("This email is already in use.", "error")
            else:
                current_user.email = new_email
                flash("Email updated successfully.", "success")

        if new_password:
            if len(new_password) < 8:
                flash("Password must contain at least 8 characters.", "error")
                return redirect(url_for("dashboard.account"))

            current_user.password_hash = generate_password_hash(new_password)
            flash("Password updated successfully.", "success")

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            print(f"Account update error: {exc}")
            flash("Account changes could not be saved.", "error")

        return redirect(url_for("dashboard.account"))

    try:
        return render_template("settings.html", user=current_user)
    except Exception:
        return render_template("dashboard/account.html", user=current_user)


premium_app.register_blueprint(dashboard_bp)

# ============================================================
# PADDLE WEBHOOK VERIFICATION (GUARDED AGAINST INDEX ERRORS)
# ============================================================

def verify_paddle_webhook(request_data, signature_header):
    if not PADDLE_WEBHOOK_SECRET_KEY or not signature_header or not isinstance(signature_header, str):
        return False

    try:
        components = {}
        for item in signature_header.split(";"):
            item = item.strip()
            if "=" in item:
                parts = item.split("=", 1)
                if len(parts) != 2:
                    continue
                key, value = parts[0].strip(), parts[1].strip()
                if key and value:
                    components[key] = value

        timestamp = components.get("ts")
        received_signature = components.get("h1")

        if not timestamp or not received_signature:
            return False

        decoded_body = (
            request_data.decode("utf-8")
            if isinstance(request_data, bytes)
            else str(request_data)
        )

        signed_payload = f"{timestamp}:{decoded_body}"

        digest = hmac.new(
            PADDLE_WEBHOOK_SECRET_KEY.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(digest, received_signature)

    except Exception as exc:
        print(f"Paddle HMAC Verification Error: {exc}")
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
        "paddle_price_id": PADDLE_PREMIUM_PRICE_ID,
    })


@premium_bp.route("/webhook/paddle", methods=["POST"])
def paddle_webhook():
    signature = request.headers.get("Paddle-Signature")
    payload = request.get_data()

    if not verify_paddle_webhook(payload, signature):
        return jsonify({"error": "Invalid signature"}), 400

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid webhook payload"}), 400

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
            try:
                user.is_premium = True
                user.subscription_status = event_data.get("status", "active")
                user.paddle_customer_id = event_data.get("customer_id")
                user.paddle_subscription_id = event_data.get("id")
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                print(f"Paddle activation update error: {exc}")
                return jsonify({"error": "Unable to update subscription"}), 500

    elif event_type in ["subscription.canceled", "subscription.past_due"]:
        subscription_id = event_data.get("id")
        if subscription_id:
            user = User.query.filter_by(paddle_subscription_id=subscription_id).first()
            if user:
                try:
                    user.is_premium = False
                    user.subscription_status = event_data.get("status", "canceled")
                    db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    print(f"Paddle cancellation update error: {exc}")
                    return jsonify({"error": "Unable to update subscription"}), 500

    return jsonify({"status": "success"}), 200


@premium_bp.route("/analyze-ats", methods=["POST"])
@login_required
def analyze_ats():
    if not getattr(current_user, "is_premium", False):
        return jsonify({"error": "Premium subscription required"}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON request is required."}), 400

    cv_data = data.get("cv_data")
    job_desc = data.get("job_description")

    if not cv_data or not job_desc:
        return jsonify({"error": "CV data and job description are required."}), 400

    try:
        cv_json = json.dumps(cv_data, ensure_ascii=False)
    except (TypeError, ValueError):
        return jsonify({"error": "CV data must be valid JSON-compatible content."}), 400

    prompt = f"Analyze the candidate's CV against the supplied job description.\n\nCV DATA:\n{cv_json}\n\nJOB DESCRIPTION:\n{job_desc}\n\nReturn a useful ATS analysis containing:\n1. An estimated ATS match score from 0 to 100.\n2. Keywords found in the CV.\n3. Important job-description keywords missing from the CV.\n4. Relevant strengths supported by the CV.\n5. Suggestions for improving alignment.\n6. Specific CV sections that could be improved."

    gemini_key = get_gemini_api_key()
    if not gemini_key:
        return jsonify({"error": "ATS analysis is temporarily unavailable. The Gemini API key is not configured."}), 503

    try:
        analysis_text = generate_with_gemini(prompt, gemini_key)
        return jsonify({"analysis": analysis_text}), 200
    except Exception as exc:
        print(f"ATS analysis error: {type(exc).__name__}: {exc}")
        return jsonify({"error": "Unable to analyze the CV at this time. Please try again later."}), 503


premium_app.register_blueprint(premium_bp)

# ============================================================
# VERCEL ENTRY POINT
# ============================================================

app = premium_app

# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    with premium_app.app_context():
        db.create_all()

    premium_app.run(debug=True, port=5001)
