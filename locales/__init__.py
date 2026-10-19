"""Unified Locales Aggregator for CVForge Modular Feature Pathways.
Combines core translation logic, validation, and Flask integration helpers.
"""

from .common import COMMON_LOCALES
from .forgot_password import FORGOT_PASSWORD_LOCALES
from .tracker import TRACKER_LOCALES
from .ats import ATS_LOCALES
from .outreach import OUTREACH_LOCALES
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

TRANSLATIONS = {}

MODULE_PACKAGES = [
    COMMON_LOCALES,
    FORGOT_PASSWORD_LOCALES,
    TRACKER_LOCALES,
    ATS_LOCALES,
    OUTREACH_LOCALES,
    PDF_STUDIO_LOCALES,
    COVER_LETTER_LOCALES,
    LINKEDIN_LOCALES,
    INTERVIEW_LOCALES,
    SUPPORT_LOCALES,
]

for package in MODULE_PACKAGES:
    for lang, translations_dict in package.items():
        if lang not in TRANSLATIONS:
            TRANSLATIONS[lang] = {}
        if isinstance(translations_dict, dict):
            TRANSLATIONS[lang].update(translations_dict)


# ============================================================
# CORE TRANSLATION HELPERS & VALIDATION
# ============================================================

def t(key: str, lang: str = "English (US / UK)", default: str = None) -> str:
    """Core translation lookup helper matching legacy translation patterns."""
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


def get_supported_languages() -> list:
    """Return a copy of all supported languages."""
    return SUPPORTED_LANGUAGES.copy()


def get_language_code(lang: str = "English (US / UK)") -> str:
    """Return ISO language code for a given language name."""
    return LANGUAGE_CODES.get(lang, "en")


def validate_translations() -> dict:
    """Audit all modular languages against English to verify key completeness."""
    english_keys = set(TRANSLATIONS.get("English (US / UK)", {}))
    issues = {}

    for language in SUPPORTED_LANGUAGES:
        lang_dict = TRANSLATIONS.get(language)
        if not isinstance(lang_dict, dict):
            issues[language] = {"missing": sorted(english_keys), "extra": [], "invalid_values": []}
            continue

        lang_keys = set(lang_dict)
        missing = sorted(english_keys - lang_keys)
        extra = sorted(lang_keys - english_keys)
        invalid_values = sorted(k for k, v in lang_dict.items() if not isinstance(v, str))

        if missing or extra or invalid_values:
            issues[language] = {
                "missing": missing,
                "extra": extra,
                "invalid_values": invalid_values,
            }

    return issues


# ============================================================
# FLASK INTEGRATION HELPER
# ============================================================

def init_app_locales(app):
    """Registers modular translation functions into Flask's Jinja context."""
    from flask import session, request

    @app.context_processor
    def inject_modular_locales():
        user_lang = session.get("language") or request.cookies.get("language") or "English (US / UK)"
        
        if user_lang not in SUPPORTED_LANGUAGES:
            user_lang = "English (US / UK)"

        return {
            "t_modular": lambda key, default=None: t(key, lang=user_lang, default=default),
            "current_lang": user_lang,
            "supported_languages": SUPPORTED_LANGUAGES,
            "lang_code": get_language_code(user_lang),
        }


# ============================================================
# STANDALONE EXECUTION CHECK
# ============================================================

if __name__ == "__main__":
    print(f"✅ Merged modular modules successfully across {len(SUPPORTED_LANGUAGES)} languages.")
    print(f"🔑 Total unique modular translation keys in English: {len(TRANSLATIONS.get('English (US / UK)', {}))}")
    
    validation_issues = validate_translations()
    if not validation_issues:
        print("✨ All modular languages contain identical, valid keys!")
    else:
        print("⚠️ Validation issues found in modules:", validation_issues)
