# api/index.py
import os
import logging
from flask import Flask

# Initialize Flask App pointing to root templates and static folders
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get("SECRET_KEY", "cvforge_secret_key_123")

# Setup Logging
logging.basicConfig(level=logging.INFO)

# Vercel Serverless File Locations (/tmp only)
UPLOAD_FOLDER = '/tmp/uploads'
GENERATED_FOLDER = '/tmp/generated'
DATA_FOLDER = '/tmp/data'

for folder in [UPLOAD_FOLDER, GENERATED_FOLDER, DATA_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER
app.config['DATA_FOLDER'] = DATA_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt'}

# Register Blueprints / Modular Routes
from routes.main import main_bp
from routes.upload import upload_bp
from routes.draft import draft_bp
from routes.preview import preview_bp

app.register_blueprint(main_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(draft_bp)
app.register_blueprint(preview_bp)

# Vercel entry point export
app = app

if __name__ == '__main__':
    app.run(debug=True)
