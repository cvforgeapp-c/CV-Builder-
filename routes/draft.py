# routes/draft.py
import os
import json
import uuid
import logging
from flask import Blueprint, request, jsonify, current_app

draft_bp = Blueprint('draft', __name__)
logger = logging.getLogger(__name__)

@draft_bp.route('/save-draft', methods=['POST'])
def save_draft():
    try:
        data = request.get_json()
        draft_id = data.get('draft_id', str(uuid.uuid4()))
        file_path = os.path.join(current_app.config['DATA_FOLDER'], f"draft_{draft_id}.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return jsonify({'status': 'success', 'draft_id': draft_id}), 200
    except Exception as e:
        logger.error(f"Error saving draft: {str(e)}")
        return jsonify({'error': str(e)}), 500

@draft_bp.route('/get-draft/<draft_id>', methods=['GET'])
def get_draft(draft_id):
    file_path = os.path.join(current_app.config['DATA_FOLDER'], f"draft_{draft_id}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'status': 'success', 'data': data}), 200
    return jsonify({'error': 'Draft not found'}), 404
