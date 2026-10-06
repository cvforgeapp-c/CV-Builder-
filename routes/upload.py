# routes/upload.py
import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from utils.helpers import allowed_file, parse_resume_file, extract_basic_info

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/upload', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
        
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        unique_id = str(uuid.uuid4())[:8]
        saved_filename = f"{unique_id}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
        
        file.save(file_path)
        
        extracted_text = parse_resume_file(file_path, ext)
        parsed_data = extract_basic_info(extracted_text)
        
        return jsonify({
            'message': 'File uploaded and parsed successfully',
            'filename': saved_filename,
            'parsed_data': parsed_data
        }), 200
        
    return jsonify({'error': 'Invalid file format. Allowed: PDF, DOCX, TXT'}), 400
