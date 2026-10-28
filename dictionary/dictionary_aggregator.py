"""Common Pathway Aggregator for CVForge Dictionaries (`t_deal`)."""

from .outreach_dict import OUTREACH_DICT
from .portal_qa_dict import PORTAL_QA_DICT
from .salary_dict import SALARY_DICT

SUPPORTED_LANGUAGES = [
    "English (US / UK)",
    "Mandarin Chinese",
    "Spanish",
    "Hindi",
    "Arabic",
    "French",
    "Portuguese",
    "Russian",
    "German",
    "Japanese",
    "Korean",
    "Italian",
    "Turkish",
    "Dutch",
    "Polish",
    "Swedish",
    "Swahili",
]

TRANSLATIONS = {}

MODULE_DICTIONARIES = [
    OUTREACH_DICT,
    PORTAL_QA_DICT,
    SALARY_DICT,
]

for package in MODULE_DICTIONARIES:
    for lang, trans_dict in package.items():
        if lang not in TRANSLATIONS:
            TRANSLATIONS[lang] = {}
        if isinstance(trans_dict, dict):
            TRANSLATIONS[lang].update(trans_dict)


def t_deal(key: str, lang: str = "English (US / UK)", default: str = None) -> str:
    """Lookup translation matching string literals or keys for the 3rd pathway."""
    if not isinstance(key, str):
        return str(key)

    if not lang or lang not in SUPPORTED_LANGUAGES:
        lang = "English (US / UK)"

    lang_dict = TRANSLATIONS.get(lang, {})
    fallback_dict = TRANSLATIONS.get("English (US / UK)", {})

    return (
        lang_dict.get(key)
        or fallback_dict.get(key)
        or default
        or key
    )


def init_app_dictionary_pathway(app):
    """Registers t_deal into Flask's Jinja context without overlapping other context processors."""
    from flask import session, request

    @app.context_processor
    def inject_deal_translator():
        user_lang = session.get("language") or request.cookies.get("language") or "English (US / UK)"
        if user_lang not in SUPPORTED_LANGUAGES:
            user_lang = "English (US / UK)"

        return {
            "t_deal": lambda key, default=None: t_deal(key, lang=user_lang, default=default),
            "deal_current_lang": user_lang,
            "deal_supported_languages": SUPPORTED_LANGUAGES,
        }
