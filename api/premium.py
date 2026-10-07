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
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

premium_app = Flask(__name__, template_folder=TEMPLATE_DIR)
premium_app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "cvforge-premium-key-998877")
premium_app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///:memory:")
premium_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(premium_app)
login_manager = LoginManager(premium_app)
login_manager.login_view = 'auth.login'

# Paddle API Configurations (Set in Vercel Environment Variables)
PADDLE_API_KEY = os.getenv("PADDLE_API_KEY")
PADDLE_WEBHOOK_SECRET_KEY = os.getenv("PADDLE_WEBHOOK_SECRET_KEY")
PADDLE_ENV = os.getenv("PADDLE_ENV", "sandbox")  # 'sandbox' or 'production'

# ============================================================
# DATABASE MODELS
# ============================================================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Paddle Subscription Details
    is_premium = db.Column(db.Boolean, default=False)
    paddle_customer_id = db.Column(db.String(255), nullable=True)
    paddle_subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(50), default="free")

    resumes = db.relationship('Resume', backref='owner', lazy=True)


class Resume(db.Model):
    __tablename__ = 'resumes'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), default="My Resume")
    content_json = db.Column(db.JSON, nullable=True)
    template_used = db.Column(db.String(50), default="modern")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobApplication(db.Model):
    __tablename__ = 'job_applications'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    role_title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default="Applied")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# ============================================================
# AUTHENTICATION ROUTES (AUTH BLUEPRINT)
# ============================================================
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please log in.")
            return redirect(url_for('auth.register'))

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect('/dashboard')

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect('/dashboard')

        flash("Invalid email or password.")
        return redirect(url_for('auth.login'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


premium_app.register_blueprint(auth_bp)


# ============================================================
# DASHBOARD ROUTES
# ============================================================
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('')
@login_required
def home():
    user_resumes = Resume.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard/index.html', resumes=user_resumes, user=current_user)


@dashboard_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    return render_template('dashboard/account.html', user=current_user)


premium_app.register_blueprint(dashboard_bp)


# ============================================================
# PADDLE WEBHOOK VERIFICATION HELPER
# ============================================================
def verify_paddle_webhook(request_data, signature_header):
    if not PADDLE_WEBHOOK_SECRET_KEY or not signature_header:
        return False
    
    try:
        # Extract ts and h1 components from Paddle-Signature header
        components = dict(item.split('=') for item in signature_header.split(';'))
        ts = components.get('ts')
        h1 = components.get('h1')

        # Reconstruct signed payload
        signed_payload = f"{ts}:{request_data.decode('utf-8')}"
        
        # Compute HMAC SHA256 hash
        digest = hmac.new(
            PADDLE_WEBHOOK_SECRET_KEY.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(digest, h1)
    except Exception as e:
        print(f"Paddle HMAC Verification Error: {e}")
        return False


# ============================================================
# PHASE 1 & 2: PREMIUM ROUTE MODULE (PADDLE INTEGRATED)
# ============================================================
premium_bp = Blueprint('premium_api', __name__, url_prefix='/api/v1/premium')


@premium_bp.route('/user-status', methods=['GET'])
@login_required
def get_user_status():
    """Returns current user details to initialize Paddle Overlay Checkout on Frontend"""
    return jsonify({
        "user_id": current_user.id,
        "email": current_user.email,
        "is_premium": current_user.is_premium,
        "paddle_price_id": os.getenv("PADDLE_PREMIUM_PRICE_ID", "pri_01hxxxxxxxxx")
    })


@premium_bp.route('/webhook/paddle', methods=['POST'])
def paddle_webhook():
    """Listens for Paddle Billing Events (Billing v2)"""
    signature = request.headers.get('Paddle-Signature')
    payload = request.get_data()

    if not verify_paddle_webhook(payload, signature):
        return jsonify({"error": "Invalid signature"}), 400

    data = request.json
    event_type = data.get("event_type")
    event_data = data.get("data", {})

    # 1. Subscription Created or Activated
    if event_type in ["subscription.created", "subscription.activated"]:
        custom_data = event_data.get("custom_data", {})
        user_id = custom_data.get("user_id")
        
        user = None
        if user_id:
            user = User.query.get(user_id)
        else:
            # Fallback lookup by customer email
            customer_id = event_data.get("customer_id")
            user = User.query.filter_by(paddle_customer_id=customer_id).first()

        if user:
            user.is_premium = True
            user.subscription_status = event_data.get("status", "active")
            user.paddle_customer_id = event_data.get("customer_id")
            user.paddle_subscription_id = event_data.get("id")
            db.session.commit()

    # 2. Subscription Canceled or Past Due
    elif event_type in ["subscription.canceled", "subscription.past_due"]:
        sub_id = event_data.get("id")
        user = User.query.filter_by(paddle_subscription_id=sub_id).first()
        if user:
            user.is_premium = False
            user.subscription_status = event_data.get("status", "canceled")
            db.session.commit()

    return jsonify({"status": "success"}), 200


@premium_bp.route('/analyze-ats', methods=['POST'])
@login_required
def analyze_ats():
    if not current_user.is_premium:
        return jsonify({"error": "Premium subscription required"}), 403

    cv_data = request.json.get('cv_data')
    job_desc = request.json.get('job_description')

    prompt = f"Provide ATS Score (0-100) and list missing keywords:\nCV: {json.dumps(cv_data)}\nJob: {job_desc}"
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"analysis": response.choices[0].message.content})


premium_app.register_blueprint(premium_bp)

with premium_app.app_context():
    db.create_all()

if __name__ == "__main__":
    premium_app.run(debug=True, port=5001)
