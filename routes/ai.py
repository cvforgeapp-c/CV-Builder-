import json, httpx, openai
from bs4 import BeautifulSoup
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

ai_bp = Blueprint('ai', __name__, url_prefix='/api/v1/ai')

def require_premium_check(user):
    return user.is_authenticated and user.is_premium

@ai_bp.route('/scrape-job', methods=['POST'])
@login_required
def scrape_job():
    url = request.json.get('job_url')
    headers = {"User-Agent": "Mozilla/5.0"}
    res = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
    
    soup = BeautifulSoup(res.text, "html.parser")
    for script in soup(["script", "style", "nav", "footer"]):
        script.extract()
        
    clean_text = "\n".join(line.strip() for line in soup.get_text().splitlines() if line.strip())
    return jsonify({"job_description": clean_text[:4000]})

@ai_bp.route('/analyze-ats', methods=['POST'])
@login_required
def analyze_ats():
    if not require_premium_check(current_user):
        return jsonify({"error": "Premium required"}), 403

    cv_data = request.json.get('cv_data')
    job_desc = request.json.get('job_description')

    prompt = f"Calculate ATS score (0-100) and list missing keywords:\nCV: {json.dumps(cv_data)}\nJob: {job_desc}"
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"analysis": response.choices[0].message.content})

@ai_bp.route('/tailor-cv', methods=['POST'])
@login_required
def tailor_cv():
    if not require_premium_check(current_user):
        return jsonify({"error": "Premium required"}), 403

    cv_data = request.json.get('cv_data')
    job_desc = request.json.get('job_description')

    prompt = f"Rewrite CV summary & experience bullets for this job:\nCV: {json.dumps(cv_data)}\nJob: {job_desc}"
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"tailored_data": response.choices[0].message.content})
