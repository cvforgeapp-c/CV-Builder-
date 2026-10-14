"""Master Translation Pathway for CVForge.

Aggregates all screen-specific translation modules into a single, unified pipeline.
"""

from translations_auth import AUTH_TRANSLATIONS
from translations_dashboard import DASHBOARD_TRANSLATIONS
from translations_editor import EDITOR_TRANSLATIONS
from translations_landing import LANDING_TRANSLATIONS
from translations_preview import PREVIEW_TRANSLATIONS
from translations_register import REGISTER_TRANSLATIONS
from translations_settings import SETTINGS_TRANSLATIONS
from translations_forgot_password import FORGOT_PASSWORD_TRANSLATIONS

# Master list of 17 supported languages
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

# Language ISO codes for HTML lang tags and API interfaces
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

# --- MASTER AGGREGATION LOOP ---
TRANSLATIONS = {}

MODULES_TO_MERGE = [
    AUTH_TRANSLATIONS,
    DASHBOARD_TRANSLATIONS,
    EDITOR_TRANSLATIONS,
    LANDING_TRANSLATIONS,
    PREVIEW_TRANSLATIONS,
    REGISTER_TRANSLATIONS,
    SETTINGS_TRANSLATIONS,
    FORGOT_PASSWORD_TRANSLATIONS,
]

for source_dict in MODULES_TO_MERGE:
    for lang, keys in source_dict.items():
        if lang not in TRANSLATIONS:
            TRANSLATIONS[lang] = {}
        TRANSLATIONS[lang].update(keys)

# Ensure fallback to English for any missing keys in other languages
_ENGLISH_KEYS = TRANSLATIONS.get("English (US / UK)", {})

for language in SUPPORTED_LANGUAGES:
    TRANSLATIONS.setdefault(language, {})
    for key, english_val in _ENGLISH_KEYS.items():
        TRANSLATIONS[language].setdefault(key, english_val)


# --- CORE TRANSLATION HELPERS ---

def t(key: str, lang: str = "English (US / UK)", default: str = None) -> str:
    """Retrieve a translated string by key for the given language.
    
    Falls back to English dict, then explicit default argument, then the raw key.
    """
    if not isinstance(key, str):
        return str(key)

    # Normalize language name if an ISO code (e.g. 'en', 'fr') or invalid value is passed
    if not isinstance(lang, str) or lang not in SUPPORTED_LANGUAGES:
        code_map = {v: k for k, v in LANGUAGE_CODES.items()}
        lang = code_map.get(lang, "English (US / UK)")

    english = TRANSLATIONS.get("English (US / UK)", {})
    lang_dict = TRANSLATIONS.get(lang, english)

    # 1. Try target language dictionary
    translated_val = lang_dict.get(key)
    if translated_val is not None:
        return translated_val

    # 2. Try English master dictionary fallback
    english_val = english.get(key)
    if english_val is not None:
        return english_val

    # 3. Try inline template fallback default string
    if default is not None:
        return default

    # 4. Graceful final fallback to raw key
    return key


def get_supported_languages() -> list:
    """Return a copy of the supported languages list."""
    return SUPPORTED_LANGUAGES.copy()


def get_language_code(lang: str = "English (US / UK)") -> str:
    """Get ISO language code for HTML lang attributes."""
    return LANGUAGE_CODES.get(lang, "en")


def validate_translations() -> dict:
    """Audit all languages against English to verify key completeness."""
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


# --- FLASK INTEGRATION HELPER ---

def init_app_translations(app):
    """Inject translation functions into Jinja globally across all routes/templates."""
    from flask import session, request

    @app.context_processor
    def inject_translation_helpers():
        # Safeguard fallback resolution across sessions, request cookies, and default state
        user_lang = session.get('language') or request.cookies.get('language') or 'English (US / UK)'
        return dict(
            t=lambda key, default=None: t(key, lang=user_lang, default=default),
            current_lang=user_lang,
            supported_languages=get_supported_languages(),
            lang_code=get_language_code(user_lang)
        )


if __name__ == "__main__":
    print(f"✅ Merged modules successfully across {len(SUPPORTED_LANGUAGES)} languages.")
    print(f"🔑 Total unique translation keys in English: {len(TRANSLATIONS['English (US / UK)'])}")
    
    validation_issues = validate_translations()
    if not validation_issues:
        print("✨ All languages contain identical, valid keys!")
    else:
        print("⚠️ Validation issues found:", validation_issues)
