from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from app import db, User  # Adjust import based on your main app file name
from plans import PLANS
import uuid

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered.', 'error')
            return redirect(url_for('auth.register'))
        
        # Create new user with 15 Free Trial Credits and 'free' plan tier
        hashed_password = generate_password_hash(password)
        new_user = User(
            id=str(uuid.uuid4()), # Generates 36-char string ID matching your model
            email=email,
            password_hash=hashed_password,
            plan_tier='free',
            credits_balance=PLANS['free']['monthly_credits'], # Sets 15 credits
            ai_credits_remaining=PLANS['free']['monthly_credits']
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Log the user in automatically upon registration
        login_user(new_user)
        flash('Account created successfully! Enjoy your 15 free trial credits.', 'success')
        return redirect(url_for('dashboard')) # Change to your main dashboard/editor route
        
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
