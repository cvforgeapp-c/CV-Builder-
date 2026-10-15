"""Master Translation Pathway for CVForge.
Bulletproof aggregation with direct fallback mapping.
"""

from translations_auth import AUTH_TRANSLATIONS
from translations_dashboard import DASHBOARD_TRANSLATIONS
from translations_editor import EDITOR_TRANSLATIONS
from translations_forgot_password import FORGOT_PASSWORD_TRANSLATIONS
from translations_landing import LANDING_TRANSLATIONS
from translations_preview import PREVIEW_TRANSLATIONS
from translations_register import REGISTER_TRANSLATIONS
from translations_settings import SETTINGS_TRANSLATIONS

SUPPORTED_LANGUAGES = [
    "English (US / UK)", "Mandarin Chinese", "Spanish", "Hindi", "Arabic", 
    "French", "Portuguese", "Russian", "German", "Japanese", "Korean", 
    "Italian", "Turkish", "Dutch", "Polish", "Swedish", "Swahili"
]

LANGUAGE_CODES = {
    "English (US / UK)": "en", "Mandarin Chinese": "zh-CN", "Spanish": "es",
    "Hindi": "hi", "Arabic": "ar", "French": "fr", "Portuguese": "pt",
    "Russian": "ru", "German": "de", "Japanese": "ja", "Korean": "ko",
    "Italian": "it", "Turkish": "tr", "Dutch": "nl", "Polish": "pl",
    "Swedish": "sv", "Swahili": "sw"
}

# Explicitly build TRANSLATIONS to avoid silent merge bugs
TRANSLATIONS = {}

modules = [
    AUTH_TRANSLATIONS, DASHBOARD_TRANSLATIONS, EDITOR_TRANSLATIONS,
    FORGOT_PASSWORD_TRANSLATIONS, LANDING_TRANSLATIONS, PREVIEW_TRANSLATIONS,
    REGISTER_TRANSLATIONS, SETTINGS_TRANSLATIONS
]

for mod in modules:
    for lang, keys in mod.items():
        if lang not in TRANSLATIONS:
            TRANSLATIONS[lang] = {}
        if isinstance(keys, dict):
            TRANSLATIONS[lang].update(keys)

def t(key: str, lang: str = "English (US / UK)", default: str = None) -> str:
    """Bulletproof lookup that NEVER returns the raw key if English or default exists."""
    if not isinstance(key, str):
        return str(key)
        
    # 1. Normalize language
    if lang not in TRANSLATIONS:
        lang = "English (US / UK)"
        
    # 2. Check target language dictionary
    val = TRANSLATIONS.get(lang, {}).get(key)
    if val:
        return val
        
    # 3. Check English master dictionary fallback
    eng_val = TRANSLATIONS.get("English (US / UK)", {}).get(key)
    if eng_val:
        return eng_val
        
    # 4. Check explicit default parameter
    if default is not None:
        return default
        
    # 5. Final fallback: Clean up the raw key into a readable sentence instead of showing code keys
    # e.g., 'hero_title_exact' becomes 'Hero Title Exact' instead of leaking code
    return key.replace('_', ' ').title()
