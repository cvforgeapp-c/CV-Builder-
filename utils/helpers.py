# utils/helpers.py
import re
from flask import current_app

try:
    import docx
except ImportError:
    docx = None

try:
    from pdfminer.high_level import extract_text as extract_pdf_text
except ImportError:
    extract_pdf_text = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def parse_resume_file(file_path, extension):
    text = ""
    if extension == 'txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    elif extension == 'docx' and docx:
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
    elif extension == 'pdf' and extract_pdf_text:
        text = extract_pdf_text(file_path)
    return text

def extract_basic_info(text):
    data = {
        'full_name': '',
        'email': '',
        'phone': '',
        'skills': [],
        'raw_text': text
    }
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if email_match:
        data['email'] = email_match.group(0)
        
    phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phone_match:
        data['phone'] = phone_match.group(0)
        
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        data['full_name'] = lines[0]
        
    return data
