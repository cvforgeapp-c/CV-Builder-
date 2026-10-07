from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Resume

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
