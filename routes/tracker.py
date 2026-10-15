from flask import Blueprint, render_template, session, request
from flask_login import login_required, current_user

tracker_bp = Blueprint("tracker", __name__, url_prefix="/dashboard/tracker")

TRACKER_TRANSLATIONS = {
    "English (US / UK)": {
        "tracker_title": "Job Application Tracker — CVForge Pro",
        "btn_back_dashboard": "← Back to Dashboard",
        "tracker_heading": "Job Application Tracker",
        "tracker_subheading": "Monitor your target applications, interview stages, and follow-ups in real time.",
        "btn_add_application": "Add Application",
        "metric_applied": "Total Applied",
        "metric_interviewing": "Interviewing",
        "metric_offers": "Offers Received",
        "metric_response_rate": "Interview Rate",
        "col_saved": "Saved / Target",
        "col_applied": "Applied",
        "col_interview": "Interviewing",
        "col_offer": "Offer Received",
        "modal_title": "Add Job Application",
        "label_company": "Company Name",
        "label_role": "Job Title / Role",
        "label_salary": "Salary Range (Optional)",
        "label_status": "Application Status",
        "opt_saved": "Saved / Target",
        "opt_applied": "Applied",
        "opt_interview": "Interviewing",
        "opt_offer": "Offer Received",
        "btn_save_app": "Save Application"
    }
}

def get_tracker_text(key: str, lang: str = "English (US / UK)", default: str = None) -> str:
    eng = TRACKER_TRANSLATIONS.get("English (US / UK)", {})
    lang_dict = TRACKER_TRANSLATIONS.get(lang, eng)
    return lang_dict.get(key, eng.get(key, default or key))

@tracker_bp.route("")
@login_required
def view_tracker():
    user_lang = session.get("language") or request.cookies.get("language") or "English (US / UK)"
    return render_template(
        "dashboard/tracker.html",
        t_page=lambda k, default=None: get_tracker_text(k, lang=user_lang, default=default),
        user=current_user
    )
