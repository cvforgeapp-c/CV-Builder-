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
    
    # Map the updatedAt column to prevent NOT NULL database violations
    updated_at = db.Column("updatedAt", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Entitlement / Subscription
    is_premium = db.Column(db.Boolean, default=False)
    paddle_customer_id = db.Column(db.String(255), nullable=True)
    paddle_subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(50), default="free")
    
    # Metering
    monthly_cv_generations = db.Column(db.Integer, default=0)
    ai_credits_remaining = db.Column(db.Integer, default=3)
    
    resumes = db.relationship('Resume', backref='owner', lazy=True)
    applications = db.relationship('JobApplication', backref='owner', lazy=True)
