"""Unified Locales Aggregator for CVForge.

Safely combines all modular dictionaries (common UI, auth, and all 8 premium features)
into a unified translation mapping across all 17 supported core global languages.
"""

from .common import COMMON_LOCALES
from .forgot_password import FORGOT_PASSWORD_LOCALES
from .tracker import TRACKER_LOCALES
from .ats import ATS_LOCALES
from .matcher import MATCHER_LOCALES
from .pdf_studio import PDF_STUDIO_LOCALES
from .cover_letter import COVER_LETTER_LOCALES
from .linkedin import LINKEDIN_LOCALES
from .interview import INTERVIEW_LOCALES
from .support import SUPPORT_LOCALES

# ============================================================
# SUPPORTED LANGUAGES & ISO CODES (17 Core Global Languages)
# ============================================================

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

LANGUAGE_CODES = {
    "English (US / UK)": "en",
    "Mandarin Chinese": "zh-CN",
    "Spanish": "es",
    "Hindi": "hi",
    "Arabic": "ar",
    "French": "fr",
    "Portuguese": "pt",
    "Russian": "ru",
    "German": "de",
    "Japanese": "ja",
    "Korean": "ko",
    "Italian": "it",
    "Turkish": "tr",
    "Dutch": "nl",
    "Polish": "pl",
    "Swedish": "sv",
    "Swahili": "sw",
}

# ============================================================
# MASTER DICTIONARY AGGREGATION
# ============================================================

ALL_LOCALES = {}

MODULE_PACKAGES = [
    COMMON_LOCALES,
    FORGOT_PASSWORD_LOCALES,
    TRACKER_LOCALES,
    ATS_LOCALES,
    MATCHER_LOCALES,
    PDF_STUDIO_LOCALES,
    COVER_LETTER_LOCALES,
    LINKEDIN_LOCALES,
    INTERVIEW_LOCALES,
    SUPPORT_LOCALES,
]

for package in MODULE_PACKAGES:
    for lang, translations in package.items():
        if lang not in ALL_LOCALES:
            ALL_LOCALES[lang] = {}
        if isinstance(translations, dict):
            ALL_LOCALES[lang].update(translations)


# ============================================================
# BULLETPROOF LOOKUP & TRANSLATION RESOLVER
# ============================================================

def resolve_translation(key: str, lang: str = "English (US / UK)", default: str = None) -> str:
    """Bulletproof translation lookup with explicit fallback mechanisms.
    
    Resolution Order:
    1. Target language translation dictionary
    2. English (US / UK) fallback dictionary
    3. Default parameter string (if provided)
    4. Clean Title-Cased string derived from key
    """
    if not isinstance(key, str):
        return str(key)

    if not lang or lang not in SUPPORTED_LANGUAGES:
        lang = "English (US / UK)"

    english_dict = ALL_LOCALES.get("English (US / UK)", {})
    target_dict = ALL_LOCALES.get(lang, english_dict)

    return (
        target_dict.get(key)
        or english_dict.get(key)
        or default
        or key.replace('_', ' ').title()
    )


def get_supported_languages() -> list:
    """Return a copy of all supported languages."""
    return SUPPORTED_LANGUAGES.copy()


def get_language_code(lang: str = "English (US / UK)") -> str:
    """Return ISO language code for a given language name."""
    return LANGUAGE_CODES.get(lang, "en")


# ============================================================
# FLASK CONTEXT PROCESSOR INTEGRATION
# ============================================================

def init_app_locales(app):
    """Registers global translation helpers into Flask's Jinja context."""
    from flask import session, request

    @app.context_processor
    def inject_locales():
        user_lang = session.get("language") or "English (US / UK)"
        return {
            "current_language": user_lang,
            "html_lang_code": get_language_code(user_lang),
            "supported_languages": SUPPORTED_LANGUAGES,
            "t": lambda key, default=None: resolve_translation(key, lang=user_lang, default=default),
        }
