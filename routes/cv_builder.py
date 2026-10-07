import os, tempfile, uuid, base64
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from utils.pdf_generator import generate_cv
from models import db, Resume

cv_bp = Blueprint('cv', __name__)
USER_SESSIONS = {}

@cv_bp.route('/')
def index():
    token = request.args.get("token")
    user_data = USER_SESSIONS.get(token, {})
    return render_template("index.html", data=user_data, token=token)

@cv_bp.route('/generate', methods=['POST'])
def generate():
    data = {
        "name": request.form.get("name", ""),
        "title": request.form.get("title", ""),
        "phone": request.form.get("phone", ""),
        "email": request.form.get("email", ""),
        "location": request.form.get("location", ""),
        "linkedin": request.form.get("linkedin", ""),
        "website": request.form.get("website", ""),
        "summary": request.form.get("summary", ""),
        "experience": request.form.get("experience", ""),
        "education": request.form.get("education", ""),
        "skills": request.form.get("skills", ""),
        "certificates": request.form.get("certificates", ""),
        "languages": request.form.get("languages", ""),
        "hobbies": request.form.get("hobbies", ""),
        "references": request.form.get("references", ""),
        "template": request.form.get("template", "modern"),
        "accent_color": request.form.get("accent_color", "#F2B632"),
        "sidebar_color": request.form.get("sidebar_color", "#173F49"),
    }

    token = str(uuid.uuid4())
    USER_SESSIONS[token] = data

    pdf_path = os.path.join(tempfile.gettempdir(), f"CV_{token}.pdf")
    generate_cv(data["template"], data, pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

    return render_template("preview.html", pdf_data=pdf_base64, token=token)
