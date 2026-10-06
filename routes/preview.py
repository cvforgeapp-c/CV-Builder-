# routes/preview.py
from flask import Blueprint, request, jsonify, render_template_string

preview_bp = Blueprint('preview', __name__)

@preview_bp.route('/generate-preview', methods=['POST'])
def generate_preview():
    data = request.get_json() or {}
    template_type = data.get('template', 'modern')
    
    template_str = """
    <div class="resume-preview template-{{ template_type }}">
        <header>
            <h1>{{ data.get('full_name', 'Your Name') }}</h1>
            <p>{{ data.get('email', '') }} | {{ data.get('phone', '') }} | {{ data.get('location', '') }}</p>
        </header>
        <hr>
        {% if data.get('summary') %}
        <section class="section">
            <h3>Professional Summary</h3>
            <p>{{ data.get('summary') }}</p>
        </section>
        {% endif %}
        
        {% if data.get('skills') %}
        <section class="section">
            <h3>Skills</h3>
            <p>{{ data.get('skills') }}</p>
        </section>
        {% endif %}
    </div>
    """
    
    rendered_html = render_template_string(template_str, data=data, template_type=template_type)
    return jsonify({'html': rendered_html})
