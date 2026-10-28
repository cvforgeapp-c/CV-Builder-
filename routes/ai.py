# routes/ai.py
from flask import Blueprint, jsonify, request, g
from decorators import require_feature, deduct_credits

ai_bp = Blueprint('ai', __name__)

# Cover Letter Generation (Pro & Elite only + 3 Credits)
@ai_bp.route('/api/generate-cover-letter', methods=['POST'])
@require_feature('cover_letter_generator')
@deduct_credits('cover_letter')
def generate_cover_letter():
    # Generation logic here...
    return jsonify({"status": "success", "data": "Generated letter..."}), 200

# Salary Negotiator (Elite only + 5 Credits)
@ai_bp.route('/api/negotiate-salary', methods=['POST'])
@require_feature('salary_negotiator')
@deduct_credits('salary_negotiate')
def negotiate_salary():
    # Executive salary negotiation AI logic...
    return jsonify({"status": "success", "data": "Negotiation script..."}), 200

# ATS Optimization (All plans including Free + 2 Credits)
@ai_bp.route('/api/optimize-ats', methods=['POST'])
@require_feature('ats_resume_builder')
@deduct_credits('ats_optimize')
def optimize_ats():
    return jsonify({"status": "success", "data": "Optimized score..."}), 200
