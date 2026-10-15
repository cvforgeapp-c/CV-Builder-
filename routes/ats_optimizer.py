from flask import Blueprint, render_template, session, request
from flask_login import login_required, current_user
try:
    from models import Resume
except ImportError:
    from ..models import Resume

ats_bp = Blueprint("ats_optimizer", __name__, url_prefix="/dashboard/ats-optimizer")

ATS_TRANSLATIONS = {
    "English (US / UK)": {
        "ats_title": "AI ATS Optimizer — CVForge Pro",
        "btn_back_dashboard": "← Back to Dashboard",
        "ats_heading": "Unlimited AI ATS Optimization Engine",
        "ats_subheading": "Target any job description, pinpoint ATS keyword gaps, and automatically rewrite your resume bullet points for high-match scores.",
        "section_input_title": "Select CV & Paste Target Job",
        "label_select_cv": "Select CV to Optimize",
        "label_job_desc": "Target Job Description",
        "btn_analyze_now": "Analyze & Optimize ATS Match",
        "section_results_title": "ATS Match Analysis & Keyword Report",
        "score_title": "Estimated ATS Match Score",
        "score_desc": "Based on keyword density, skills alignment & formatting",
        "title_matched_keywords": "Matched Keywords Found",
        "title_missing_keywords": "Missing Critical Keywords",
        "ai_suggestion_title": "AI Bullet-Point Optimization Suggestion",
        "btn_apply_rewrite": "Apply Rewrite to CV"
    }
}

def get_ats_text(key: str, lang: str = "English (US / UK)", default: str = None) -> str:
    eng = ATS_TRANSLATIONS.get("English (US / UK)", {})
    lang_dict = ATS_TRANSLATIONS.get(lang, eng)
    return lang_dict.get(key, eng.get(key, default or key))

@ats_bp.route("")
@login_required
def view_ats_optimizer():
    user_lang = session.get("language") or request.cookies.get("language") or "English (US / UK)"
    resumes = Resume.query.filter_by(user_id=current_user.id).all()
    return render_template(
        "dashboard/ats_optimizer.html",
        t_page=lambda k, default=None: get_ats_text(k, lang=user_lang, default=default),
        resumes=resumes,
        user=current_user
    )
