from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column("passwordHash", db.String(255), nullable=False)
    created_at = db.Column("createdAt", db.DateTime, default=datetime.utcnow)
    updated_at = db.Column("updatedAt", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User Profile & Settings Extensions
    full_name = db.Column("fullName", db.String(255), nullable=True)
    avatar_url = db.Column("avatarUrl", db.String(500), nullable=True)
    preferences_json = db.Column("preferencesJson", db.JSON, nullable=True, default=dict)

    # Entitlement / Subscription
    is_premium = db.Column(db.Boolean, default=False)
    paddle_customer_id = db.Column(db.String(255), nullable=True)
    paddle_subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(50), default="free")
    
    # NEW FIELDS FOR FREEMIUM CONTROL
    plan_tier = db.Column(db.String(20), default='free')       # 'free', 'pro', or 'elite'
    credits_balance = db.Column(db.Integer, default=15)         # Starts at 15 for new signups
    
    # Metering
    monthly_cv_generations = db.Column(db.Integer, default=0)
    ai_credits_remaining = db.Column(db.Integer, default=15)    # Aligned with starter credits
    
    resumes = db.relationship('Resume', backref='owner', lazy=True)
    applications = db.relationship('JobApplication', backref='owner', lazy=True)
    cover_letters = db.relationship('CoverLetter', backref='owner', lazy=True)
    support_tickets = db.relationship('SupportTicket', backref='owner', lazy=True)


class Resume(db.Model):
    __tablename__ = 'resumes'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column("userId", db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), default="My Resume")
    content_json = db.Column("content_json", db.JSON, nullable=True)
    optimized_json = db.Column("optimizedJson", db.JSON, nullable=True, default={})
    original_text = db.Column("originalText", db.Text, nullable=True, default="")
    template_used = db.Column("template_used", db.String(50), default="modern")
    accent_color = db.Column("accent_color", db.String(20), default="#E5A93C")
    sidebar_color = db.Column("sidebar_color", db.String(20), default="#02353C")
    updated_at = db.Column("updatedAt", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobApplication(db.Model):
    __tablename__ = 'job_applications'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column("user_id", db.String(36), db.ForeignKey('users.id'), nullable=False)
    company_name = db.Column("company_name", db.String(255), nullable=False)
    role_title = db.Column("role_title", db.String(255), nullable=False)
    salary = db.Column("salary", db.String(100), nullable=True, default="")
    status = db.Column(db.String(50), default="Applied")
    job_url = db.Column("job_url", db.Text, nullable=True)
    ats_score = db.Column("ats_score", db.Integer, nullable=True)
    applied_date = db.Column("applied_date", db.DateTime, default=datetime.utcnow)
    updated_at = db.Column("updated_at", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CoverLetter(db.Model):
    __tablename__ = 'cover_letters'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column("userId", db.String(36), db.ForeignKey('users.id'), nullable=False)
    resume_id = db.Column("resumeId", db.String(36), db.ForeignKey('resumes.id'), nullable=True)
    company_name = db.Column("companyName", db.String(255), nullable=False)
    job_title = db.Column("jobTitle", db.String(255), nullable=False)
    tone = db.Column("tone", db.String(50), default="confident")
    job_description = db.Column("jobDescription", db.Text, nullable=True, default="")
    content = db.Column("content", db.Text, nullable=False)
    created_at = db.Column("createdAt", db.DateTime, default=datetime.utcnow)
    updated_at = db.Column("updatedAt", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column("user_id", db.String(36), db.ForeignKey('users.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # 'open', 'in_progress', 'resolved'
    created_at = db.Column("createdAt", db.DateTime, default=datetime.utcnow)
