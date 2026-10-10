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

# Import Google Generative AI SDK
try:
    import google.generativeai as genai
except ImportError:
    genai = None

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

# Initialize AI API Keys
openai_api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if openai_api_key:
    openai.api_key = openai_api_key

if gemini_api_key and genai:
    genai.configure(api_key=gemini_api_key)

# ============================================================
# PADDLE CONFIGURATION
# ============================================================

PADDLE_API_KEY = os.getenv("PADDLE_API_KEY")
PADDLE_WEBHOOK_SECRET_KEY = os.getenv("PADDLE_WEBHOOK_SECRET_KEY")
PADDLE_ENV = os.getenv("PADDLE_ENV", "sandbox")
PADDLE_PREMIUM_PRICE_ID = os.getenv("PADDLE_PREMIUM_PRICE_ID", "pri_01hxxxxxxxxx")

# ============================================================
# DOMAIN FALLBACK DICTIONARY FOR AI SUGGEST SKILLS
# ============================================================

domain_fallbacks = {
    "healthcare": "Pediatric Care, Neonatal Intensive Care (NICU), Clinical Pharmacology, WHO Growth Standards, Patient Diagnostics, Emergency Triage, Biostatistics, Medical Research, Patient Advocacy, Cross-Functional Leadership",
    "tech": "Python, Flask, Next.js, React, TypeScript, PostgreSQL, REST APIs, Docker, Vercel Serverless, Tailwind CSS, System Architecture, Agile Methodologies",
    "finance": "Financial Modeling, Risk Assessment, Quantitative Analysis, Portfolio Management, Budgeting & Forecasting, Regulatory Compliance, Financial Reporting, Valuation, Excel (VBA)",
    "marketing": "Search Engine Optimization (SEO), Content Strategy, Digital Advertising (Meta/Google Ads), Marketing Automation, Brand Positioning, Social Media Analytics, Conversion Rate Optimization (CRO), Market Research",
    "sales": "B2B Sales, CRM Management (Salesforce, HubSpot), Lead Generation, Account Management, Consultative Selling, Pipeline Management, Contract Negotiation, Revenue Forecasting",
    "product": "Product Lifecycle Management, User Stories & Roadmapping, A/B Testing, Feature Prioritization, Customer Discovery, Agile/Scrum, Product Analytics (Mixpanel/Amplitude), Market Competitive Analysis",
    "hr": "Talent Acquisition, Employee Relations, HR Information Systems (HRIS), Performance Management, Compensation & Benefits, Onboarding Strategy, Regulatory Labor Compliance, Organizational Development",
    "general": "Strategic Planning, Process Optimization, Cross-Functional Project Management, Data Analysis, Stakeholder Engagement, Quality Assurance, Workflow Automation, Performance Metrics"
}

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
# SAVE RESUME ENDPOINT
# ============================================================

@premium_app.route("/api/v1/resumes/save", methods=["POST"])
@login_required
def save_resume():
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    title = data.get("title") or "My CV"

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
        "languages": data.get("languages", "")
    }

    resume_id = request.args.get("id") or data.get("id") or str(uuid.uuid4())
    resume = db.session.get(Resume, resume_id)

    if resume and resume.user_id == current_user.id:
        resume.title = title
        resume.content_json = content_data
        resume.template_used = "ats"
        resume.updated_at = datetime.utcnow()
    else:
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
            updated_at=datetime.utcnow()
        )
        db.session.add(resume)

    try:
        db.session.commit()
        
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "success", "redirect_url": f"/preview?id={resume.id}"}), 200

        flash("Resume saved successfully!", "success")
        return redirect(f"/preview?id={resume.id}")
    except Exception as e:
        db.session.rollback()
        print(f"Save Resume Error: {e}")
        if request.is_json:
            return jsonify({"error": "Failed to save resume."}), 500
        flash("Failed to save resume.", "error")
        return redirect(f"/editor?id={resume_id}")

# ============================================================
# DUAL OPENAI & GEMINI AI GENERATION ENDPOINT
# ============================================================

DEVELOPER_EMAILS = ["subhnllha@gmail.com"]

@premium_app.route("/api/v1/ai/generate-field", methods=["POST"])
@login_required
def generate_ai_field():
    # 1. DEVELOPER & PREMIUM CHECK
    user_email = getattr(current_user, "email", "").lower().strip()
    is_developer = user_email in DEVELOPER_EMAILS or user_email == "subhnllha@gmail.com"
    
    is_premium_user = getattr(current_user, "is_premium", False) or is_developer
    credits_remaining = getattr(current_user, "ai_credits_remaining", 0)

    if not is_premium_user and credits_remaining <= 0:
        return jsonify({"error": "No AI credits remaining. Please upgrade to Premium."}), 403

    # 2. EXTRACT FORM PAYLOAD
    data = request.get_json(silent=True) or {}
    field_type = data.get("field_type", "summary")
    
    target_role = data.get("target_role") or "Experienced Specialist"
    job_title = data.get("job_title") or target_role
    full_name = data.get("full_name") or "Candidate"
    skills = data.get("skills") or ""
    current_input = data.get("current_input") or ""

    # 3. BUILD CONTEXT STRING
    context_details = []
    if target_role: context_details.append(f"Target Role: {target_role}")
    if job_title: context_details.append(f"Recent Job Title: {job_title}")
    if full_name: context_details.append(f"Candidate Name: {full_name}")
    if skills: context_details.append(f"Technical & Core Skills: {skills}")
    if current_input: context_details.append(f"User Notes/Draft: {current_input}")
    
    context_str = "\n".join(context_details)

    # 4. INDUSTRY CLASSIFICATION & DYNAMIC FALLBACK CONSTRUCTOR
    role_lower = (target_role + " " + job_title).lower()
    is_medical = any(word in role_lower for word in ["doctor", "physician", "pediatric", "clinical", "nurse", "medical", "health", "hospital"])
    is_tech = any(word in role_lower for word in ["developer", "engineer", "software", "architect", "tech", "data", "full-stack", "backend", "frontend"])

    skills_part = f" specializing in {skills}" if skills else ""
    job_part = f" with hands-on experience as a {job_title}" if job_title and job_title != target_role else ""

    if is_medical:
        impact_sentence = "Proven ability to deliver high-quality patient care, optimize triage workflows, and maintain strict clinical standards."
        growth_sentence = "Dedicated to advancing patient health outcomes and fostering evidence-based healthcare excellence."
    elif is_tech:
        impact_sentence = "Proven ability to architect scalable system solutions, optimize backend performance, and build maintainable code bases."
        growth_sentence = "Focused on leveraging modern technical frameworks to engineer high-efficiency web applications."
    else:
        impact_sentence = "Proven ability to execute key strategic initiatives, optimize operational workflows, and drive cross-functional productivity."
        growth_sentence = "Committed to delivering measurable business impact and driving continuous operational growth."

    dynamic_fallback_summary = f"Dedicated {target_role}{job_part}{skills_part}. {impact_sentence} {growth_sentence}"

    # 5. CONSTRUCT AI PROMPTS
    if field_type == "summary":
        prompt = f"""
        You are an elite ATS resume writer and executive career strategist.
        Write a high-impact, 3-sentence executive summary for {full_name} using ALL provided details below.

        Context:
        {context_str}

        Instructions:
        1. Sentence 1: Combine Target Role ({target_role}) and Recent Experience ({job_title}).
        2. Sentence 2: Seamlessly integrate 2 to 4 of their listed skills ({skills}).
        3. Sentence 3: End with a strong value statement on driving quality and impact.
        4. Do NOT use generic filler sentences. Return ONLY the final paragraph.
        """
    elif field_type == "experience":
        prompt = f"""
        Transform these details into 3 high-impact, ATS-optimized bullet points for a resume:
        {context_str}

        Requirements:
        - Start every bullet with a strong action verb (e.g., Engineered, Spearheaded, Optimized).
        - Integrate listed skills: {skills}.
        - Return ONLY bullet points starting with a hyphen (-).
        """
    elif field_type == "project":
        prompt = f"""
        Write a concise 2-sentence project overview for {full_name} using these details:
        {context_str}

        Instructions:
        - Highlight project scope, technical implementation, and delivered impact.
        - Return ONLY clean paragraph text with no quotes.
        """
    elif field_type == "skills":
        prompt = f"""
        You are an expert career coach and ATS optimization specialist.
        Provide a comprehensive, comma-separated list of 10 to 12 highly relevant core technical, clinical, and professional skills tailored precisely for a {target_role}.

        Context:
        {context_str}

        Instructions:
        - Include industry-specific hard skills, technical competencies, and essential professional capabilities.
        - Return ONLY the comma-separated list of skills, with no extra formatting, bullets, or introductory text.
        """
    else:
        prompt = f"Write an executive resume passage using:\n{context_str}"

    generated_text = None

    # 6. STEP 1: TRY OPENAI GENERATION (gpt-4o)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            if hasattr(openai, "OpenAI"):
                client = openai.OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=250,
                    temperature=0.7
                )
                generated_text = response.choices[0].message.content.strip()
            else:
                openai.api_key = openai_key
                response = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=250,
                    temperature=0.7
                )
                generated_text = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI Attempt Failed: {e}")

    # 7. STEP 2: FALLBACK TO GOOGLE GEMINI IF OPENAI FAILS
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not generated_text and gemini_key and genai:
        try:
            gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            gemini_response = gemini_model.generate_content(prompt)
            if gemini_response and gemini_response.text:
                generated_text = gemini_response.text.strip()
        except Exception as e:
            print(f"Gemini Attempt Failed: {e}")

    # 8. STEP 3: INDUSTRY-TAILORED DYNAMIC FALLBACK IF BOTH APIS FAIL
    if not generated_text:
        if field_type == "experience":
            if is_medical:
                generated_text = (
                    f"- Directed clinical diagnostic and patient care protocols as {job_title}, ensuring 100% adherence to national health regulations.\n"
                    f"- Managed specialized treatments and patient evaluations utilizing {skills or 'evidence-based clinical practices'}.\n"
                    f"- Streamlined emergency triage and admission procedures, cutting average patient processing time by 20%."
                )
            elif is_tech:
                generated_text = (
                    f"- Architected and deployed production software components as {job_title}, improving application throughput by 30%.\n"
                    f"- Implemented automated workflows and resilient API endpoints using {skills or 'modern frameworks'}.\n"
                    f"- Optimized database queries and system performance to maintain high availability across core infrastructure."
                )
            else:
                generated_text = (
                    f"- Spearheaded key operational projects as {job_title}, driving cross-functional efficiency across major deliverables.\n"
                    f"- Leveraged domain expertise in {skills or 'strategic planning and leadership'} to optimize workflow output by 25%.\n"
                    f"- Directed performance evaluations and stakeholder engagement aligned with top industry benchmarks."
                )
        elif field_type == "project":
            if is_medical:
                generated_text = f"Led high-impact clinical research project focused on {skills or target_role}. Delivered measurable diagnostic efficiency gains and optimized patient care tracking workflows."
            elif is_tech:
                generated_text = f"Architected and deployed high-performance web solution centered around {skills or target_role}. Optimized serverless API throughput and reduced system response latency by 35%."
            else:
                generated_text = f"Led high-impact strategic initiative focused on {skills or target_role}. Delivered measurable operational performance gains ahead of project deadlines."
        elif field_type == "skills":
            # 8-Domain Skill Fallback Lookup
            if any(w in role_lower for w in ["doctor", "physician", "pediatric", "clinical", "nurse", "medical", "health", "hospital"]):
                generated_text = domain_fallbacks["healthcare"]
            elif any(w in role_lower for w in ["developer", "engineer", "software", "architect", "tech", "data", "full-stack", "backend", "frontend"]):
                generated_text = domain_fallbacks["tech"]
            elif any(w in role_lower for w in ["finance", "financial", "accounting", "auditor", "analyst", "banking", "investment"]):
                generated_text = domain_fallbacks["finance"]
            elif any(w in role_lower for w in ["marketing", "seo", "content", "social media", "brand", "growth"]):
                generated_text = domain_fallbacks["marketing"]
            elif any(w in role_lower for w in ["sales", "account executive", "business development", "crm"]):
                generated_text = domain_fallbacks["sales"]
            elif any(w in role_lower for w in ["product manager", "product owner", "scrum", "ux"]):
                generated_text = domain_fallbacks["product"]
            elif any(w in role_lower for w in ["hr", "human resources", "recruiter", "talent", "people"]):
                generated_text = domain_fallbacks["hr"]
            else:
                generated_text = domain_fallbacks["general"]
        else:
            generated_text = dynamic_fallback_summary

    # 9. DEDUCT CREDITS ONLY FOR REGULAR NON-PREMIUM USERS
    if not is_premium_user:
        current_user.ai_credits_remaining = max(0, current_user.ai_credits_remaining - 1)
        db.session.commit()

    return jsonify({"result": generated_text})

# ============================================================
# DASHBOARD ROUTES
# ============================================================

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@dashboard_bp.route("")
@login_required
def home():
    try:
        user_resumes = Resume.query.filter_by(user_id=current_user.id).all() if current_user and hasattr(current_user, "id") else []
        
        for resume in user_resumes:
            if isinstance(resume.content_json, str):
                try:
                    resume.content_json = json.loads(resume.content_json)
                except Exception:
                    resume.content_json = {}
            elif resume.content_json is None:
                resume.content_json = {}

        return render_template("dashboard/index.html", resumes=user_resumes, user=current_user)
    except Exception as e:
        print(f"Dashboard Route Error: {e}")
        return render_template("dashboard/index.html", resumes=[], user=current_user)


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
