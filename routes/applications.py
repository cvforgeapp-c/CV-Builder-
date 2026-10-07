import uuid
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models import db, JobApplication

apps_bp = Blueprint('applications', __name__, url_prefix='/applications')

@apps_bp.route('', methods=['GET'])
@login_required
def index():
    user_apps = JobApplication.query.filter_by(user_id=current_user.id).all()
    return render_template('applications/index.html', applications=user_apps)

@apps_bp.route('/create', methods=['POST'])
@login_required
def create():
    app_item = JobApplication(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_name=request.json.get('company_name'),
        role_title=request.json.get('role_title'),
        status=request.json.get('status', 'Applied'),
        job_url=request.json.get('job_url')
    )
    db.session.add(app_item)
    db.session.commit()
    return jsonify({"status": "created", "id": app_item.id})

@apps_bp.route('/update/<app_id>', methods=['PUT'])
@login_required
def update(app_id):
    app_item = JobApplication.query.filter_by(id=app_id, user_id=current_user.id).first_or_404()
    app_item.status = request.json.get('status', app_item.status)
    db.session.commit()
    return jsonify({"status": "updated"})
