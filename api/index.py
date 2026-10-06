import os
import sys
import tempfile
import uuid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, request, render_template, send_file
from utils.pdf_generator import generate_cv

TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)

@app.route("/")
def index():
    return render_template("index.html")

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
    pdf_path = os.path.join(tempfile.gettempdir(), f"CV_{token}.pdf")

    generate_cv(selected_template, data, pdf_path)

    return send_file(pdf_path, as_attachment=True, download_name=f"{data['name'] or 'CV'}.pdf")

if __name__ == "__main__":
    app.run(debug=True)
