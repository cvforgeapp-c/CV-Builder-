# plans.py

PLANS = {
    "free": {
        "name": "Free Explorer",
        "monthly_credits": 15,
        "is_recurring": False,
        "features": {
            "ats_resume_builder": True,
            "kanban_tracker": True,
            "pdf_template_studio": True,
            "application_copilot": True,
            "cover_letter_generator": False,
            "linkedin_optimizer": False,
            "interview_coach": False,
            "salary_negotiator": False,
            "outreach_email": False,
            "job_portal_qa": False,
            "priority_speed": False,
            "vip_support": False,
        }
    },
    "pro": {
        "name": "Pro Career Suite",
        "monthly_credits": 130,
        "is_recurring": True,
        "features": {
            "ats_resume_builder": True,
            "kanban_tracker": True,
            "pdf_template_studio": True,
            "application_copilot": True,
            "cover_letter_generator": True,
            "linkedin_optimizer": True,
            "interview_coach": True,
            "salary_negotiator": False,
            "outreach_email": False,
            "job_portal_qa": False,
            "priority_speed": False,
            "vip_support": False,
        }
    },
    "elite": {
        "name": "Elite Executive",
        "monthly_credits": 360,
        "is_recurring": True,
        "features": {
            "ats_resume_builder": True,
            "kanban_tracker": True,
            "pdf_template_studio": True,
            "application_copilot": True,
            "cover_letter_generator": True,
            "linkedin_optimizer": True,
            "interview_coach": True,
            "salary_negotiator": True,
            "outreach_email": True,
            "job_portal_qa": True,
            "priority_speed": True,
            "vip_support": True,
        }
    }
}

