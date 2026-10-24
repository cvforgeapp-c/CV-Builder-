import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import io
import json
import os
import random
import re
import sys
import uuid
from bs4 import BeautifulSoup
from flask import (
    Blueprint,
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
import httpx
import requests
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)
from werkzeug.utils import secure_filename

# ============================================================
# MODERN GOOGLE GENAI SDK
# ============================================================

try:
  from google import genai
  from google.genai import types
except ImportError:
  genai = None
  types = None

# ============================================================
# PATH CONFIGURATION FOR VERCEL
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))

if BASE_DIR not in sys.path:
  sys.path.insert(0, BASE_DIR)

if PROJECT_ROOT not in sys.path:
  sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# DATABASE MODELS & DUAL TRANSLATION PATHWAY SETUP
# ============================================================

try:
  from models import CoverLetter, JobApplication, Resume, User, db
except ImportError:
  from ..models import CoverLetter, JobApplication, Resume, User, db

# 1. LEGACY CORE PATHWAY (translations.py)
try:
  from translations import (
      TRANSLATIONS,
      SUPPORTED_LANGUAGES,
      get_language_code,
      get_supported_languages,
      t,
  )
except ImportError:
  try:
    from ..translations import (
        TRANSLATIONS,
        SUPPORTED_LANGUAGES,
        get_language_code,
        get_supported_languages,
        t,
    )
  except ImportError:
    SUPPORTED_LANGUAGES = [
        'English (US / UK)',
        'Mandarin Chinese',
        'Spanish',
        'Hindi',
        'Arabic',
        'French',
        'Portuguese',
        'Russian',
        'German',
        'Japanese',
        'Korean',
        'Italian',
        'Turkish',
        'Dutch',
        'Polish',
        'Swedish',
        'Swahili',
    ]

    def t(key, lang='English (US / UK)'):
      return str(key)

    def get_supported_languages():
      return SUPPORTED_LANGUAGES.copy()

    def get_language_code(lang='English (US / UK)'):
      return 'en'

    TRANSLATIONS = {}

# 2. NEW MODULAR LOCALES PATHWAY (locales/__init__.py)
try:
  from locales import (
      SUPPORTED_LANGUAGES as MODULAR_SUPPORTED_LANGUAGES,
      TRANSLATIONS as MODULAR_TRANSLATIONS,
      get_language_code as get_modular_language_code,
      get_supported_languages as get_modular_supported_languages,
      t as modular_t,
  )
except ImportError:
  try:
    from ..locales import (
        SUPPORTED_LANGUAGES as MODULAR_SUPPORTED_LANGUAGES,
        TRANSLATIONS as MODULAR_TRANSLATIONS,
        get_language_code as get_modular_language_code,
        get_supported_languages as get_modular_supported_languages,
        t as modular_t,
    )
  except ImportError:

    def modular_t(key, lang='English (US / UK)', default=None):
      return str(key)

    MODULAR_SUPPORTED_LANGUAGES = SUPPORTED_LANGUAGES.copy()

    def get_modular_supported_languages():
      return MODULAR_SUPPORTED_LANGUAGES.copy()

    def get_modular_language_code(lang='English (US / UK)'):
      return 'en'

    MODULAR_TRANSLATIONS = {}

# ============================================================
# USER LANGUAGE PREFERENCE HELPER
# ============================================================

DEFAULT_LANGUAGE = 'English (US / UK)'

LANGUAGE_CODES = {
    'English (US / UK)': 'en',
    'Mandarin Chinese': 'zh-CN',
    'Spanish': 'es',
    'Hindi': 'hi',
    'Arabic': 'ar',
    'French': 'fr',
    'Portuguese': 'pt',
    'Russian': 'ru',
    'German': 'de',
    'Japanese': 'ja',
    'Korean': 'ko',
    'Italian': 'it',
    'Turkish': 'tr',
    'Dutch': 'nl',
    'Polish': 'pl',
    'Swedish': 'sv',
    'Swahili': 'sw',
}


def get_user_preferred_language(user):
  if session.get('language') in SUPPORTED_LANGUAGES:
    return session['language']

  if user and getattr(user, 'is_authenticated', False):
    preferences = getattr(user, 'preferences_json', None) or {}

    if isinstance(preferences, dict):
      ai_preferences = preferences.get('aiPreferences', {})

      if not isinstance(ai_preferences, dict):
        ai_preferences = {}

      language = preferences.get('language') or ai_preferences.get('aiLanguage')

      if language in SUPPORTED_LANGUAGES:
        return language

  return DEFAULT_LANGUAGE


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

TEMPLATE_DIR = os.path.join(PROJECT_ROOT, 'templates')

premium_app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
)

premium_app.config['SECRET_KEY'] = (
    os.getenv('SECRET_KEY')
    or os.getenv('secret_key')
    or 'cvforge-premium-key-998877'
)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

db_url = (
    os.getenv('DATABASE_URL')
    or os.getenv('database_url')
    or 'sqlite:///:memory:'
)

if db_url.startswith('postgres://'):
  db_url = db_url.replace(
      'postgres://',
      'postgresql+psycopg://',
      1,
  )

elif db_url.startswith('postgresql://') and not db_url.startswith(
    'postgresql+psycopg://'
):
  db_url = db_url.replace(
      'postgresql://',
      'postgresql+psycopg://',
      1,
  )

premium_app.config['SQLALCHEMY_DATABASE_URI'] = db_url
premium_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

premium_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

db.init_app(premium_app)

# ============================================================
# LOGIN MANAGER
# ============================================================

login_manager = LoginManager(premium_app)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access your account settings.'
login_manager.login_message_category = 'info'


# ============================================================
# GLOBAL TRANSLATION CONTEXT PROCESSORS
# ============================================================


@premium_app.context_processor
def inject_global_translations():
  user_language = get_user_preferred_language(
      current_user if current_user.is_authenticated else None
  )

  language_code = LANGUAGE_CODES.get(user_language, 'en')

  def translate(key, default=None):
    if not isinstance(key, str):
      return str(key)

    try:
      val = t(key, user_language)
      if val != key:
        return val

      english_dict = TRANSLATIONS.get(DEFAULT_LANGUAGE, {})
      if key in english_dict:
        return english_dict[key]

      if default is not None:
        return default

      return key

    except Exception as exc:
      premium_app.logger.warning(
          'Legacy translation failed for key %r: %s',
          key,
          type(exc).__name__,
      )
      return default if default is not None else str(key)

  def translate_modular(key, default=None):
    if not isinstance(key, str):
      return str(key)

    try:
      val = modular_t(key, lang=user_language)
      if val != key:
        return val

      english_dict = MODULAR_TRANSLATIONS.get(DEFAULT_LANGUAGE, {})
      if key in english_dict:
        return english_dict[key]

      if default is not None:
        return default

      return key

    except Exception as exc:
      premium_app.logger.warning(
          'Modular translation failed for key %r: %s',
          key,
          type(exc).__name__,
      )
      return default if default is not None else str(key)

  try:
    active_dictionary = TRANSLATIONS.get(user_language, {})
    if not active_dictionary:
      active_dictionary = TRANSLATIONS.get(DEFAULT_LANGUAGE, {})

    javascript_translations = {k: translate(k) for k in active_dictionary}
  except (ImportError, AttributeError, TypeError):
    javascript_translations = {}

  return {
      'current_language': user_language,
      'html_lang_code': language_code,
      'supported_languages': SUPPORTED_LANGUAGES,
      't': translate,
      't_modular': translate_modular,
      'cvforge_translations': javascript_translations,
  }


# ============================================================
# AI API CONFIGURATION & GENERATION HELPERS
# ============================================================


def get_gemini_api_key():
  return os.getenv('GEMINI_API_KEY') or os.getenv('gemini_api_key')


AI_SYSTEM_INSTRUCTIONS = """
You are CVForge AI, a professional resume-writing assistant and executive interview coach.

FLEXIBLE & FACTUAL GUIDELINES:
1. Craft compelling, highly polished professional content tailored to the candidate's target role and supplied skills or draft notes.
2. Support career transitions and multi-disciplinary backgrounds gracefully by connecting transferable skills.
3. Never invent completely fabricated companies or dates, but skillfully synthesize provided details, technical stacks, and experiences.
4. Maintain a professional, executive tone.
5. Follow requested output schemas strictly.
"""


def generate_with_gemini(prompt, api_key=None, max_tokens=2048):
  api_key = api_key or get_gemini_api_key()

  if not api_key:
    raise RuntimeError(
        'Gemini API key is not configured in environment variables.'
    )

  if not genai:
    raise RuntimeError('Google GenAI SDK (google-genai) is not installed.')

  full_prompt = AI_SYSTEM_INSTRUCTIONS + '\n\nUser request:\n' + prompt

  client = genai.Client(api_key=api_key)

  config = (
      types.GenerateContentConfig(max_output_tokens=max_tokens)
      if types
      else None
  )

  response = client.models.generate_content(
      model='gemini-3.8-flash',
      contents=full_prompt,
      config=config,
  )

  generated_text = getattr(response, 'text', None)
  if generated_text and generated_text.strip():
    return generated_text.strip()

  raise RuntimeError('Gemini returned an empty response.')


def generate_ai_text(prompt, max_tokens=2048):
  gemini_key = get_gemini_api_key()

  if not gemini_key:
    raise RuntimeError('GEMINI_API_KEY environment variable is missing.')

  try:
    result = generate_with_gemini(prompt, gemini_key, max_tokens=max_tokens)
    return result
  except Exception as exc:
    print(f'GEMINI GENERATION FAILED: {type(exc).__name__}: {exc}')
    raise RuntimeError(f'Gemini generation failed: {type(exc).__name__}: {exc}')


# ============================================================
# PADDLE CONFIGURATION & PRICING STRUCTURE
# ============================================================

PADDLE_API_KEY = os.getenv('PADDLE_API_KEY') or os.getenv('paddle_api_key')
PADDLE_WEBHOOK_SECRET_KEY = os.getenv('PADDLE_WEBHOOK_SECRET_KEY') or os.getenv(
    'paddle_webhook_secret_key'
)
PADDLE_ENV = os.getenv('PADDLE_ENV', 'sandbox')

# Updated Pricing Structure Mappings & Price IDs
PADDLE_PRO_PRICE_ID = os.getenv('PADDLE_PRO_PRICE_ID', 'pri_pro_monthly_1799')
PADDLE_ELITE_PRICE_ID = os.getenv(
    'PADDLE_ELITE_PRICE_ID', 'pri_expert_monthly_4399'
)

PRICE_MAP = {
    # Monthly Subscriptions ($17.99 Pro, $43.99 Elite)
    PADDLE_PRO_PRICE_ID: {'type': 'sub', 'tier': 'pro', 'credits': 130},
    PADDLE_ELITE_PRICE_ID: {'type': 'sub', 'tier': 'elite', 'credits': 360},
    # 7-Day One-Time Pass ($7.99)
    'pri_pass_7day_799': {
        'type': 'pass',
        'tier': 'pro',
        'credits': 60,
        'days': 7,
    },
    # One-Time Credit Top-Up Packs ($2.99, $9.99, $24.99)
    'pri_topup_10_299': {'type': 'topup', 'credits': 10},
    'pri_topup_50_999': {'type': 'topup', 'credits': 50},
    'pri_topup_150_2499': {'type': 'topup', 'credits': 150},
}

# Feature Consumption Weights
FEATURE_RULES = {
    'ats_optimizer': {'tier': 'free', 'cost': 3},
    'cover_letter': {'tier': 'pro', 'cost': 3},
    'cold_outreach': {'tier': 'pro', 'cost': 2},
    'portal_qa': {'tier': 'pro', 'cost': 3},
    'linkedin_optimizer': {'tier': 'pro', 'cost': 4},
    'interview_coach': {'tier': 'pro', 'cost': 5},
    'pdf_studio': {'tier': 'pro', 'cost': 5},
    'salary_negotiator': {'tier': 'elite', 'cost': 8},
    'application_copilot': {'tier': 'pro', 'cost': 9},
}

# ============================================================
# LOGIN MANAGER USER LOADER
# ============================================================


@login_manager.user_loader
def load_user(user_id):
  if not user_id:
    return None

  try:
    return db.session.get(User, user_id)
  except Exception as exc:
    print(f'User loader error: {exc}')
    return None


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

verification_codes = {}


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''

    if not email or not password:
      flash('Please enter both an email address and a password.', 'error')
      return redirect(url_for('auth.register'))

    if len(password) < 8:
      flash('Your password must be at least 8 characters long.', 'error')
      return redirect(url_for('auth.register'))

    if User.query.filter_by(email=email).first():
      flash(
          'An account with this email address already exists. Please log in.',
          'error',
      )
      return redirect(url_for('auth.register'))

    try:
      now = datetime.utcnow()
      user = User(
          id=str(uuid.uuid4()),
          email=email,
          password_hash=generate_password_hash(password),
          created_at=now,
          updated_at=now,
          is_premium=False,
          subscription_status='free',
          monthly_cv_generations=0,
          ai_credits_remaining=15,  # Updated starting credit balance
          preferences_json={},
      )

      db.session.add(user)
      db.session.commit()
      login_user(user)
      return redirect('/dashboard')

    except Exception as exc:
      db.session.rollback()
      print(f'Registration DB Error: {exc}')
      flash(
          'We encountered an issue creating your account. Please try again in'
          ' a few moments.',
          'error',
      )
      return redirect(url_for('auth.register'))

  return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''

    user = User.query.filter_by(email=email).first()

    if (
        user
        and user.password_hash
        and check_password_hash(user.password_hash, password)
    ):
      login_user(user)
      return redirect('/dashboard')

    flash(
        'Incorrect email address or password. Please verify your credentials'
        ' and try again.',
        'error',
    )
    return redirect(url_for('auth.login'))

  return render_template('auth/login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
  if request.method == 'GET':
    return render_template('auth/forgot_password.html')

  data = request.get_json(silent=True) or {}
  email = (data.get('email') or '').strip().lower()

  if not email:
    return (
        jsonify({'error': 'Please enter your email address to proceed.'}),
        400,
    )

  user = User.query.filter_by(email=email).first()
  if not user:
    return jsonify({
        'message': (
            'If an account exists with this email, a verification code has'
            ' been generated.'
        )
    }), 200

  code = f'{random.randint(100000, 999999)}'
  verification_codes[email] = code

  return jsonify({
      'message': 'A verification code has been generated successfully.',
      'code': code,
  }), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
  data = request.get_json(silent=True) or {}
  email = (data.get('email') or '').strip().lower()
  code = (data.get('code') or '').strip()
  new_password = data.get('newPassword') or ''

  if not email or not code or not new_password:
    return jsonify({'error': 'Please fill in all required fields.'}), 400

  saved_code = verification_codes.get(email)
  if not saved_code or saved_code != code:
    return jsonify({
        'error': 'The verification code provided is invalid or has expired.'
    }), 400

  if len(new_password) < 8:
    return jsonify({
        'error': 'Your new password must be at least 8 characters long.'
    }), 400

  user = User.query.filter_by(email=email).first()
  if not user:
    return jsonify({
        'error': 'Account not found. Please verify your email address.'
    }), 404

  try:
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    verification_codes.pop(email, None)
    return (
        jsonify({'message': 'Your password has been updated successfully.'}),
        200,
    )
  except Exception as exc:
    db.session.rollback()
    print(f'Reset password DB error: {exc}')
    return jsonify({
        'error': (
            'Unable to reset password at this time. Please try again shortly.'
        )
    }), 500


@auth_bp.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect('/')


premium_app.register_blueprint(auth_bp)

# ============================================================
# PUBLIC ROOT & SETTINGS ROUTES
# ============================================================


@premium_app.route('/')
def landing():
  requested_lang = request.args.get('lang')
  if requested_lang and requested_lang in SUPPORTED_LANGUAGES:
    session['language'] = requested_lang

  try:
    return render_template('landing.html')
  except Exception:
    return render_template('index.html')


@premium_app.route('/settings')
def public_settings():
  if current_user and getattr(current_user, 'is_authenticated', False):
    return redirect(url_for('dashboard.account'))
  return redirect(url_for('auth.login'))


@premium_app.route('/dashboard/settings')
@login_required
def dashboard_settings_redirect():
  return redirect(url_for('dashboard.account'))


# ============================================================
# EDITOR, PRICING & PREVIEW ROUTES
# ============================================================


@premium_app.route('/editor')
@login_required
def editor():
  resume_id = request.args.get('id')
  resume = None

  if resume_id:
    resume = Resume.query.filter_by(
        id=resume_id, user_id=current_user.id
    ).first()

  user_prefs = getattr(current_user, 'preferences_json', None) or {}
  pdf_settings = (
      user_prefs.get('pdf_settings', {}) if isinstance(user_prefs, dict) else {}
  )

  raw_template = request.args.get('template') or (
      resume.template_used
      if resume and getattr(resume, 'template_used', None)
      else pdf_settings.get('template_id', 'exec_minimalist')
  )
  active_template = raw_template.replace('-', '_')

  active_accent = (
      resume.accent_color
      if resume and getattr(resume, 'accent_color', None)
      else pdf_settings.get('accent_color', '#02353C')
  )

  try:
    return render_template(
        'editor.html',
        resume=resume,
        user=current_user,
        active_template=active_template,
        active_accent=active_accent,
    )
  except Exception:
    return render_template(
        'index.html',
        resume=resume,
        user=current_user,
        active_template=active_template,
        active_accent=active_accent,
    )


@premium_app.route('/builder')
def builder_redirect():
  return redirect('/editor')


@premium_app.route('/pricing')
def pricing():
  try:
    return render_template('pricing.html', user=current_user)
  except Exception:
    return render_template('landing.html', user=current_user)


@premium_app.route('/preview')
@login_required
def preview():
  resume_id = request.args.get('id')
  resume = None
  if resume_id:
    resume = Resume.query.filter_by(
        id=resume_id, user_id=current_user.id
    ).first()

  user_prefs = getattr(current_user, 'preferences_json', None) or {}
  pdf_settings = (
      user_prefs.get('pdf_settings', {}) if isinstance(user_prefs, dict) else {}
  )

  raw_template = request.args.get('template') or (
      resume.template_used
      if resume and getattr(resume, 'template_used', None)
      else pdf_settings.get('template_id', 'exec_minimalist')
  )
  active_template = raw_template.replace('-', '_')

  active_accent = (
      resume.accent_color
      if resume and getattr(resume, 'accent_color', None)
      else pdf_settings.get('accent_color', '#02353C')
  )

  return render_template(
      'preview.html',
      resume=resume,
      user=current_user,
      active_template=active_template,
      active_accent=active_accent,
      pdf_settings=pdf_settings,
  )


# ============================================================
# CVFORGE PRO CAREER SUITE FEATURE ROUTES
# ============================================================


@premium_app.route('/ats')
@login_required
def ats_optimizer():
  resumes = Resume.query.filter_by(user_id=current_user.id).all()
  return render_template(
      'dashboard/ats_optimizer.html', resumes=resumes, user=current_user
  )


@premium_app.route('/cover-letter')
@login_required
def cover_letter():
  resumes = Resume.query.filter_by(user_id=current_user.id).all()
  try:
    saved_cover_letters = (
        CoverLetter.query.filter_by(user_id=current_user.id)
        .order_by(CoverLetter.created_at.desc())
        .all()
    )
  except Exception as exc:
    db.session.rollback()
    premium_app.logger.warning('CoverLetter table query failed: %s', exc)
    try:
      db.create_all()
      saved_cover_letters = (
          CoverLetter.query.filter_by(user_id=current_user.id)
          .order_by(CoverLetter.created_at.desc())
          .all()
      )
    except Exception as inner_exc:
      premium_app.logger.warning(
          'Failed to auto-create CoverLetter table: %s', inner_exc
      )
      saved_cover_letters = []

  return render_template(
      'dashboard/cover_letter.html',
      resumes=resumes,
      cover_letters=saved_cover_letters,
      user=current_user,
  )


@premium_app.route('/interview')
@login_required
def interview_prep():
  return render_template('dashboard/interview_prep.html', user=current_user)


@premium_app.route('/tracker')
@login_required
def job_tracker():
  return render_template('dashboard/tracker.html', user=current_user)


@premium_app.route('/matcher')
@login_required
def keyword_matcher():
  resumes = Resume.query.filter_by(user_id=current_user.id).all()
  return render_template(
      'dashboard/keyword_matcher.html', resumes=resumes, user=current_user
  )


@premium_app.route('/outreach')
@login_required
def cold_outreach():
  resumes = Resume.query.filter_by(user_id=current_user.id).all()
  return render_template('outreach.html', resumes=resumes, user=current_user)


@premium_app.route('/salary-negotiator')
@login_required
def salary_negotiator():
  resumes = Resume.query.filter_by(user_id=current_user.id).all()
  return render_template(
      'salary_negotiator.html', resumes=resumes, user=current_user
  )


@premium_app.route('/portal-qa')
@login_required
def portal_qa_page():
  resumes = Resume.query.filter_by(user_id=current_user.id).all()
  return render_template('portal_qa.html', resumes=resumes, user=current_user)


@premium_app.route('/linkedin')
@login_required
def linkedin_optimizer():
  resumes = Resume.query.filter_by(user_id=current_user.id).all()
  return render_template(
      'dashboard/linkedin_optimizer.html', resumes=resumes, user=current_user
  )


@premium_app.route('/pdf-studio', methods=['GET', 'POST'])
@login_required
def pdf_studio():
  resume_id = request.args.get('resume_id') or request.form.get('resume_id')

  user_prefs = getattr(current_user, 'preferences_json', None) or {}
  if not isinstance(user_prefs, dict):
    user_prefs = {}

  pdf_settings = user_prefs.get(
      'pdf_settings',
      {
          'template_id': 'exec_minimalist',
          'accent_color': '#02353C',
          'font_pairing': 'helvetica',
          'line_spacing': 'normal',
          'target_action': 'editor',
      },
  )

  if request.method == 'POST':
    template_id = (
        request.form.get('template_id', 'exec_minimalist')
    ).replace('-', '_')
    accent_color = request.form.get('accent_color', '#02353C')
    font_pairing = request.form.get('font_pairing', 'helvetica')
    line_spacing = request.form.get('line_spacing', 'normal')

    updated_settings = {
        'template_id': template_id,
        'accent_color': accent_color,
        'font_pairing': font_pairing,
        'line_spacing': line_spacing,
    }

    user_prefs['pdf_settings'] = updated_settings
    current_user.preferences_json = user_prefs
    flag_modified(current_user, 'preferences_json')

    if resume_id:
      resume = Resume.query.filter_by(
          id=resume_id, user_id=current_user.id
      ).first()
      if resume:
        resume.template_used = template_id
        resume.accent_color = accent_color

    try:
      db.session.commit()
      session['pdf_settings'] = updated_settings
      flash('PDF Template settings saved!', 'success')
    except Exception as exc:
      db.session.rollback()
      premium_app.logger.error('Failed to save settings: %s', exc)

    if resume_id:
      return redirect(url_for('preview', id=resume_id, template=template_id))
    else:
      return redirect(url_for('editor', template=template_id))

  return render_template(
      'dashboard/pdf_templates.html',
      settings=pdf_settings,
      resume_id=resume_id,
      user=current_user,
  )


@premium_app.route('/support')
@login_required
def priority_support():
  return render_template('dashboard/priority_support.html', user=current_user)


# ============================================================
# LINKEDIN OPTIMIZER API ENDPOINTS
# ============================================================


@premium_app.route('/api/fetch-job-keywords', methods=['POST'])
@login_required
def fetch_job_keywords():
  data = request.get_json(silent=True) or {}
  job_url = (data.get('url') or '').strip()

  if not job_url:
    return jsonify({'error': 'Please provide a valid job posting URL.'}), 400

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      ),
  }

  try:
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
      response = client.get(job_url, headers=headers)
      if response.status_code != 200:
        return (
            jsonify({'error': 'Unable to access the specified job URL.'}),
            400,
        )

      soup = BeautifulSoup(response.text, 'html.parser')
      for tag in soup(
          ['script', 'style', 'noscript', 'header', 'footer', 'nav']
      ):
        tag.decompose()

      raw_text = soup.get_text(separator=' ')
      clean_text = re.sub(r'\s+', ' ', raw_text).strip()[:4000]

      prompt = f"""
Extract the top 8 to 12 critical technical and professional keywords, required skills, and core domain terms from this job description text.
Return ONLY a concise, comma-separated list of keywords.

Job Description Text:
{clean_text}
"""
      extracted_keywords = generate_ai_text(prompt, max_tokens=300)
      return jsonify({'success': True, 'keywords': extracted_keywords}), 200

  except Exception as exc:
    premium_app.logger.error('Error fetching job keywords: %s', exc)
    return (
        jsonify({'error': 'Failed to extract keywords from provided URL.'}),
        500,
    )


@premium_app.route('/api/generate-linkedin', methods=['POST'])
@login_required
def generate_linkedin_assets():
  target_keywords = (request.form.get('target_keywords') or '').strip()
  profile_goal = (
      request.form.get('profile_goal') or 'recruiter_search'
  ).strip()
  resume_id = request.form.get('resume_id')

  cv_text = ''

  if resume_id:
    resume_obj = Resume.query.filter_by(
        id=resume_id, user_id=current_user.id
    ).first()
    if resume_obj and isinstance(resume_obj.content_json, dict):
      cv_text = json.dumps(resume_obj.content_json, ensure_ascii=False)

  if not cv_text and 'file' in request.files:
    file = request.files['file']
    if file and file.filename:
      filename = secure_filename(file.filename)
      file_bytes = file.read()
      if filename.lower().endswith('.pdf'):
        try:
          import pypdf

          pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
          cv_text = '\n'.join(
              [p.extract_text() or '' for p in pdf_reader.pages]
          )
        except Exception:
          cv_text = file_bytes.decode('utf-8', errors='ignore')
      else:
        cv_text = file_bytes.decode('utf-8', errors='ignore')

  if not cv_text:
    return (
        jsonify({'error': 'Please provide a source CV or upload a CV file.'}),
        400,
    )

  preferred_language = get_user_preferred_language(current_user)

  prompt = f"""
You are an executive personal branding strategist and LinkedIn SEO specialist.

TASK:
Optimize the candidate's CV for LinkedIn based on target keywords and career goals.

Candidate CV Content:
{cv_text}

Target Role & Keywords:
{target_keywords or 'High-value industry technical skills'}

Optimization Goal:
{profile_goal}

Preferred Language:
{preferred_language}

REQUIREMENTS:
1. "headlines": Provide 3 distinct, highly engaging LinkedIn profile headlines (under 220 characters each) optimized for recruiter search.
2. "about": Write a compelling, 3 to 4 paragraph LinkedIn About section (Summary) incorporating key skills, achievements, and call to action.
3. "experience": Write 3 impactful experience bullet points tailored for LinkedIn profile experience entries.

Output MUST be strictly valid JSON matching this structure:
{{
  "headlines": [
    "Headline option 1...",
    "Headline option 2...",
    "Headline option 3..."
  ],
  "about": "Full LinkedIn About section copy...",
  "experience": [
    "Experience bullet 1...",
    "Experience bullet 2...",
    "Experience bullet 3..."
  ]
}}
"""

  try:
    raw_response = generate_ai_text(prompt, max_tokens=1800)

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    result = json.loads(clean_json_str.strip())
    return jsonify(result), 200

  except Exception as exc:
    premium_app.logger.error('LinkedIn generation failed: %s', exc)
    return (
        jsonify({'error': 'Unable to generate LinkedIn assets at this time.'}),
        500,
    )


# ============================================================
# INTERVIEW PRACTICE & AI COACH API ENDPOINTS
# ============================================================


@premium_app.route('/api/interview/generate', methods=['POST'])
@login_required
def generate_interview_questions():
  data = request.get_json(silent=True) or {}
  target_role = (data.get('target_role') or 'Software Engineer').strip()
  persona = (data.get('persona') or 'tech_lead').strip()
  category = (data.get('category') or 'behavioral').strip()
  job_context = (data.get('job_context') or '').strip()

  preferred_language = get_user_preferred_language(current_user)

  prompt = f"""
You are an expert interview coach conducting an interview for the target position: "{target_role}".
Interviewer Persona: {persona}
Focus Category: {category}
Language: {preferred_language}

Job Context / Requirements:
{job_context or 'Standard industry expectations for this position.'}

Generate 3 challenging, highly relevant interview practice questions tailored to this role and persona.
Output MUST be strictly valid JSON matching this schema:
{{
  "questions": [
    {{
      "category": "{category.upper()} • {target_role.upper()}",
      "question_text": "First interview question..."
    }},
    ...
  ]
}}
"""

  try:
    raw_response = generate_ai_text(prompt, max_tokens=1024)

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    result = json.loads(clean_json_str.strip())
    return jsonify(result), 200

  except Exception as exc:
    premium_app.logger.error('Interview question generation error: %s', exc)
    return (
        jsonify({
            'error': (
                'Unable to generate interview questions. Please verify your AI'
                ' configuration.'
            )
        }),
        500,
    )


@premium_app.route('/api/interview/evaluate', methods=['POST'])
@login_required
def evaluate_interview_answer():
  data = request.get_json(silent=True) or {}
  user_answer = (data.get('answer') or '').strip()
  question_text = (data.get('question') or '').strip()

  if not user_answer:
    return (
        jsonify({
            'error': 'Please provide an answer before requesting feedback.'
        }),
        400,
    )

  preferred_language = get_user_preferred_language(current_user)

  prompt = f"""
You are an executive career coach evaluating a candidate's response to an interview question using the STAR method (Situation, Task, Action, Result).

Question: "{question_text}"
Candidate Response: "{user_answer}"
Output Language: {preferred_language}

Provide constructive feedback.
Output MUST be strictly valid JSON matching this schema:
{{
  "strength": "One concise sentence detailing what the candidate executed effectively.",
  "improvement": "One actionable sentence advising how to optimize the response (e.g., metrics, STAR alignment).",
  "rewrite": "An executive-level optimized version of the candidate's response."
}}
"""

  try:
    raw_response = generate_ai_text(prompt, max_tokens=1024)

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    result = json.loads(clean_json_str.strip())
    return jsonify(result), 200

  except Exception as exc:
    premium_app.logger.error(
        'Interview evaluation critical error: %s',
        type(exc).__name__,
        exc_info=True,
    )
    return jsonify({'error': f'Evaluation error: {str(exc)}'}), 500


# ============================================================
# SAVE & DELETE RESUME ENDPOINTS
# ============================================================


@premium_app.route('/api/v1/resumes/save', methods=['POST'])
@login_required
def save_resume():
  if request.is_json:
    data = request.get_json(silent=True) or {}
  else:
    data = request.form.to_dict()

  if not isinstance(data, dict):
    return jsonify({'error': 'Invalid resume data structure.'}), 400

  title = (data.get('title') or 'My CV').strip() or 'My CV'

  content_data = {
      'target_role': data.get('target_role', ''),
      'full_name': data.get('full_name', ''),
      'email': data.get('email', ''),
      'phone': data.get('phone', ''),
      'location': data.get('location', ''),
      'linkedin': data.get('linkedin', ''),
      'portfolio': data.get('portfolio', ''),
      'summary': data.get('summary', ''),
      'company': data.get('company', ''),
      'job_title': data.get('job_title', ''),
      'job_location': data.get('job_location', ''),
      'job_dates': data.get('job_dates', ''),
      'experience_bullets': data.get('experience_bullets', ''),
      'education_degree': data.get('education_degree', ''),
      'education_school': data.get('education_school', ''),
      'education_dates': data.get('education_dates', ''),
      'education_honors': data.get('education_honors', ''),
      'skills_tech': data.get('skills_tech', ''),
      'skills_soft': data.get('skills_soft', ''),
      'certifications': data.get('certifications', ''),
      'projects': data.get('projects', ''),
      'languages': data.get('languages', ''),
  }

  resume_id = request.args.get('id') or data.get('id') or str(uuid.uuid4())
  resume = db.session.get(Resume, resume_id)

  user_prefs = getattr(current_user, 'preferences_json', None) or {}
  pdf_settings = (
      user_prefs.get('pdf_settings', {}) if isinstance(user_prefs, dict) else {}
  )

  raw_chosen_template = data.get('template_id') or pdf_settings.get(
      'template_id', 'exec_minimalist'
  )
  chosen_template = raw_chosen_template.replace('-', '_')
  chosen_accent = data.get('accent_color') or pdf_settings.get(
      'accent_color', '#02353C'
  )

  if resume and str(resume.user_id) == str(current_user.id):
    resume.title = title
    resume.content_json = content_data
    resume.template_used = chosen_template
    resume.accent_color = chosen_accent
    resume.updated_at = datetime.utcnow()
  else:
    if resume:
      return (
          jsonify(
              {'error': 'You do not have permission to modify this document.'}
          ),
          403,
      )

    resume = Resume(
        id=resume_id,
        user_id=current_user.id,
        title=title,
        content_json=content_data,
        optimized_json={},
        original_text='',
        template_used=chosen_template,
        accent_color=chosen_accent,
        sidebar_color=chosen_accent,
        updated_at=datetime.utcnow(),
    )
    db.session.add(resume)

  try:
    db.session.commit()
    if (
        request.is_json
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    ):
      return (
          jsonify({
              'status': 'success',
              'redirect_url': f'/preview?id={resume.id}',
              'resume_id': resume.id,
          }),
          200,
      )

    flash('Resume saved successfully!', 'success')
    return redirect(f'/preview?id={resume.id}')

  except Exception as exc:
    db.session.rollback()
    print(f'Save Resume Error: {exc}')
    if request.is_json:
      return (
          jsonify(
              {'error': 'Unable to save resume changes. Please try again.'}
          ),
          500,
      )

    flash('Unable to save resume changes. Please try again.', 'error')
    return redirect(f'/editor?id={resume_id}')


@premium_app.route('/api/v1/resumes/delete/<resume_id>', methods=['DELETE'])
@login_required
def delete_resume(resume_id):
  resume = Resume.query.filter_by(
      id=resume_id, user_id=current_user.id
  ).first()
  if not resume:
    return (
        jsonify({'error': 'Resume document not found or access denied.'}),
        404,
    )

  try:
    db.session.delete(resume)
    db.session.commit()
    return (
        jsonify({'success': True, 'message': 'Resume deleted successfully.'}),
        200,
    )
  except Exception as exc:
    db.session.rollback()
    print(f'Error deleting resume: {exc}')
    return jsonify({'error': 'Unable to delete resume at this time.'}), 500


# ============================================================
# JOB TRACKER API BLUEPRINT
# ============================================================

tracker_api_bp = Blueprint(
    'tracker_api', __name__, url_prefix='/api/v1/tracker'
)


@tracker_api_bp.route('', methods=['GET'])
@login_required
def get_job_applications():
  try:
    apps = JobApplication.query.filter_by(user_id=current_user.id).all()
    return (
        jsonify({
            'success': True,
            'applications': [
                {
                    'id': app.id,
                    'company_name': getattr(app, 'company_name', ''),
                    'role_title': getattr(app, 'role_title', ''),
                    'salary': getattr(app, 'salary', ''),
                    'status': getattr(app, 'status', 'saved'),
                    'job_url': getattr(app, 'job_url', ''),
                    'updated_at': (
                        app.updated_at.isoformat()
                        if getattr(app, 'updated_at', None)
                        else None
                    ),
                }
                for app in apps
            ],
        }),
        200,
    )
  except Exception as exc:
    print(f'Error fetching tracker apps: {exc}')
    return jsonify({'error': 'Unable to fetch job application records.'}), 500


@tracker_api_bp.route('', methods=['POST'])
@login_required
def create_job_application():
  data = request.get_json(silent=True) or {}
  company_name = (data.get('company_name') or '').strip()
  role_title = (data.get('role_title') or '').strip()
  salary = (data.get('salary') or '').strip()
  status = (data.get('status') or 'saved').strip()
  job_url = (data.get('job_url') or '').strip()

  if not company_name or not role_title:
    return (
        jsonify({
            'success': False,
            'error': 'Company name and job title are required.',
        }),
        400,
    )

  try:
    new_app = JobApplication(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_name=company_name,
        role_title=role_title,
        salary=salary,
        status=status,
        job_url=job_url,
        updated_at=datetime.utcnow(),
    )
    db.session.add(new_app)
    db.session.commit()
    return (
        jsonify({
            'success': True,
            'message': 'Application tracked successfully!',
            'id': new_app.id,
        }),
        201,
    )
  except Exception as exc:
    db.session.rollback()
    print(
        f'CRITICAL DB Error creating job application:'
        f' {type(exc).__name__}: {exc}'
    )
    return (
        jsonify({
            'success': False,
            'error': 'Unable to save job tracking information.',
        }),
        500,
    )


@tracker_api_bp.route('/<app_id>', methods=['DELETE'])
@login_required
def delete_job_application(app_id):
  try:
    app = JobApplication.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first()
    if not app:
      return jsonify({'error': 'Application record not found.'}), 404
    db.session.delete(app)
    db.session.commit()
    return (
        jsonify(
            {'success': True, 'message': 'Application removed from tracker.'}
        ),
        200,
    )
  except Exception as exc:
    db.session.rollback()
    print(f'Error deleting application: {exc}')
    return jsonify({'error': 'Unable to delete application record.'}), 500


premium_app.register_blueprint(tracker_api_bp)

# ============================================================
# DEVELOPER ACCESS & AI GENERATION ENDPOINTS
# ============================================================

DEVELOPER_EMAILS = {
    'subhnllha@gmail.com',
}


def is_developer_user(user):
  email = (getattr(user, 'email', '') or '').strip().lower()
  return email in DEVELOPER_EMAILS


def has_premium_access(user):
  return is_developer_user(user) or bool(getattr(user, 'is_premium', False))


@premium_app.route('/api/v1/ai/generate-field', methods=['POST'])
@login_required
def generate_ai_field():
  is_developer = is_developer_user(current_user)
  is_premium_user = has_premium_access(current_user)

  credits_remaining = int(
      getattr(current_user, 'ai_credits_remaining', 0) or 0
  )

  if not is_premium_user and credits_remaining <= 0:
    return (
        jsonify({
            'error': (
                'You have used all available AI generation credits. Please'
                ' upgrade or refill credits to continue.'
            ),
            'code': 'CREDIT_INSUFFICIENCY',
            'button_action': 'REFILL_CREDIT',
        }),
        403,
    )

  data = request.get_json(silent=True)
  if not isinstance(data, dict):
    return jsonify({'error': 'A valid JSON request payload is required.'}), 400

  field_type = (data.get('field_type') or 'summary').strip().lower()
  supported_fields = {'summary', 'experience', 'project', 'skills'}

  if field_type not in supported_fields:
    return (
        jsonify({
            'error': 'Unsupported resume section specified.',
            'supported_fields': sorted(supported_fields),
        }),
        400,
    )

  target_role = (data.get('target_role') or '').strip()
  job_title = (data.get('job_title') or '').strip()
  full_name = (data.get('full_name') or '').strip()
  skills = (data.get('skills') or '').strip()
  current_input = (data.get('current_input') or '').strip()
  source_cv = (data.get('source_cv') or '').strip()
  job_description = (data.get('job_description') or '').strip()

  has_candidate_content = any(
      [full_name, skills, current_input, source_cv, target_role]
  )
  if not has_candidate_content:
    return (
        jsonify({
            'error': (
                'Please specify a target role or provide basic CV details'
                ' before generating AI content.'
            ),
            'code': 'MISSING_DETAILS',
            'button_action': 'FILL_DETAILS',
        }),
        400,
    )

  preferred_language = get_user_preferred_language(current_user)

  context_details = []
  if full_name:
    context_details.append(f'Candidate name supplied by user: {full_name}')
  if target_role:
    context_details.append(f'Target role: {target_role}')
  if job_title:
    context_details.append(f'Job title supplied by user: {job_title}')
  if skills:
    context_details.append(f'Skills explicitly supplied by user: {skills}')
  if current_input:
    context_details.append(f'Existing user draft or notes:\n{current_input}')
  if source_cv:
    context_details.append(f'Extracted source CV content:\n{source_cv}')
  if job_description:
    context_details.append(f'Target job description:\n{job_description}')

  context_str = '\n\n'.join(context_details)

  lang_directive = (
      'CRITICAL REQUIREMENT: Write ALL generated text, phrases, and'
      f' descriptions strictly and exclusively in {preferred_language}.'
  )

  if field_type == 'summary':
    prompt = (
        'Write a concise, professional resume summary tailored to the target'
        f' role ({target_role}) using the candidate information supplied'
        f' below.\n\n{lang_directive}\n\nCandidate'
        f' information:\n{context_str}\n\nRequirements:\n- Highlight core'
        ' strengths, technical skills, and background.\n- Write the entire'
        f' output in {preferred_language}.\n- Seamlessly accommodate career'
        ' transitions or multi-disciplinary profiles.\n- Return only the'
        ' professional summary text without commentary or questions.'
    )
  elif field_type == 'experience':
    prompt = (
        "Improve and polish the candidate's professional experience bullet"
        f' points for the target role ({target_role}).\n\n{lang_directive}\n\nCandidate'
        f' information:\n{context_str}\n\nRequirements:\n- Enhance clarity,'
        ' professional tone, and ATS keyword alignment.\n- Write the entire'
        f' output in {preferred_language}.\n- Return clear bullet points'
        " beginning with '-'."
    )
  elif field_type == 'project':
    prompt = (
        'Write a compelling project description highlighting technical'
        f' implementation and impact for the target role ({target_role}).\n\n{lang_directive}\n\nCandidate'
        f' information:\n{context_str}\n\nRequirements:\n- Focus on technical'
        ' stack, architecture, and deliverables.\n- Write the entire output in'
        f' {preferred_language}.\n- Return concise paragraph or bullet points.'
    )
  else:
    prompt = (
        "Organize and format the candidate's professional and technical skills"
        f' tailored to the target role ({target_role}).\n\n{lang_directive}\n\nCandidate'
        f' information:\n{context_str}\n\nRequirements:\n- Group or list clean,'
        f' industry-standard skills in {preferred_language}.\n- Return a'
        ' comma-separated list or clean categorized text without introductory'
        ' text.'
    )

  try:
    generated_text = generate_ai_text(prompt, max_tokens=1024)
  except Exception as exc:
    err_msg = str(exc).lower()

    if any(
        keyword in err_msg
        for keyword in [
            'resource_exhausted',
            'quota exceeded',
            'rate limit',
            '429',
            'insufficient_quota',
        ]
    ):
      return (
          jsonify({
              'error': (
                  'The AI service is experiencing high request volume. Please'
                  ' wait a moment and try again.'
              ),
              'code': 'AI_PROVIDER_QUOTA_EXCEEDED',
              'button_action': 'TRY_AGAIN',
          }),
          503,
      )

    if any(
        keyword in err_msg
        for keyword in [
            'connection',
            'timeout',
            'network',
            'socket',
            'unreachable',
        ]
    ):
      return (
          jsonify({
              'error': (
                  'A network connection error occurred while contacting AI'
                  ' Assist. Please check your connection and try again.'
              ),
              'code': 'NETWORK_ERROR',
              'button_action': 'TRY_AGAIN',
          }),
          503,
      )

    return (
        jsonify({
            'error': (
                'AI Assist is temporarily unavailable. Please try again'
                ' shortly.'
            ),
            'code': 'AI_SERVICE_UNAVAILABLE',
            'button_action': 'TRY_AGAIN',
        }),
        503,
    )

  if not is_premium_user:
    try:
      current_credits = int(
          getattr(current_user, 'ai_credits_remaining', 0) or 0
      )
      if current_credits <= 0:
        return (
            jsonify({
                'error': (
                    'No AI generation credits remaining. Please upgrade or top'
                    ' up.'
                ),
                'code': 'CREDIT_INSUFFICIENCY',
                'button_action': 'REFILL_CREDIT',
            }),
            403,
        )

      current_user.ai_credits_remaining = current_credits - 1
      db.session.commit()
      credits_remaining = current_user.ai_credits_remaining
    except Exception as exc:
      db.session.rollback()
      print(f'AI credit deduction error: {exc}')
      return (
          jsonify({
              'error': (
                  'Unable to update generation credits. Please check your'
                  ' account status.'
              ),
              'result': generated_text,
          }),
          500,
      )
  else:
    credits_remaining = int(
        getattr(current_user, 'ai_credits_remaining', 0) or 0
    )

  return (
      jsonify({
          'result': generated_text,
          'field_type': field_type,
          'credits_remaining': credits_remaining,
          'premium': is_premium_user,
      }),
      200,
  )


# ============================================================
# DASHBOARD ROUTES
# ============================================================

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('')
@login_required
def home():
  try:
    user_resumes = Resume.query.filter_by(user_id=current_user.id).all()
    for resume in user_resumes:
      if isinstance(resume.content_json, str):
        try:
          resume.content_json = json.loads(resume.content_json)
        except Exception:
          resume.content_json = {}
      elif resume.content_json is None:
        resume.content_json = {}

    return render_template(
        'dashboard/index.html', resumes=user_resumes, user=current_user
    )
  except Exception as exc:
    print(f'Dashboard Route Error: {exc}')
    return render_template(
        'dashboard/index.html', resumes=[], user=current_user
    )


@dashboard_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
  if request.method == 'POST':
    new_email = (request.form.get('email') or '').strip().lower()
    new_password = request.form.get('password') or ''

    if new_email and new_email != getattr(current_user, 'email', None):
      existing_user = User.query.filter_by(email=new_email).first()
      if existing_user:
        flash('This email address is already registered.', 'error')
      else:
        current_user.email = new_email
        flash('Your email address has been updated successfully.', 'success')

    if new_password:
      if len(new_password) < 8:
        flash('Your new password must be at least 8 characters long.', 'error')
        return redirect(url_for('dashboard.account'))

      current_user.password_hash = generate_password_hash(new_password)
      flash('Your password has been updated successfully.', 'success')

    try:
      db.session.commit()
    except Exception as exc:
      db.session.rollback()
      print(f'Account update error: {exc}')
      flash('Account updates could not be saved at this time.', 'error')

    return redirect(url_for('dashboard.account'))

  try:
    return render_template('settings.html', user=current_user)
  except Exception:
    return render_template('dashboard/account.html', user=current_user)


premium_app.register_blueprint(dashboard_bp)

# ============================================================
# SETTINGS API BLUEPRINT
# ============================================================

settings_api_bp = Blueprint(
    'settings_api', __name__, url_prefix='/api/v1/settings'
)


@settings_api_bp.route('', methods=['GET'])
@login_required
def get_settings():
  prefs = current_user.preferences_json or {}
  profile_prefs = prefs.get('profile', {})

  return (
      jsonify({
          'profile': {
              'fullName': (
                  getattr(current_user, 'full_name', '')
                  or profile_prefs.get('fullName', '')
              ),
              'email': current_user.email,
              'targetTitle': profile_prefs.get('targetTitle', ''),
              'phone': profile_prefs.get('phone', ''),
              'linkedin': profile_prefs.get('linkedin', ''),
              'avatarUrl': getattr(current_user, 'avatar_url', '') or '',
          },
          'globalLanguage': (
              prefs.get('language')
              or (
                  prefs.get('aiPreferences', {}).get('aiLanguage')
                  if isinstance(prefs.get('aiPreferences'), dict)
                  else None
              )
              or 'English (US / UK)'
          ),
          'aiPreferences': prefs.get(
              'aiPreferences',
              {
                  'aiTone': 'Executive & Leadership',
                  'aiLayout': 'Modern ATS Minimalist',
                  'atsRigor': 'Balanced Match (Recommended)',
              },
          ),
          'trackerSettings': prefs.get(
              'trackerSettings',
              {
                  'currency': 'USD ($)',
                  'trackerLayout': 'Kanban Drag & Drop Board',
                  'followupReminders': 'Remind me after 7 days',
                  'notifyMethod': 'Email & Dashboard Alert',
                  'weeklyGoal': 5,
                  'aiAutomation': 'Auto-draft follow-up emails on alert date',
              },
          ),
          'subscription': {
              'tier': 'Pro' if has_premium_access(current_user) else 'Free'
          },
      }),
      200,
  )


@settings_api_bp.route('/<section>', methods=['PUT'])
@login_required
def update_settings_section(section):
  data = request.get_json(silent=True)

  if not isinstance(data, dict):
    if section == 'language' and isinstance(data, str):
      data = {'language': data}
    else:
      return (
          jsonify({'error': 'A valid configuration payload is required.'}),
          400,
      )

  existing_preferences = getattr(current_user, 'preferences_json', None) or {}

  if not isinstance(existing_preferences, dict):
    existing_preferences = {}

  prefs = json.loads(json.dumps(existing_preferences))

  if section == 'profile':
    profile_data = prefs.get('profile', {})

    if not isinstance(profile_data, dict):
      profile_data = {}

    profile_data.update(data)
    prefs['profile'] = profile_data

    if 'fullName' in data:
      current_user.full_name = data['fullName']

  elif section == 'language':
    selected_language = data.get('language') or data.get('aiLanguage') or ''

    if not isinstance(selected_language, str):
      return (
          jsonify({
              'error': 'Language selection must be provided as text.',
              'supported_languages': SUPPORTED_LANGUAGES,
          }),
          400,
      )

    selected_language = selected_language.strip()

    if not selected_language:
      return (
          jsonify({
              'error': 'Please select a language preference.',
              'supported_languages': SUPPORTED_LANGUAGES,
          }),
          400,
      )

    if selected_language not in SUPPORTED_LANGUAGES:
      return (
          jsonify({
              'error': 'The selected language is not supported.',
              'supported_languages': SUPPORTED_LANGUAGES,
          }),
          400,
      )

    prefs['language'] = selected_language
    session['language'] = selected_language

    ai_preferences = prefs.get('aiPreferences', {})

    if not isinstance(ai_preferences, dict):
      ai_preferences = {}

    ai_preferences['aiLanguage'] = selected_language
    prefs['aiPreferences'] = ai_preferences

  elif section == 'ai':
    ai_preferences = prefs.get('aiPreferences', {})

    if not isinstance(ai_preferences, dict):
      ai_preferences = {}

    ai_preferences.update(data)

    if 'aiLanguage' in data:
      selected_language = data['aiLanguage']

      if (
          not isinstance(selected_language, str)
          or selected_language not in SUPPORTED_LANGUAGES
      ):
        return (
            jsonify({
                'error': 'The selected language is not supported.',
                'supported_languages': SUPPORTED_LANGUAGES,
            }),
            400,
        )

      prefs['language'] = selected_language
      session['language'] = selected_language

    prefs['aiPreferences'] = ai_preferences

  elif section == 'tracker':
    tracker_settings = prefs.get('trackerSettings', {})

    if not isinstance(tracker_settings, dict):
      tracker_settings = {}

    tracker_settings.update(data)
    prefs['trackerSettings'] = tracker_settings

  else:
    return jsonify({'error': 'Invalid settings section specified.'}), 400

  current_user.preferences_json = prefs

  flag_modified(
      current_user,
      'preferences_json',
  )

  try:
    db.session.commit()

    saved_language = get_user_preferred_language(current_user)

    return (
        jsonify({
            'success': True,
            'message': f'{section.capitalize()} settings updated successfully.',
            'language': saved_language,
            'language_code': LANGUAGE_CODES.get(
                saved_language,
                'en',
            ),
        }),
        200,
    )

  except Exception as exc:
    db.session.rollback()

    premium_app.logger.error(
        'Settings update failed for section %s: %s',
        section,
        type(exc).__name__,
    )

    return (
        jsonify({'error': 'Unable to save setting changes. Please try again.'}),
        500,
    )


@settings_api_bp.route('/avatar', methods=['POST'])
@login_required
def upload_avatar():
  if 'avatar' not in request.files:
    return jsonify({'error': 'Please select an image file to upload.'}), 400

  file = request.files['avatar']
  if not file.filename:
    return jsonify({'error': 'No file was selected for upload.'}), 400

  try:
    file_bytes = file.read()
    mimetype = file.content_type or 'image/jpeg'
    encoded_string = base64.b64encode(file_bytes).decode('utf-8')
    avatar_url = f'data:{mimetype};base64,{encoded_string}'

    current_user.avatar_url = avatar_url
    db.session.commit()

    return jsonify({'success': True, 'avatarUrl': avatar_url}), 200

  except Exception as exc:
    db.session.rollback()
    print(f'Avatar upload error: {exc}')
    return (
        jsonify({
            'error': (
                'Unable to process profile image. Please try a different image'
                ' file.'
            )
        }),
        500,
    )


@settings_api_bp.route('/password', methods=['PUT'])
@login_required
def update_user_password():
  data = request.get_json(silent=True) or {}
  curr_pass = data.get('currPassword', '')
  new_pass = data.get('newPassword', '')

  if not check_password_hash(current_user.password_hash, curr_pass):
    return (
        jsonify({'error': 'The current password provided is incorrect.'}),
        400,
    )

  if len(new_pass) < 8:
    return (
        jsonify(
            {'error': 'Your new password must be at least 8 characters long.'}
        ),
        400,
    )

  current_user.password_hash = generate_password_hash(new_pass)
  try:
    db.session.commit()
    return (
        jsonify({'success': True, 'message': 'Password updated successfully.'}),
        200,
    )
  except Exception as exc:
    db.session.rollback()
    return jsonify({'error': 'Unable to update password. Please try again.'}), 500


@settings_api_bp.route('/export', methods=['GET'])
@login_required
def export_user_data():
  try:
    user_resumes = Resume.query.filter_by(user_id=current_user.id).all()

    clean_prefs = dict(current_user.preferences_json or {})
    if 'profile' in clean_prefs and isinstance(clean_prefs['profile'], dict):
      clean_prefs['profile'].pop('avatarImage', None)

    user_data = {
        'email': current_user.email,
        'full_name': getattr(current_user, 'full_name', ''),
        'avatar_url': getattr(current_user, 'avatar_url', ''),
        'preferences': clean_prefs,
        'resumes': [
            {
                'id': r.id,
                'title': r.title,
                'template_used': r.template_used,
                'updated_at': r.updated_at.isoformat() if r.updated_at else None,
                'content': r.content_json or {},
            }
            for r in user_resumes
        ],
    }
    buffer = io.BytesIO(json.dumps(user_data, indent=2).encode('utf-8'))
    return send_file(
        buffer,
        mimetype='application/json',
        as_attachment=True,
        download_name='CVForge_Data_Export.json',
    )
  except Exception as exc:
    print(f'Data export error: {exc}')
    return (
        jsonify({'error': 'Unable to export account data at this time.'}),
        500,
    )


@settings_api_bp.route('/account', methods=['DELETE'])
@login_required
def delete_user_account():
  try:
    JobApplication.query.filter_by(user_id=current_user.id).delete()
    Resume.query.filter_by(user_id=current_user.id).delete()
    try:
      CoverLetter.query.filter_by(user_id=current_user.id).delete()
    except Exception:
      db.session.rollback()
    db.session.delete(current_user)
    db.session.commit()
    logout_user()
    return (
        jsonify({
            'success': True,
            'message': 'Your account has been deleted successfully.',
        }),
        200,
    )
  except Exception as exc:
    db.session.rollback()
    print(f'Delete account error: {exc}')
    return (
        jsonify({
            'error': (
                'Unable to delete account at this time. Please contact'
                ' support.'
            )
        }),
        500,
    )


premium_app.register_blueprint(settings_api_bp)

# ============================================================
# DIRECT APP-LEVEL EXPORT ROUTE FALLBACK
# ============================================================


@premium_app.route('/api/v1/settings/export', methods=['GET'])
@login_required
def export_user_data_direct():
  return export_user_data()


# ============================================================
# PADDLE WEBHOOK VERIFICATION
# ============================================================


def verify_paddle_webhook(request_data, signature_header):
  if (
      not PADDLE_WEBHOOK_SECRET_KEY
      or not signature_header
      or not isinstance(signature_header, str)
  ):
    return False

  try:
    components = {}
    for item in signature_header.split(';'):
      item = item.strip()
      if '=' in item:
        parts = item.split('=', 1)
        if len(parts) != 2:
          continue
        key, value = parts[0].strip(), parts[1].strip()
        if key and value:
          components[key] = value

    timestamp = components.get('ts')
    received_signature = components.get('h1')

    if not timestamp or not received_signature:
      return False

    decoded_body = (
        request_data.decode('utf-8')
        if isinstance(request_data, bytes)
        else str(request_data)
    )

    signed_payload = f'{timestamp}:{decoded_body}'

    digest = hmac.new(
        PADDLE_WEBHOOK_SECRET_KEY.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(digest, received_signature)

  except Exception as exc:
    print(f'Paddle HMAC Verification Error: {exc}')
    return False


# ============================================================
# PREMIUM API BLUEPRINT
# ============================================================

premium_bp = Blueprint('premium_api', __name__, url_prefix='/api/v1/premium')

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}


def extract_targeted_job_description(html_content: str) -> str:
  soup = BeautifulSoup(html_content, 'html.parser')

  for tag in soup([
      'script',
      'style',
      'noscript',
      'header',
      'footer',
      'nav',
      'aside',
      'form',
      'iframe',
  ]):
    tag.decompose()

  selectors = [
      'article',
      '.job-description',
      '#job-description',
      '.description',
      '.posting-description',
      '#job-details',
      '.job-details',
      'main',
  ]

  target_container = None
  for selector in selectors:
    target_container = soup.select_one(selector)
    if target_container:
      break

  content_source = target_container if target_container else soup.body or soup

  text = content_source.get_text(separator=' ')
  clean_text = re.sub(r'\s+', ' ', text).strip()
  return clean_text[:8000]


@premium_bp.route('/scrape-job', methods=['POST'])
@login_required
def scrape_job_url():
  data = request.get_json() or {}
  job_url = data.get('url', '').strip()

  if not job_url:
    return jsonify({'error': 'Please provide a valid job posting URL.'}), 400

  try:
    if 'linkedin.com' in job_url.lower():
      match = re.search(
          r'/(?:jobs/view|current|posting)/([0-9]+)', job_url
      ) or re.search(r'([0-9]{9,10})', job_url)
      if match:
        job_id = match.group(1)
        guest_api_url = (
            '[https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/](https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/)' + job_id
        )
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
          response = client.get(guest_api_url, headers=HEADERS)

          if response.status_code == 429:
            return (
                jsonify({
                    'error': (
                        'The job portal is currently limiting automated'
                        ' requests. Please copy and paste the job description'
                        ' text directly below.'
                    )
                }),
                429,
            )

          if response.status_code == 200:
            trimmed_description = extract_targeted_job_description(
                response.text
            )
            if len(trimmed_description) > 50:
              return jsonify({
                  'success': True,
                  'job_title_meta': 'Job Listing',
                  'job_description': trimmed_description,
              })

    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
      response = client.get(job_url, headers=HEADERS)

      if response.status_code == 429:
        return (
            jsonify({
                'error': (
                    'The target website is limiting automated access. Please'
                    ' copy and paste the job description text directly below.'
                )
            }),
            429,
        )

      response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    trimmed_description = extract_targeted_job_description(response.text)

    page_title = soup.title.string.strip() if soup.title else ''
    og_title = soup.find('meta', property='og:title')
    meta_title = (
        og_title['content']
        if og_title and og_title.get('content')
        else page_title
    )

    return jsonify({
        'success': True,
        'job_title_meta': meta_title,
        'job_description': trimmed_description,
    })

  except requests.exceptions.Timeout:
    return (
        jsonify({
            'error': (
                'The job website took too long to respond. Please copy and'
                ' paste the description text directly.'
            )
        }),
        504,
    )
  except Exception as e:
    return (
        jsonify({
            'error': (
                'Unable to extract text from this link due to security'
                ' protections. Please copy and paste the job description text'
                ' directly.'
            )
        }),
        500,
    )


@premium_bp.route('/application-copilot', methods=['POST'])
@login_required
def run_application_copilot():
  data = request.get_json(silent=True) or {}

  job_description = (data.get('job_description') or '').strip()
  company_name = (data.get('company_name') or 'Target Company').strip()
  job_title = (data.get('job_title') or 'Target Role').strip()
  resume_id = data.get('resume_id')

  COPILOT_CREDIT_COST = FEATURE_RULES['application_copilot']['cost']

  user_credits = getattr(current_user, 'ai_credits_remaining', 0) or 0
  if not has_premium_access(current_user) and user_credits < COPILOT_CREDIT_COST:
    return (
        jsonify({
            'error': 'Insufficient credits to run the AI Application Copilot.',
            'required_credits': COPILOT_CREDIT_COST,
            'credits_remaining': user_credits,
            'button_action': 'REFILL_CREDIT',
        }),
        402,
    )

  if not job_description:
    return jsonify({'error': 'Job description is required for Copilot.'}), 400

  try:
    preferred_language = get_user_preferred_language(current_user)

    resume_content = {}
    source_resume = None
    if resume_id:
      source_resume = Resume.query.filter_by(
          id=resume_id, user_id=current_user.id
      ).first()
      if source_resume and isinstance(source_resume.content_json, dict):
        resume_content = source_resume.content_json

    copilot_prompt = f"""
You are CVForge Copilot — an executive career agent and elite ATS resume writer.

Generate a complete, cohesive, and fully optimized application package for this job posting in {preferred_language}.

TARGET COMPANY: {company_name}
TARGET ROLE: {job_title}

JOB DESCRIPTION:
{job_description}

CANDIDATE BACKGROUND:
{json.dumps(resume_content, ensure_ascii=False)}

STRICT NO-FABRICATION & TRUTHFULNESS DIRECTIVES:
1. DO NOT invent completely false companies, dates, degrees, or tools that the candidate has never used.
2. Re-frame and polish existing candidate bullet points to emphasize relevant transferable skills and impact aligned with the job description.
3. Re-organize technical and soft skills to prioritize terms directly mentioned in the job description that match the candidate's real profile.

Generate strictly valid JSON containing:
1. "ats_score": Estimated match score (1-100).
2. "matched_keywords": Array of key terms matched between candidate profile and job description.
3. "integrated_keywords": Array of target keywords integrated into the optimized CV text.
4. "tailored_summary": A rewritten, job-specific professional summary.
5. "tailored_experience": Rewritten, impact-oriented experience bullet points formatted with standard bullet prefixes ('- ').
6. "tailored_skills_tech": Clean, comma-separated technical skills tailored to the role.
7. "tailored_skills_soft": Clean, comma-separated soft skills tailored to the role.
8. "cover_letter": A complete, persuasive 3-paragraph cover letter.
9. "cold_email_subject": High-converting recruiter email subject line.
10. "cold_email_body": A structured cold email body.
11. "interview_questions": 3 role-specific practice interview questions.

OUTPUT FORMAT (JSON ONLY):
{{
  "ats_score": 88,
  "matched_keywords": ["Python", "Flask", "PostgreSQL"],
  "integrated_keywords": ["REST API", "Database Optimization"],
  "tailored_summary": "...",
  "tailored_experience": "- Enhanced system reliability by...",
  "tailored_skills_tech": "Python, Flask, PostgreSQL, REST APIs",
  "tailored_skills_soft": "Cross-functional Collaboration, Problem Solving",
  "cover_letter": "...",
  "cold_email_subject": "...",
  "cold_email_body": "...",
  "interview_questions": ["Question 1...", "Question 2...", "Question 3..."]
}}
"""

    raw_response = generate_ai_text(copilot_prompt, max_tokens=2800)

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    copilot_result = json.loads(clean_json_str.strip())

    tailored_summary = copilot_result.get('tailored_summary', '').strip()
    tailored_experience = copilot_result.get('tailored_experience', '').strip()
    tailored_skills_tech = copilot_result.get(
        'tailored_skills_tech', ''
    ).strip()
    tailored_skills_soft = copilot_result.get(
        'tailored_skills_soft', ''
    ).strip()

    # PERSIST ALL TAILORED SECTIONS (SUMMARY, EXPERIENCE, SKILLS) INTO NEW RESUME RECORD
    import copy

    user_prefs = getattr(current_user, 'preferences_json', None) or {}
    pdf_settings = (
        user_prefs.get('pdf_settings', {})
        if isinstance(user_prefs, dict)
        else {}
    )
    chosen_template = (
        source_resume.template_used
        if source_resume and getattr(source_resume, 'template_used', None)
        else pdf_settings.get('template_id', 'exec_minimalist')
    ).replace('-', '_')
    chosen_accent = (
        source_resume.accent_color
        if source_resume and getattr(source_resume, 'accent_color', None)
        else pdf_settings.get('accent_color', '#02353C')
    )

    if source_resume:
      new_resume = Resume(
          id=str(uuid.uuid4()),
          user_id=current_user.id,
          title=f'CV - {company_name} ({job_title})',
          content_json=(
              copy.deepcopy(source_resume.content_json)
              if isinstance(source_resume.content_json, dict)
              else {}
          ),
          template_used=chosen_template,
          accent_color=chosen_accent,
          updated_at=datetime.utcnow(),
      )
    else:
      new_resume = Resume(
          id=str(uuid.uuid4()),
          user_id=current_user.id,
          title=f'CV - {company_name} ({job_title})',
          content_json={
              'full_name': getattr(current_user, 'full_name', ''),
              'email': current_user.email,
              'target_role': job_title,
          },
          template_used=chosen_template,
          accent_color=chosen_accent,
          updated_at=datetime.utcnow(),
      )

    if not isinstance(new_resume.content_json, dict):
      new_resume.content_json = {}

    if tailored_summary:
      new_resume.content_json['summary'] = tailored_summary
    if tailored_experience:
      new_resume.content_json['experience_bullets'] = tailored_experience
    if tailored_skills_tech:
      new_resume.content_json['skills_tech'] = tailored_skills_tech
    if tailored_skills_soft:
      new_resume.content_json['skills_soft'] = tailored_skills_soft

    new_resume.content_json['target_role'] = job_title

    flag_modified(new_resume, 'content_json')
    db.session.add(new_resume)

    if not has_premium_access(current_user):
      current_user.ai_credits_remaining = user_credits - COPILOT_CREDIT_COST

    new_job_app = JobApplication(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_name=company_name,
        role_title=job_title,
        status='applying',
        updated_at=datetime.utcnow(),
    )
    db.session.add(new_job_app)
    db.session.commit()

    copilot_result['generated_resume_id'] = new_resume.id

    return (
        jsonify({
            'success': True,
            'copilot_package': copilot_result,
            'tracker_id': new_job_app.id,
            'credits_remaining': current_user.ai_credits_remaining,
        }),
        200,
    )

  except Exception as exc:
    db.session.rollback()
    premium_app.logger.error(f'Copilot execution error: {exc}')
    return (
        jsonify({
            'error': (
                'Failed to complete Copilot application run. Please try again.'
            )
        }),
        500,
    )


@premium_bp.route('/portal-qa', methods=['POST'])
@login_required
def generate_portal_qa():
  try:
    data = request.get_json(silent=True) or {}

    prompt_question = data.get('prompt', '').strip()
    if not prompt_question:
      return (
          jsonify(
              {'error': 'The application portal question prompt is required.'}
          ),
          400,
      )

    company_name = data.get('company_name', '').strip() or 'Target Company'
    job_title = data.get('job_title', '').strip() or 'Candidate Role'
    tone = data.get('tone', 'Professional & Direct')
    custom_context = data.get('custom_context', '').strip()
    max_words = data.get('max_words')
    resume_id = data.get('resume_id')

    candidate_cv_summary = (
        'Professional candidate with strong background in software'
        ' development, project execution, and cross-functional team leadership.'
    )
    if resume_id and resume_id != 'default':
      resume_obj = Resume.query.filter_by(
          id=resume_id, user_id=current_user.id
      ).first()
      if resume_obj and isinstance(resume_obj.content_json, dict):
        c_json = resume_obj.content_json
        candidate_cv_summary = f"""
                Name: {c_json.get('full_name', '')}
                Target Role: {c_json.get('target_role', '')}
                Summary: {c_json.get('summary', '')}
                Experience: {c_json.get('experience_bullets', '')}
                Skills: {c_json.get('skills_tech', '')} {c_json.get('skills_soft', '')}
                Projects: {c_json.get('projects', '')}
                """

    word_constraint_clause = ''
    if max_words:
      try:
        max_w_int = int(max_words)
        word_constraint_clause = (
            'CRITICAL CONSTRAINT: The final answer MUST NOT exceed'
            f' {max_w_int} words.'
        )
      except ValueError:
        pass

    system_instructions = (
        'You are an executive career coach and expert job application writer'
        ' for CVForge Pro. Your objective is to craft high-converting,'
        ' metric-driven responses to job portal essay questions. Always'
        ' structure candidate stories using the STAR framework (Situation,'
        ' Task, Action, Result). Never use generic AI fluff or empty'
        ' buzzwords. Provide clear, concrete actions and outcomes.'
    )

    user_prompt = f"""
TARGET COMPANY: {company_name}
TARGET ROLE: {job_title}
PREFERRED TONE: {tone}

PORTAL ESSAY PROMPT / QUESTION:
"{prompt_question}"

CANDIDATE CV BACKGROUND:
{candidate_cv_summary}

SPECIFIC PROJECT / CONTEXT FOCUS:
{custom_context if custom_context else "Select the best matching project/experience from candidate background."}

{word_constraint_clause}

INSTRUCTIONS:
1. Deconstruct the response into the STAR framework (Situation, Task, Action, Result) in concise bullet summaries.
2. Draft the complete final answer in paragraph form matching the requested tone and strict length boundaries.
3. Output MUST adhere strictly to valid JSON with keys `star_breakdown` (object containing situation, task, action, result) and `answer` (string).
"""

    raw_response = generate_ai_text(
        system_instructions + '\n\n' + user_prompt, max_tokens=1500
    )

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    result = json.loads(clean_json_str.strip())
    return jsonify(result), 200

  except Exception as exc:
    premium_app.logger.error(
        f'Error generating portal Q&A response: {str(exc)}', exc_info=True
    )
    return (
        jsonify({
            'error': (
                'Failed to generate application response. Please try again.'
            )
        }),
        500,
    )


@premium_bp.route('/generate-cover-letter', methods=['POST'])
@login_required
def generate_cover_letter():
  data = request.get_json(silent=True) or {}

  resume_id = data.get('resume_id')
  company_name = (data.get('company_name') or 'Hiring Organization').strip()
  job_title = (data.get('job_title') or 'Target Position').strip()
  tone = (data.get('tone') or 'confident').strip()
  job_description = (data.get('job_description') or '').strip()

  resume_content = {}
  if resume_id:
    resume_obj = Resume.query.filter_by(
        id=resume_id, user_id=current_user.id
    ).first()
    if resume_obj and isinstance(resume_obj.content_json, dict):
      resume_content = resume_obj.content_json

  user_name = (
      resume_content.get('full_name')
      or getattr(current_user, 'full_name', '')
      or 'Applicant'
  )
  user_summary = resume_content.get('summary', '')
  user_experience = resume_content.get('experience_bullets', '')
  user_skills = (
      f"{resume_content.get('skills_tech', '')}"
      f" {resume_content.get('skills_soft', '')}"
  ).strip()

  preferred_language = get_user_preferred_language(current_user)

  prompt = f"""
You are CVForge AI, an expert executive career strategist and professional cover letter writer.

Task: Write a highly targeted, persuasive, and custom cover letter for {user_name}.

Target Company: {company_name}
Target Position: {job_title}
Desired Tone/Style: {tone}
Preferred Output Language: {preferred_language}

Candidate Profile Details:
- Name: {user_name}
- Professional Summary: {user_summary}
- Core Skills: {user_skills}
- Key Experience Details: {user_experience}

Target Job Requirements / Description:
{job_description or 'Align with industry standard expectations for this position.'}

Formatting & Content Requirements:
1. Write the cover letter strictly in {preferred_language}.
2. Maintain a {tone} tone.
3. Express strong enthusiasm for joining {company_name} in the {job_title} role.
4. Directly connect candidate experience to key requirements.
5. Include formal letter structure (salutation, body paragraphs, and professional sign-off).
6. Return strictly the cover letter text without introductory conversation or meta notes.
"""

  try:
    generated_letter = generate_ai_text(prompt, max_tokens=1500)

    try:
      new_letter = CoverLetter(
          id=str(uuid.uuid4()),
          user_id=current_user.id,
          resume_id=resume_id if resume_id != 'demo' else None,
          company_name=company_name,
          job_title=job_title,
          tone=tone,
          job_description=job_description,
          content=generated_letter,
          created_at=datetime.utcnow(),
      )
      db.session.add(new_letter)
      db.session.commit()
      letter_id = new_letter.id
    except Exception as db_exc:
      db.session.rollback()
      premium_app.logger.warning('Failed to save cover letter to DB: %s', db_exc)
      letter_id = None

    return (
        jsonify({
            'status': 'success',
            'letter_id': letter_id,
            'cover_letter_text': generated_letter,
        }),
        200,
    )

  except Exception as exc:
    db.session.rollback()
    premium_app.logger.error('Cover letter generation failed: %s', exc)
    return (
        jsonify({
            'error': (
                'Failed to generate cover letter. Please try again in a moment.'
            )
        }),
        500,
    )


@premium_bp.route('/generate-outreach', methods=['POST'])
@login_required
def generate_outreach_campaign():
  try:
    resume_source_type = request.form.get('resume_source_type', 'saved')
    resume_id = request.form.get('resume_id')
    target_company = (
        request.form.get('target_company') or 'Target Company'
    ).strip()
    recipient_role = (
        request.form.get('recipient_role') or 'Hiring Manager'
    ).strip()
    recipient_name = (request.form.get('recipient_name') or '').strip()
    tone = (request.form.get('tone') or 'Confident & Professional').strip()
    job_context = (request.form.get('job_context') or '').strip()

    resume_text_content = ''

    if resume_source_type == 'saved':
      if resume_id:
        resume_obj = Resume.query.filter_by(
            id=resume_id, user_id=current_user.id
        ).first()
        if resume_obj and isinstance(resume_obj.content_json, dict):
          resume_text_content = json.dumps(
              resume_obj.content_json, ensure_ascii=False
          )
    elif resume_source_type == 'upload':
      if 'resume_file' in request.files:
        file = request.files['resume_file']
        if file and file.filename:
          filename = secure_filename(file.filename)
          file_bytes = file.read()
          if filename.lower().endswith('.pdf'):
            try:
              import pypdf

              pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
              resume_text_content = '\n'.join(
                  [p.extract_text() or '' for p in pdf_reader.pages]
              )
            except Exception:
              resume_text_content = file_bytes.decode('utf-8', errors='ignore')
          else:
            resume_text_content = file_bytes.decode('utf-8', errors='ignore')

    user_name = getattr(current_user, 'full_name', '') or 'Applicant'
    preferred_language = get_user_preferred_language(current_user)

    prompt = f"""
You are CVForge AI, an elite career networking strategist and executive communication assistant.

Task: Generate a multi-channel direct cold outreach campaign for {user_name} targeting {target_company}.

Target Company: {target_company}
Recipient Role: {recipient_role}
Recipient Name: {recipient_name or 'Hiring Team'}
Tone/Style: {tone}
Preferred Output Language: {preferred_language}

Candidate Background Context / Resume:
{resume_text_content or 'Standard professional profile'}

Job Details / Context:
{job_context or 'Targeting positions at ' + target_company}

REQUIREMENTS:
1. "linkedin_note": A direct, engaging connection request note MUST be under 300 characters strictly.
2. "email_subject": A high-converting subject line for cold emailing a recruiter or decision-maker.
3. "email_body": A structured 3-paragraph cold email (Hook, Value Proposition from Candidate Context, Low-friction Call To Action).
4. "referral_request": A polite, friendly message to send to a peer or alumni asking for an internal referral or advice.
5. All outputs MUST be strictly in {preferred_language}.

Output MUST be strictly valid JSON matching this schema:
{{
  "linkedin_note": "Connection message...",
  "email_subject": "Subject line...",
  "email_body": "Full email body text...",
  "referral_request": "Referral message text..."
}}
"""

    raw_response = generate_ai_text(prompt, max_tokens=1500)

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    result = json.loads(clean_json_str.strip())
    return jsonify(result), 200

  except Exception as exc:
    premium_app.logger.error('Outreach generation error: %s', exc)
    return (
        jsonify({
            'error': (
                'Unable to generate outreach campaign. Please try again'
                ' shortly.'
            )
        }),
        500,
    )


@premium_bp.route('/evaluate-offer', methods=['POST'])
@login_required
def evaluate_offer():
  data = request.get_json(silent=True) or {}

  company_name = (data.get('company_name') or 'Target Company').strip()
  job_title = (data.get('job_title') or 'Target Position').strip()
  currency = (data.get('currency') or 'USD').strip()
  base_salary = (data.get('base_salary') or '').strip()
  bonus_equity = (data.get('bonus_equity') or '').strip()
  target_salary = (data.get('target_salary') or '').strip()
  location_remote = (data.get('location_remote') or '').strip()
  perks_notes = (data.get('perks_notes') or '').strip()
  tone = (data.get('tone') or 'Professional & Firm').strip()

  preferred_language = get_user_preferred_language(current_user)

  prompt = f"""
You are CVForge AI, an executive compensation consultant and salary negotiation expert.

Task: Evaluate a job offer and craft a high-impact, persuasive counter-offer negotiation strategy for a candidate.

Target Company: {company_name}
Job Title: {job_title}
Currency: {currency}
Offered Base Salary: {base_salary} {currency}
Offered Bonus / Equity / Benefits: {bonus_equity or 'Not specified'}
Candidate Target Salary / Goal: {target_salary or 'Market maximum'} {currency if target_salary else ''}
Location / Remote Setup: {location_remote or 'Not specified'}
Additional Notes / Perks: {perks_notes or 'None'}
Desired Negotiation Tone: {tone}
Output Language: {preferred_language}

REQUIREMENTS:
1. "offer_grade": A quick assessment rating (e.g., "Competitive", "Below Market Range", "Strong Base / Low Equity").
2. "evaluation_summary": 2-3 sentences analyzing the offer strength based on market trends for {job_title} using {currency}.
3. "strategy_points": An array of 3 actionable leverage points the candidate should emphasize (e.g., key skills, competing timelines, unique experience).
4. "counter_email_subject": A professional subject line for replying to the recruiter or hiring manager.
5. "counter_email_body": A structured counter-offer email requesting the target compensation or perks in {currency}, maintaining a {tone} tone.
6. Write ALL text strictly in {preferred_language}.

Output MUST be strictly valid JSON matching this schema:
{{
  "offer_grade": "Grade/Rating",
  "evaluation_summary": "Summary evaluation...",
  "strategy_points": [
    "Leverage point 1...",
    "Leverage point 2...",
    "Leverage point 3..."
  ],
  "counter_email_subject": "Subject line...",
  "counter_email_body": "Full counter-offer email text..."
}}
"""

  try:
    raw_response = generate_ai_text(prompt, max_tokens=1500)

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    result = json.loads(clean_json_str.strip())
    return jsonify(result), 200

  except Exception as exc:
    premium_app.logger.error('Salary negotiation evaluation error: %s', exc)
    return (
        jsonify({
            'error': (
                'Unable to evaluate offer. Please verify your input details and'
                ' try again.'
            )
        }),
        500,
    )


@premium_bp.route('/save-cover-letter-pdf', methods=['POST'])
@login_required
def save_cover_letter_pdf():
  data = request.get_json(silent=True) or {}
  content = data.get('content', '').strip()
  company_name = data.get('company_name', 'Target_Company').strip()

  if not content:
    return jsonify({'error': 'No cover letter content provided.'}), 400

  try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        'CoverLetterBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=16,
        textColor=colors.HexColor('#0f172a'),
    )

    story = []
    for paragraph in content.split('\n'):
      if paragraph.strip():
        story.append(
            Paragraph(
                paragraph.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'),
                body_style,
            )
        )
        story.append(Spacer(1, 10))
      else:
        story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)

    safe_filename = (
        re.sub(r'[^\w\s-]', '', company_name).strip().replace(' ', '_')
    )
    download_name = f"Cover_Letter_{safe_filename or 'Document'}.pdf"

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=download_name,
    )
  except Exception as exc:
    premium_app.logger.error('PDF generation failed: %s', exc)
    return jsonify({'error': 'Failed to generate PDF document.'}), 500


@premium_bp.route('/user-status', methods=['GET'])
@login_required
def get_user_status():
  is_developer = is_developer_user(current_user)
  premium_access = has_premium_access(current_user)

  return (
      jsonify({
          'user_id': getattr(current_user, 'id', None),
          'email': getattr(current_user, 'email', None),
          'is_premium': premium_access,
          'is_developer': is_developer,
          'subscription_status': (
              'developer'
              if is_developer
              else getattr(current_user, 'subscription_status', 'free')
          ),
          'paddle_price_id': PADDLE_PRO_PRICE_ID,
      }),
      200,
  )


@premium_bp.route('/webhook/paddle', methods=['POST'])
def paddle_webhook():
  signature = request.headers.get('Paddle-Signature')
  payload = request.get_data()

  if not verify_paddle_webhook(payload, signature):
    return jsonify({'error': 'Invalid webhook signature.'}), 400

  data = request.get_json(silent=True) or {}
  if not isinstance(data, dict):
    return jsonify({'error': 'Invalid webhook payload structure.'}), 400

  event_type = data.get('event_type')
  event_data = data.get('data', {})
  if not isinstance(event_data, dict):
    event_data = {}

  customer_email = event_data.get('customer', {}).get(
      'email'
  ) or event_data.get('customer_email')
  items = event_data.get('items', [])
  price_id = items[0].get('price', {}).get('id') if items else None
  item_config = PRICE_MAP.get(price_id, {})

  # 1. HANDLE SUBSCRIPTION CREATED / UPDATED / ACTIVATED
  if event_type in [
      'subscription.created',
      'subscription.activated',
      'subscription.updated',
  ]:
    subscription_status = event_data.get('status')
    if (
        subscription_status == 'active'
        and item_config.get('type') == 'sub'
        and customer_email
    ):
      user = User.query.filter_by(email=customer_email.lower()).first()
      if user:
        try:
          user.is_premium = True
          user.subscription_tier = item_config['tier']
          user.subscription_status = 'active'
          user.ai_credits_remaining = item_config['credits']
          user.paddle_subscription_id = event_data.get('id')
          db.session.commit()
        except Exception as exc:
          db.session.rollback()
          print(f'Paddle sub update error: {exc}')
          return jsonify({'error': 'Unable to update subscription status.'}), 500

  # 2. HANDLE ONE-TIME TRANSACTIONS (Passes & Credit Top-Ups)
  elif event_type == 'transaction.completed':
    if price_id in PRICE_MAP and customer_email:
      user = User.query.filter_by(email=customer_email.lower()).first()
      if user:
        try:
          if item_config['type'] == 'pass':
            expiry_date = datetime.utcnow() + timedelta(
                days=item_config['days']
            )
            user.subscription_tier = 'pro'
            user.ai_credits_remaining = (
                user.ai_credits_remaining or 0
            ) + item_config['credits']
            user.pass_expires_at = expiry_date
            db.session.commit()
          elif item_config['type'] == 'topup':
            user.ai_credits_remaining = (
                user.ai_credits_remaining or 0
            ) + item_config['credits']
            db.session.commit()
        except Exception as exc:
          db.session.rollback()
          print(f'Paddle one-time purchase update error: {exc}')
          return (
              jsonify({'error': 'Unable to process purchase transaction.'}),
              500,
          )

  # 3. HANDLE CANCELLATIONS / PAST DUE
  elif event_type in ['subscription.canceled', 'subscription.past_due']:
    subscription_id = event_data.get('id')
    if subscription_id:
      user = User.query.filter_by(
          paddle_subscription_id=subscription_id
      ).first()
      if user:
        try:
          user.is_premium = False
          user.subscription_tier = 'free'
          user.subscription_status = event_data.get('status', 'canceled')
          db.session.commit()
        except Exception as exc:
          db.session.rollback()
          print(f'Paddle cancellation update error: {exc}')
          return jsonify({'error': 'Unable to update subscription status.'}), 500

  return jsonify({'status': 'success'}), 200


@premium_bp.route('/analyze-ats', methods=['POST'])
@login_required
def analyze_ats():
  if not has_premium_access(current_user):
    return (
        jsonify({
            'error': (
                'Your premium subscription has expired. Please renew your'
                ' subscription to access ATS optimization features.'
            ),
            'code': 'SUBSCRIPTION_EXPIRED',
            'button_action': 'PAY',
        }),
        403,
    )

  if request.is_json:
    data = request.get_json(silent=True) or {}
  else:
    data = request.form.to_dict()

  cv_text = ''
  resume_obj = None
  original_content = {}

  dashboard_resume_id = data.get('resume_id') or data.get('saved_resume_id')
  uploaded_file = request.files.get('cv_file') if not request.is_json else None

  if dashboard_resume_id:
    resume_obj = Resume.query.filter_by(
        id=dashboard_resume_id, user_id=current_user.id
    ).first()
    if resume_obj:
      if isinstance(resume_obj.content_json, dict):
        original_content = dict(resume_obj.content_json)
      cv_text = json.dumps(original_content, ensure_ascii=False)

  if not cv_text and uploaded_file and uploaded_file.filename:
    filename = secure_filename(uploaded_file.filename)
    file_bytes = uploaded_file.read()

    if filename.lower().endswith('.pdf'):
      try:
        import pypdf

        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        cv_text = '\n'.join(
            [page.extract_text() or '' for page in pdf_reader.pages]
        )
      except Exception:
        cv_text = file_bytes.decode('utf-8', errors='ignore')
    else:
      cv_text = file_bytes.decode('utf-8', errors='ignore')

  if not cv_text:
    return (
        jsonify({
            'error': (
                'Please select a resume from your dashboard or upload a valid'
                ' CV document.'
            )
        }),
        400,
    )

  job_desc = (data.get('job_description') or '').strip()

  if not job_desc:
    return (
        jsonify({
            'error': (
                'Please provide a valid job description before running the'
                ' optimization.'
            )
        }),
        400,
    )

  preferred_language = get_user_preferred_language(current_user)

  prompt = f"""
You are CVForge Engine — an advanced ATS Resume Parser & Optimization System.

TASK:
1. Parse ALL information from the candidate's CV text below.
2. STICK STRICTLY TO THE PROVIDED CANDIDATE CV TEXT. Do not substitute candidate details.
3. Rewrite Summary, Experience, and Skills to align with Target Job Description.
4. Output strictly in {preferred_language}.

Candidate CV Text:
{cv_text}

Target Job Description:
{job_desc}

Return ONLY a JSON object matching this structure:
{{
  "ats_score": 85,
  "matched_keywords": [],
  "missing_keywords": [],
  "summary_feedback": "Resume effectively adapted for target role...",
  "parsed_profile": {{
    "full_name": "Extract exact Full Name",
    "email": "Extract exact Email",
    "phone": "Extract exact Phone",
    "location": "Extract exact Location",
    "linkedin": "Extract exact LinkedIn",
    "portfolio": "Extract exact Portfolio",
    "job_title": "Extract exact Primary Job Title",
    "company": "Extract exact Latest Company",
    "job_location": "Extract exact Job Location",
    "job_dates": "Extract exact Employment Dates",
    "education_degree": "Extract exact Degree",
    "education_school": "Extract exact School",
    "education_dates": "Extract exact Education Dates",
    "education_honors": "",
    "certifications": "Extract exact Certifications",
    "projects": "Extract exact Projects",
    "languages": "Extract exact Languages"
  }},
  "optimized_sections": {{
    "summary": "ATS-optimized summary...",
    "experience_bullets": "- Professional experience bullet 1\\n- Professional experience bullet 2",
    "skills_tech": "Extracted technical skills",
    "skills_soft": "Extracted soft skills"
  }}
}}
"""

  gemini_key = get_gemini_api_key()
  if not gemini_key:
    return (
        jsonify({
            'error': (
                'ATS analysis service is temporarily unavailable. Please try'
                ' again shortly.'
            )
        }),
        503,
    )

  try:
    raw_response = generate_ai_text(prompt, max_tokens=2048)

    clean_json_str = raw_response.strip()
    if clean_json_str.startswith('```json'):
      clean_json_str = clean_json_str[7:]
    if clean_json_str.startswith('```'):
      clean_json_str = clean_json_str[3:]
    if clean_json_str.endswith('```'):
      clean_json_str = clean_json_str[:-3]

    parsed_data = json.loads(clean_json_str.strip())
    opt_sections = parsed_data.get('optimized_sections', {})
    extracted = parsed_data.get('parsed_profile', {})

    def clean_val(val):
      if (
          not val
          or str(val).strip().lower()
          in ['not specified', 'none', 'n/a', 'not provided', 'null']
      ):
        return ''
      return str(val).strip()

    merged_content = {}
    merged_content['full_name'] = (
        clean_val(original_content.get('full_name'))
        or clean_val(getattr(current_user, 'full_name', ''))
        or clean_val(extracted.get('full_name', ''))
    )
    merged_content['email'] = (
        clean_val(original_content.get('email'))
        or clean_val(getattr(current_user, 'email', ''))
        or clean_val(extracted.get('email', ''))
    )
    merged_content['phone'] = clean_val(
        original_content.get('phone')
    ) or clean_val(extracted.get('phone', ''))
    merged_content['location'] = clean_val(
        original_content.get('location')
    ) or clean_val(extracted.get('location', ''))
    merged_content['linkedin'] = clean_val(
        original_content.get('linkedin')
    ) or clean_val(extracted.get('linkedin', ''))
    merged_content['portfolio'] = clean_val(
        original_content.get('portfolio')
    ) or clean_val(extracted.get('portfolio', ''))

    merged_content['job_title'] = clean_val(
        original_content.get('job_title')
    ) or clean_val(extracted.get('job_title', ''))
    merged_content['target_role'] = (
        clean_val(original_content.get('target_role'))
        or merged_content['job_title']
    )
    merged_content['company'] = clean_val(
        original_content.get('company')
    ) or clean_val(extracted.get('company', ''))
    merged_content['job_location'] = clean_val(
        original_content.get('job_location')
    ) or clean_val(extracted.get('job_location', ''))
    merged_content['job_dates'] = clean_val(
        original_content.get('job_dates')
    ) or clean_val(extracted.get('job_dates', ''))

    merged_content['education_degree'] = clean_val(
        original_content.get('education_degree')
    ) or clean_val(extracted.get('education_degree', ''))
    merged_content['education_school'] = clean_val(
        original_content.get('education_school')
    ) or clean_val(extracted.get('education_school', ''))
    merged_content['education_dates'] = clean_val(
        original_content.get('education_dates')
    ) or clean_val(extracted.get('education_dates', ''))
    merged_content['education_honors'] = clean_val(
        original_content.get('education_honors')
    ) or clean_val(extracted.get('education_honors', ''))

    merged_content['certifications'] = clean_val(
        original_content.get('certifications')
    ) or clean_val(extracted.get('certifications', ''))
    merged_content['projects'] = clean_val(
        original_content.get('projects')
    ) or clean_val(extracted.get('projects', ''))
    merged_content['languages'] = clean_val(
        original_content.get('languages')
    ) or clean_val(extracted.get('languages', ''))

    merged_content['summary'] = opt_sections.get(
        'summary'
    ) or original_content.get('summary', '')
    merged_content['experience_bullets'] = opt_sections.get(
        'experience_bullets'
    ) or original_content.get('experience_bullets', '')
    merged_content['skills_tech'] = opt_sections.get(
        'skills_tech'
    ) or original_content.get('skills_tech', '')
    merged_content['skills_soft'] = opt_sections.get(
        'skills_soft'
    ) or original_content.get('skills_soft', '')

    user_prefs = getattr(current_user, 'preferences_json', None) or {}
    pdf_settings = (
        user_prefs.get('pdf_settings', {})
        if isinstance(user_prefs, dict)
        else {}
    )

    is_pro = has_premium_access(current_user)

    if is_pro and pdf_settings.get('template_id'):
      chosen_template = (
          pdf_settings.get('template_id', 'exec_minimalist')
      ).replace('-', '_')
      chosen_accent = pdf_settings.get('accent_color', '#02353C')
    else:
      chosen_template = 'standard_ats'
      chosen_accent = '#0f172a'

    new_resume_id = str(uuid.uuid4())
    base_title = resume_obj.title if resume_obj else 'Optimized CV'

    new_resume = Resume(
        id=new_resume_id,
        user_id=current_user.id,
        title=f'ATS Optimized - {base_title}',
        content_json=merged_content,
        template_used=chosen_template,
        accent_color=chosen_accent,
        updated_at=datetime.utcnow(),
    )
    db.session.add(new_resume)
    db.session.commit()

    return (
        jsonify({
            'success': data.get('success', True),
            'ats_score': parsed_data.get('ats_score', 80),
            'matched_keywords': parsed_data.get('matched_keywords', []),
            'missing_keywords': parsed_data.get('missing_keywords', []),
            'summary_feedback': parsed_data.get('summary_feedback', ''),
            'optimized_resume_id': new_resume.id,
            'optimized_cv': merged_content,
        }),
        200,
    )

  except Exception as updated_exc:
    db.session.rollback()
    premium_app.logger.error('ATS analysis failed: %s', updated_exc)
    return (
        jsonify({
            'error': (
                'ATS analysis is temporarily unavailable. Please try again'
                ' shortly.'
            )
        }),
        503,
    )


# Register premium blueprint onto the main Flask app instance
premium_app.register_blueprint(premium_bp)

# ============================================================
# Vercel Entry Point & Local Dev
# ============================================================

app = premium_app

if __name__ == '__main__':
  with premium_app.app_context():
    db.create_all()

  premium_app.run(debug=True, port=5001)
