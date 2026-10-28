from flask import Blueprint, jsonify, request, g
from decorators import require_feature, deduct_credits
from app import db

ai_bp = Blueprint('ai', __name__)

# ============================================================
# FREE TIER FEATURES (Supported via 15 Trial Credits)
# ============================================================

@ai_bp.route('/resume-builder', methods=['POST'])
@require_feature('ats_resume_builder')
def resume_builder():
    return jsonify({"status": "success", "message": "Standard ATS Resume Builder active."}), 200

@ai_bp.route('/kanban-tracker', methods=['POST'])
@require_feature('kanban_tracker')
def kanban_tracker():
    return jsonify({"status": "success", "message": "Kanban Tracker active."}), 200

@ai_bp.route('/pdf-studio', methods=['POST'])
@require_feature('pdf_template_studio')
@deduct_credits('pdf_studio')
def pdf_template_studio():
    return jsonify({"status": "success", "message": "PDF Template Studio rendered!"}), 200

@ai_bp.route('/application-copilot', methods=['POST'])
@require_feature('application_copilot')
@deduct_credits('application_copilot')
def application_copilot():
    return jsonify({"status": "success", "message": "Application Copilot executed!"}), 200


# ============================================================
# PRO CAREER SUITE FEATURES ($17.99/mo — 130 Credits)
# ============================================================

@ai_bp.route('/optimize-ats', methods=['POST'])
@require_feature('ats_resume_builder')
@deduct_credits('ats_optimizer')
def optimize_ats():
    return jsonify({"status": "success", "message": "Full ATS Deep Matcher & Optimizer complete!"}), 200

@ai_bp.route('/generate-cover-letter', methods=['POST'])
@require_feature('cover_letter_generator')
@deduct_credits('cover_letter')
def generate_cover_letter():
    return jsonify({"status": "success", "message": "Cover letter generated successfully!"}), 200

@ai_bp.route('/optimize-linkedin', methods=['POST'])
@require_feature('linkedin_optimizer')
@deduct_credits('linkedin_optimizer')
def optimize_linkedin():
    return jsonify({"status": "success", "message": "LinkedIn profile optimized!"}), 200

@ai_bp.route('/interview-prep', methods=['POST'])
@require_feature('interview_coach')
@deduct_credits('interview_coach')
def interview_prep():
    return jsonify({"status": "success", "message": "Interview coaching session generated!"}), 200


# ============================================================
# ELITE EXECUTIVE FEATURES ($43.99/mo — 360 Credits)
# ============================================================

@ai_bp.route('/negotiate-salary', methods=['POST'])
@require_feature('salary_negotiator')
@deduct_credits('salary_negotiator')
def negotiate_salary():
    return jsonify({"status": "success", "message": "Executive salary negotiation strategy ready!"}), 200

@ai_bp.route('/outreach-email', methods=['POST'])
@require_feature('outreach_email')
@deduct_credits('cold_outreach')
def outreach_email():
    return jsonify({"status": "success", "message": "Recruiter outreach campaign generated!"}), 200

@ai_bp.route('/job-qa', methods=['POST'])
@require_feature('job_portal_qa')
@deduct_credits('portal_qa')
def job_qa():
    return jsonify({"status": "success", "message": "Job portal application answers generated!"}), 200
