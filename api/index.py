import os
import base64
from io import BytesIO
from flask import Flask, request, render_template, send_file
from utils.pdf_generator import generate_pdf

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app = Flask(__name__, template_folder=template_dir)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    photo = request.files.get("photo")

    def form_limit(name, maximum):
        return request.form.get(name, "")[:maximum]

    data = {
        "name": form_limit("name", 100),
        "title": form_limit("title", 70),
        "phone": form_limit("phone", 50),
        "email": form_limit("email", 100),
        "location": form_limit("location", 100),
        "linkedin": form_limit("linkedin", 200),
        "website": form_limit("website", 200),
        "summary": form_limit("summary", 500),
        "experience": form_limit("experience", 1200),
        "projects": form_limit("projects", 800),
        "education": form_limit("education", 600),
        "skills": form_limit("skills", 400),
        "certificates": form_limit("certificates", 500),
        "languages": form_limit("languages", 250),
        "hobbies": form_limit("hobbies", 250),
        "references": form_limit("references", 500),
        "template": request.form.get("template", "modern"),
        "accent_color": request.form.get("accent_color", "#F2B632"),
        "sidebar_color": request.form.get("sidebar_color", "#173F49"),
    }

    if photo and photo.filename:
        photo_stream = BytesIO(photo.read())
        data["photo_stream"] = photo_stream
    else:
        data["photo_stream"] = None

    pdf_buffer = BytesIO()
    generate_pdf(data, pdf_buffer)
    pdf_bytes = pdf_buffer.getvalue()

    pdf_data = base64.b64encode(pdf_bytes).decode("utf-8")

    return render_template("preview.html", pdf_data=pdf_data)

@app.route("/download", methods=["POST"])
def download_pdf():
    pdf_data = request.form.get("pdf_data")
    if not pdf_data:
        return "Invalid request.", 400

    pdf_bytes = base64.b64decode(pdf_data)
    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name="CVForge_Professional_CV.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
