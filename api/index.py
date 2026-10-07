import os
import sys
import tempfile
import uuid
import base64

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, request, render_template, send_file
from utils.pdf_generator import generate_cv

TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Global session cache to store form data per token
USER_SESSIONS = {}


@app.route("/")
def landing():
    """Serves the Landing Page showcasing Free vs Premium features"""
    return render_template("landing.html")


@app.route("/builder")
def index():
    """Serves the Free CV Builder interface"""
    token = request.args.get("token")
    # Retrieve previous data if token exists, or pass an empty dictionary
    user_data = USER_SESSIONS.get(token, {})
    return render_template("index.html", data=user_data, token=token)


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route("/generate", methods=["POST"])
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
        "projects": request.form.get("projects", ""),
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

    photo = request.files.get("photo")
    if photo and photo.filename:
        photo_path = os.path.join(tempfile.gettempdir(), f"photo_{uuid.uuid4().hex}_{photo.filename}")
        photo.save(photo_path)
        data["photo"] = photo_path

    selected_template = request.form.get("template", "modern")
    token = str(uuid.uuid4())
    
    # Store form data under session token
    USER_SESSIONS[token] = data

    pdf_path = os.path.join(tempfile.gettempdir(), f"CV_{token}.pdf")

    # Generate the PDF file on disk
    generate_cv(selected_template, data, pdf_path)

    # Read binary PDF and convert to base64 string for preview.html
    with open(pdf_path, "rb") as f:
        pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

    # Return preview page with session token
    return render_template("preview.html", pdf_data=pdf_base64, token=token)


if __name__ == "__main__":
    app.run(debug=True)
