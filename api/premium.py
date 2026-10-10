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
# DUAL OPENAI & GEMINI AI GENERATION ENDPOINT (DYNAMIC PROMPTS & MULTI-DOMAIN FALLBACKS)
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

    # 3. UPDATED DYNAMIC PROMPT BUILDER
    if field_type == "summary":
        prompt = f"""
        You are an elite ATS resume writer and executive career strategist.
        Write a high-impact, 3-sentence executive summary for {full_name} who is transitioning from their recent role as '{job_title}' to the target role of '{target_role}'.

        Context & Client Inputs:
        - Target Role: {target_role}
        - Recent Job Title: {job_title}
        - Key Skills: {skills}
        - Additional Notes: {current_input}

        Dynamic Generation Rules:
        1. Tailor the tone, metrics, and vocabulary specifically to the domain of '{target_role}' (e.g., clinical/patient outcomes for healthcare, system architecture/scalability for tech, revenue/growth for sales).
        2. Sentence 1: Connect the transition from '{job_title}' to '{target_role}' naturally.
        3. Sentence 2: Seamlessly weave in at least 2 to 3 core tools or technical skills from: [{skills}].
        4. Sentence 3: End with a high-value impact statement reflecting success metrics relevant to '{target_role}'.
        5. Do NOT use generic filler sentences or uniform templates. Return ONLY the final paragraph.
        """
    elif field_type == "experience":
        prompt = f"""
        Transform these details into 3 high-impact, ATS-optimized bullet points for a resume targeting the role of '{target_role}':
        - Recent Job Title: {job_title}
        - Skills to Integrate: {skills}
        - Additional Context: {current_input}

        Requirements:
        - Start every bullet with a strong industry-specific action verb (e.g., Architected, Spearheaded, Optimized, Directed).
        - Explicitly incorporate the listed skills: [{skills}].
        - Emphasize workflow efficiency or domain-specific achievements.
        - Return ONLY bullet points starting with a hyphen (-).
        """
    elif field_type == "project":
        prompt = f"""
        Write a concise 2-sentence project overview tailored to a '{target_role}' using these details:
        - Skills/Tech: {skills}
        - Details: {current_input}
        """
    elif field_type == "skills":
        prompt = f"""
        Suggest a comprehensive list of comma-separated core technical and professional skills tailored specifically for a '{target_role}' with background experience as '{job_title}':
        - Input Skills: {skills}
        """
    else:
        prompt = f"Write an executive resume passage for a '{target_role}' using:\n{current_input}"

    generated_text = None

    # 4. STEP 1: TRY OPENAI GENERATION (gpt-4o)
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

    # 5. STEP 2: FALLBACK TO GOOGLE GEMINI IF OPENAI FAILS
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not generated_text and gemini_key and genai:
        try:
            gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            gemini_response = gemini_model.generate_content(prompt)
            if gemini_response and gemini_response.text:
                generated_text = gemini_response.text.strip()
        except Exception as e:
            print(f"Gemini Attempt Failed: {e}")

    # 6. STEP 3: EXPANDED MULTI-PROFESSION DYNAMIC FALLBACK IF BOTH APIS FAIL
    if not generated_text:
        role_lower = target_role.lower()
        skills_part = f" specializing in {skills}" if skills else ""
        job_part = f" with hands-on experience as a {job_title}" if job_title and job_title != target_role else ""

        domain_fallbacks = {
            "healthcare": {
                "keywords": ["doctor", "physician", "pediatric", "clinical", "nurse", "medical", "health", "hospital", "surgeon"],
                "impact": "Proven ability to deliver high-quality patient care, optimize triage workflows, and maintain strict clinical safety standards.",
                "growth": "Dedicated to advancing patient health outcomes and fostering evidence-based healthcare excellence.",
                "skills": "Patient Care, Clinical Triage, Medical Diagnostics, Treatment Planning, Electronic Health Records (EHR), Patient Safety, Pharmacology",
                "bullets": [
                    f"Administered comprehensive patient care as a {job_title or target_role}, utilizing expertise in {skills or 'clinical guidelines'}.",
                    "Optimized clinical workflows and diagnostic turnaround times while ensuring full compliance with medical safety regulations.",
                    "Collaborated within multidisciplinary hospital teams to elevate patient recovery metrics and treatment success rates."
                ],
                "project": f"Led clinical quality initiative focusing on {skills or target_role}. Improved patient tracking efficiency and cross-departmental coordination."
            },
            "tech": {
                "keywords": ["developer", "engineer", "software", "architect", "tech", "data", "full-stack", "backend", "frontend", "devops", "ml", "ai"],
                "impact": "Proven ability to architect scalable system solutions, optimize performance bottlenecks, and build robust software architectures.",
                "growth": "Focused on leveraging modern technical stacks to engineer high-availability applications and drive digital transformation.",
                "skills": "Python, JavaScript, TypeScript, React, Node.js, SQL, RESTful APIs, Git, Docker, System Architecture, CI/CD",
                "bullets": [
                    f"Engineered and deployed scalable backend services as a {job_title or target_role}, leveraging {skills or 'modern frameworks'}.",
                    "Optimized application performance and reduced system latency through rigorous code refactoring and database tuning.",
                    "Integrated automated CI/CD deployment pipelines, increasing release reliability and cross-team deployment speed."
                ],
                "project": f"Architected high-throughput system leveraging {skills or target_role}, cutting execution latency and enhancing data throughput."
            },
            "finance": {
                "keywords": ["finance", "financial", "accountant", "analyst", "audit", "banking", "treasury", "controller", "investment"],
                "impact": "Proven ability to drive fiscal optimization, manage complex financial forecasting, and ensure rigorous regulatory compliance.",
                "growth": "Committed to delivering strategic financial insights and maximizing capital efficiency across portfolios.",
                "skills": "Financial Modeling, Budgeting, Variance Analysis, Risk Assessment, GAAP, Excel, Auditing, Cash Flow Management",
                "bullets": [
                    f"Managed comprehensive financial models and budgeting frameworks as a {job_title or target_role}, utilizing {skills or 'financial analytics'}.",
                    "Identified cost-reduction opportunities and optimized capital allocation, driving measurable improvements in profit margins.",
                    "Executed precise financial audits and risk assessments to safeguard institutional assets against market volatility."
                ],
                "project": f"Developed automated financial modeling dashboard using {skills or target_role}, streamlining quarterly forecasting accuracy."
            },
            "marketing": {
                "keywords": ["marketing", "growth", "social media", "content", "brand", "seo", "campaign", "copywriter", "pr"],
                "impact": "Proven ability to scale digital acquisition channels, boost brand positioning, and optimize multi-channel conversion funnels.",
                "growth": "Focused on leveraging data-driven campaign strategies to maximize user engagement and return on ad spend.",
                "skills": "SEO, Google Analytics, Content Strategy, A/B Testing, Paid Social Advertising, Email Marketing, Brand Positioning",
                "bullets": [
                    f"Orchestrated multi-channel marketing campaigns as a {job_title or target_role}, leveraging expertise in {skills or 'digital growth'}.",
                    "Executed rigorous A/B testing frameworks that elevated user acquisition metrics and improved organic conversion rates.",
                    "Analyzed audience engagement metrics to refine brand messaging and scale customer retention initiatives."
                ],
                "project": f"Launched growth marketing initiative utilizing {skills or target_role}, scaling web traffic and customer acquisition KPIs."
            },
            "sales": {
                "keywords": ["sales", "account executive", "business development", "partnership", "rep", "b2b", "ae"],
                "impact": "Proven ability to accelerate revenue growth, penetrate new market segments, and build high-value client pipelines.",
                "growth": "Committed to driving enterprise client acquisition and exceeding aggressive annual sales quotas.",
                "skills": "B2B Sales, Pipeline Management, CRM (Salesforce), Contract Negotiation, Lead Generation, Account Management, Cold Outreach",
                "bullets": [
                    f"Spearheaded enterprise client acquisition as a {job_title or target_role}, leveraging mastery in {skills or 'pipeline management'}.",
                    "Negotiated high-value B2B contracts and forged strategic partnerships that expanded territorial market share.",
                    "Optimized sales conversion funnels, consistently surpassing quota targets and boosting annual recurring revenue (ARR)."
                ],
                "project": f"Executed strategic sales enablement initiative focusing on {skills or target_role}, expanding key account retention."
            },
            "product": {
                "keywords": ["product manager", "product owner", "scrum", "agile", "program manager", "project manager"],
                "impact": "Proven ability to translate business vision into structured product roadmaps and drive cross-functional product execution.",
                "growth": "Focused on aligning user needs with technical deliverables to maximize product adoption and market fit.",
                "skills": "Agile Methodologies, Product Roadmapping, User Research, Backlog Grooming, Cross-Functional Leadership, Jira, Wireframing",
                "bullets": [
                    f"Led end-to-end product lifecycles as a {job_title or target_role}, utilizing {skills or 'Agile frameworks'}.",
                    "Synthesized user feedback and market research to prioritize feature backlogs and accelerate time-to-market.",
                    "Facilitated cross-functional collaboration between engineering, design, and marketing teams to meet key product milestones."
                ],
                "project": f"Managed product rollout leveraging {skills or target_role}, driving user retention and feature adoption metrics."
            },
            "hr": {
                "keywords": ["hr", "human resources", "recruiter", "talent", "people operations"],
                "impact": "Proven ability to scale high-performing talent pipelines, enhance employee engagement, and optimize HR operations.",
                "growth": "Dedicated to cultivating positive organizational cultures and aligning talent strategy with business growth.",
                "skills": "Talent Acquisition, Employee Relations, Performance Management, HRIS, Onboarding, Compensation & Benefits, Compliance",
                "bullets": [
                    f"Streamlined full-lifecycle recruitment and talent operations as a {job_title or target_role}, leveraging {skills or 'talent sourcing'}.",
                    "Designed and implemented employee retention and professional development programs that boosted team morale.",
                    "Optimized HR compliance workflows and performance management frameworks across diverse departments."
                ],
                "project": f"Spearheaded HR automation project utilizing {skills or target_role}, cutting onboarding cycle times significantly."
            }
        }

        matched_domain = "general"
        for domain, data in domain_fallbacks.items():
            if any(kw in role_lower for kw in data["keywords"]):
                matched_domain = domain
                break

        if matched_domain != "general":
            dom = domain_fallbacks[matched_domain]
            fallback_summary = f"Dedicated {target_role}{job_part}{skills_part}. {dom['impact']} {dom['growth']}"
            fallback_skills = skills if skills else dom["skills"]
            fallback_bullets = "\n".join([f"- {b}" for b in dom['bullets']])
            fallback_project = dom['project']
        else:
            fallback_summary = f"Dedicated {target_role}{job_part}{skills_part}. Proven ability to execute key strategic initiatives, optimize operational workflows, and drive cross-functional productivity. Committed to delivering measurable business impact and driving continuous operational growth."
            fallback_skills = skills if skills else "Strategic Planning, Process Optimization, Cross-Functional Leadership, Performance Management"
            fallback_bullets = f"- Spearheaded strategic initiatives as {job_title or target_role}, leveraging expertise in {skills or 'core domain practices'}.\n- Optimized operational workflows to maintain high efficiency and compliance standards.\n- Directed cross-functional project execution aligned with organizational growth targets."
            fallback_project = f"Led high-impact project execution focused on {skills or target_role}. Delivered measurable efficiency gains ahead of schedule."

        if field_type == "experience":
            generated_text = fallback_bullets
        elif field_type == "project":
            generated_text = fallback_project
        elif field_type == "skills":
            generated_text = fallback_skills
        else:
            generated_text = fallback_summary

    # 7. DEDUCT CREDITS ONLY FOR REGULAR NON-PREMIUM USERS
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
