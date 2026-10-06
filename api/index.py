# api/index.py
import os
import sys
import logging
from flask import Flask

# Add root directory to sys.path so blueprint imports resolve cleanly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Set absolute paths to template and static folders
template_dir = os.path.join(BASE_DIR, 'templates')
static_dir = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = os.environ.get("SECRET_KEY", "cvforge_secret_key_123")

# Serverless ephemeral storage (/tmp only)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['GENERATED_FOLDER'] = '/tmp/generated'
app.config['DATA_FOLDER'] = '/tmp/data'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt'}

for folder in [app.config['UPLOAD_FOLDER'], app.config['GENERATED_FOLDER'], app.config['DATA_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# Register Blueprints
from routes.main import main_bp
from routes.upload import upload_bp
from routes.draft import draft_bp
from routes.preview import preview_bp

app.register_blueprint(main_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(draft_bp)
app.register_blueprint(preview_bp)

# Export WSGI app for Vercel
app = app
