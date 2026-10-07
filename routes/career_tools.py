import openai
from flask import Blueprint, request, jsonify
from flask_login import login_required

tools_bp = Blueprint('tools', __name__, url_prefix='/api/v1/tools')

@tools_bp.route('/linkedin-optimize', methods=['POST'])
@login_required
def linkedin_optimize():
    cv_data = request.json.get('cv_data')
    prompt = f"Generate an optimized LinkedIn headline and About section from: {cv_data}"
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"linkedin_profile": response.choices[0].message.content})

@tools_bp.route('/interview-prep', methods=['POST'])
@login_required
def interview_prep():
    job_desc = request.json.get('job_description')
    prompt = f"Generate top 5 behavioral & technical interview questions + model answers for: {job_desc}"
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"interview_prep": response.choices[0].message.content})
