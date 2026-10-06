import os
import tempfile
import base64
import uuid
import math
import re
import fitz  # PyMuPDF
from flask import Flask, request, render_template_string, send_file, redirect, url_for

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
MONTSERRAT_EXTRA_BOLD = os.path.join(FONT_DIR, "Montserrat-ExtraBold.ttf")
DANCING_SCRIPT = os.path.join(FONT_DIR, "DancingScript-Regular.ttf")

HAS_MONTSERRAT = False
HAS_DANCING = False

if os.path.exists(MONTSERRAT_EXTRA_BOLD):
    try:
        pdfmetrics.registerFont(TTFont("Montserrat-ExtraBold", MONTSERRAT_EXTRA_BOLD))
        HAS_MONTSERRAT = True
    except Exception as e:
        print(f"Font error (Montserrat): {e}")

if os.path.exists(DANCING_SCRIPT):
    try:
        pdfmetrics.registerFont(TTFont("DancingScript", DANCING_SCRIPT))
        HAS_DANCING = True
    except Exception as e:
        print(f"Font error (DancingScript): {e}")

app = Flask(__name__)

# ============================================================
# CONSTANTS & CANVAS SETUP
# ============================================================
_modern_canvas = None
PAGE_WIDTH, PAGE_HEIGHT = A4
SIDEBAR_WIDTH = 75 * mm
MAIN_MARGIN_LEFT = SIDEBAR_WIDTH + 10 * mm
MAIN_WIDTH = PAGE_WIDTH - MAIN_MARGIN_LEFT - 10 * mm
BOTTOM_MARGIN = 15 * mm

# Standardized Spacing Rules (Fixed Section Heights)
SECTION_GAP = 7 * mm    # Space above a section header
HEADER_GAP = 6 * mm     # Space below a section header line
ITEM_GAP = 3.5 * mm     # Space between separate entries/jobs
LINE_LEADING = 4.5 * mm # Line spacing for multi-line body text

# ============================================================
# HTML TEMPLATES (OPTIMIZED BUTTONS & PREVIEW)
# ============================================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV Generator</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #eef2f5; margin: 0; padding: 30px; }
        .container { max-width: 800px; margin: 0 auto; background: #fff; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); }
        h1 { text-align: center; color: #02353C; margin-bottom: 25px; font-weight: 700; }
        label { font-weight: 600; display: block; margin-top: 15px; color: #444; font-size: 14px; }
        input[type="text"], textarea, input[type="file"], input[type="color"] {
            width: 100%; padding: 12px; margin-top: 6px; border: 1.5px solid #dcdfe6; border-radius: 6px; box-sizing: border-box; font-size: 14px; transition: border 0.2s;
        }
        input[type="text"]:focus, textarea:focus { border-color: #02353C; outline: none; }
        textarea { height: 90px; resize: vertical; line-height: 1.4; }
        .row { display: flex; gap: 20px; }
        .row > div { flex: 1; }
        
        /* Modern Button Styling */
        .btn-submit {
            margin-top: 30px; width: 100%; padding: 14px; background: linear-gradient(135deg, #02353C 0%, #05535E 100%);
            color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;
            box-shadow: 0 4px 12px rgba(2, 53, 60, 0.25); transition: all 0.25s ease;
        }
        .btn-submit:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(2, 53, 60, 0.35); background: linear-gradient(135deg, #05535E 0%, #02353C 100%); }
        .btn-submit:active { transform: translateY(0); }
    </style>
</head>
<body>
    <div class="container">
        <h1>CV Builder</h1>
        <form action="/generate" method="POST" enctype="multipart/form-data">
            <div class="row">
                <div>
                    <label>Full Name</label>
                    <input type="text" name="name" value="KEDIR ABDELA" required>
                </div>
                <div>
                    <label>Job Title</label>
                    <input type="text" name="title" value="BUSINESS MARKETING" required>
                </div>
            </div>

            <div class="row">
                <div>
                    <label>Phone</label>
                    <input type="text" name="phone" value="+251 90 870 6534">
                </div>
                <div>
                    <label>Email</label>
                    <input type="text" name="email" value="rentallah85@gmail.com">
                </div>
            </div>

            <div class="row">
                <div>
                    <label>Location</label>
                    <input type="text" name="location" value="Los Angeles, USA">
                </div>
                <div>
                    <label>LinkedIn</label>
                    <input type="text" name="linkedin" value="linkedin.com/in/kedirmohammed">
                </div>
            </div>

            <label>Website</label>
            <input type="text" name="website" value="www.kedir.dev">

            <label>Profile Photo</label>
            <input type="file" name="photo" accept="image/*">

            <label>Professional Summary</label>
            <textarea name="summary">Results-driven Digital Marketing Specialist with 5+ years of experience developing data-driven marketing campaigns, increasing online engagement, and improving customer acquisition. Skilled in SEO, social media marketing, content strategy, Google Analytics, and paid advertising.</textarea>

            <label>Work Experience (Format: Title | Company | Location | Dates \n Bullet points)</label>
            <textarea name="experience">Digital Marketing Specialist | BrightWave Media | New York, NY | 2022 - Present
Developed and managed digital marketing campaigns across Google, Instagram, Facebook, and LinkedIn.
Increased website traffic by 45% through SEO and content marketing strategies.
Managed monthly advertising budgets and analyzed campaign performance.
Marketing Coordinator | NovaTech Solutions | New York, NY | 2019 - 2022
Supported digital marketing campaigns and social media activities.
Created weekly performance reports using Google Analytics.</textarea>

            <label>Education</label>
            <textarea name="education">Bachelor of Business Administration | New York University | New York, NY | 2015 - 2019</textarea>

            <label>Skills (One per line)</label>
            <textarea name="skills">Digital Marketing
Search Engine Optimization (SEO)
Social Media Marketing
Google Analytics
Content Marketing</textarea>

            <label>Certificates (One per line)</label>
            <textarea name="certificates">Google Analytics Certification | Google | 2023
Google Ads Search Certification | Google | 2023</textarea>

            <label>Languages (One per line)</label>
            <textarea name="languages">English – Native
Spanish – Professional Working Proficiency</textarea>

            <label>Interests / Hobbies (One per line)</label>
            <textarea name="hobbies">Technology and AI
Photography
Traveling</textarea>

            <label>References (One per line)</label>
            <textarea name="references">References available upon request.</textarea>

            <div class="row">
                <div>
                    <label>Sidebar Color</label>
                    <input type="color" name="sidebar_color" value="#02353C">
                </div>
                <div>
                    <label>Accent Color</label>
                    <input type="color" name="accent_color" value="#E5A93C">
                </div>
            </div>

            <button type="submit" class="btn-submit">Generate PDF CV</button>
        </form>
    </div>
</body>
</html>
"""

PREVIEW_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV Preview</title>
    <style>
        body { margin: 0; background: #1e1e24; display: flex; flex-direction: column; align-items: center; min-height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        
        .controls-bar { 
            position: sticky; top: 0; z-index: 100; width: 100%; background: #02353C; padding: 15px 0; 
            display: flex; justify-content: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        .controls-inner { width: 100%; max-width: 850px; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; box-sizing: border-box; }
        
        /* Interactive Action Buttons */
        .btn {
            display: inline-flex; align-items: center; gap: 8px; text-decoration: none; padding: 10px 22px; 
            border-radius: 6px; font-weight: 600; font-size: 14px; transition: all 0.25s ease; cursor: pointer;
        }
        .btn-back { background: rgba(255,255,255,0.15); color: #fff; border: 1px solid rgba(255,255,255,0.25); }
        .btn-back:hover { background: rgba(255,255,255,0.28); transform: translateX(-2px); }
        
        .btn-download { background: #E5A93C; color: #02353C; border: none; box-shadow: 0 3px 10px rgba(229,169,60,0.3); }
        .btn-download:hover { background: #f0b446; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(229,169,60,0.45); }
        
        .preview-container { width: 100%; max-width: 850px; padding: 30px 20px; box-sizing: border-box; display: flex; flex-direction: column; gap: 25px; align-items: center; }
        .cv-page-img { width: 100%; max-width: 800px; height: auto; box-shadow: 0 8px 30px rgba(0,0,0,0.4); border-radius: 6px; background: #fff; }
    </style>
</head>
<body>
    <div class="controls-bar">
        <div class="controls-inner">
            <a href="/" class="btn btn-back">← Edit Details</a>
            <a href="/download/{{ token }}" class="btn btn-download">Download PDF Document</a>
        </div>
    </div>
    <div class="preview-container">
        {% for img_base64 in pages %}
            <img class="cv-page-img" src="data:image/png;base64,{{ img_base64 }}" alt="CV Page {{ loop.index }}">
        {% endfor %}
    </div>
</body>
</html>
"""

# ============================================================
# VECTOR ICONS
# ============================================================
def draw_circle_icon(c, x, y, radius, bg_color, icon_type):
    c.saveState()
    c.setFillColor(bg_color)
    c.circle(x, y, radius, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.white)
    c.setLineWidth(1)
    r = radius * 0.55

    if icon_type == "experience":
        c.rect(x - r*0.7, y - r*0.5, r*1.4, r*1.0, stroke=1, fill=0)
        c.rect(x - r*0.3, y + r*0.5, r*0.6, r*0.3, stroke=1, fill=0)
        c.line(x - r*0.7, y + r*0.1, x + r*0.7, y + r*0.1)
    elif icon_type == "education":
        p = c.beginPath()
        p.moveTo(x - r*0.9, y)
        p.lineTo(x, y + r*0.6)
        p.lineTo(x + r*0.9, y)
        p.lineTo(x, y - r*0.6)
        p.close()
        c.drawPath(p, stroke=1, fill=1)
        c.rect(x - r*0.5, y - r*0.7, r*1.0, r*0.4, stroke=0, fill=1)
    elif icon_type == "certificates":
        c.rect(x - r*0.6, y - r*0.7, r*1.2, r*1.4, stroke=1, fill=0)
        c.line(x - r*0.3, y + r*0.3, x + r*0.3, y + r*0.3)
        c.line(x - r*0.3, y, x + r*0.3, y)
    elif icon_type == "references":
        c.circle(x, y + r*0.3, r*0.35, stroke=1, fill=1)
        p = c.beginPath()
        p.moveTo(x - r*0.6, y - r*0.6)
        p.curveTo(x - r*0.6, y - r*0.1, x + r*0.6, y - r*0.1, x + r*0.6, y - r*0.6)
        c.drawPath(p, stroke=1, fill=1)
    elif icon_type == "contact":
        c.circle(x, y + r*0.2, r*0.4, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(x - r*0.3, y + r*0.1)
        p.lineTo(x, y - r*0.6)
        p.lineTo(x + r*0.3, y + r*0.1)
        c.drawPath(p, stroke=1, fill=1)
    elif icon_type == "skills":
        c.circle(x, y, r*0.4, stroke=1, fill=0)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            c.line(x + r*0.4*math.cos(rad), y + r*0.4*math.sin(rad), x + r*0.75*math.cos(rad), y + r*0.75*math.sin(rad))
    elif icon_type == "languages":
        c.circle(x, y, r*0.7, stroke=1, fill=0)
        c.line(x - r*0.7, y, x + r*0.7, y)
        c.line(x, y - r*0.7, x, y + r*0.7)
    elif icon_type == "interests":
        p = c.beginPath()
        p.moveTo(x, y - r*0.6)
        p.curveTo(x - r*0.8, y, x - r*0.8, y + r*0.6, x, y + r*0.3)
        p.curveTo(x + r*0.8, y + r*0.6, x + r*0.8, y, x, y - r*0.6)
        c.drawPath(p, stroke=1, fill=1)

    c.restoreState()

def draw_sidebar_contact_icon(c, x, y, icon_type, color):
    c.saveState()
    c.setFillColor(color)
    c.setStrokeColor(color)
    c.setLineWidth(1)
    r = 2.0 * mm

    if icon_type == "phone":
        c.rect(x - r*0.4, y - r*0.7, r*0.8, r*1.4, stroke=1, fill=0)
        c.circle(x, y - r*0.4, 0.3, stroke=0, fill=1)
    elif icon_type == "email":
        c.rect(x - r*0.7, y - r*0.5, r*1.4, r*1.0, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(x - r*0.7, y + r*0.5)
        p.lineTo(x, y)
        p.lineTo(x + r*0.7, y + r*0.5)
        c.drawPath(p, stroke=1, fill=0)
    elif icon_type == "location":
        c.circle(x, y + r*0.2, r*0.4, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(x - r*0.3, y + r*0.1)
        p.lineTo(x, y - r*0.6)
        p.lineTo(x + r*0.3, y + r*0.1)
        c.drawPath(p, stroke=1, fill=1)
    elif icon_type == "linkedin":
        c.rect(x - r*0.6, y - r*0.6, r*1.2, r*1.2, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 5)
        c.drawString(x - r*0.3, y - r*0.3, "in")
    elif icon_type == "website":
        c.circle(x, y, r*0.6, stroke=1, fill=0)
        c.line(x - r*0.6, y, x + r*0.6, y)
        c.line(x, y - r*0.6, x, y + r*0.6)

    c.restoreState()

# ============================================================
# TEXT WRAPPING & FORMATTING UTILITIES
# ============================================================
def clean(text):
    return str(text).strip() if text else ""

def strip_bullets(text):
    return re.sub(r'^[•\-\*\s]+', '', text.strip())

def wrap_text(c, text, font, size, max_width):
    if not text:
        return []

    lines = []
    for paragraph in str(text).splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        words = paragraph.split(" ")
        current_line = ""

        for word in words:
            word_w = c.stringWidth(word, font, size) if c else stringWidth(word, font, size)
            if word_w > max_width:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                sub_str = ""
                for char in word:
                    test_sub = sub_str + char
                    test_w = c.stringWidth(test_sub, font, size) if c else stringWidth(test_sub, font, size)
                    if test_w <= max_width:
                        sub_str = test_sub
                    else:
                        lines.append(sub_str)
                        sub_str = char
                if sub_str:
                    current_line = sub_str
                continue

            test_line = word if not current_line else current_line + " " + word
            test_w = c.stringWidth(test_line, font, size) if c else stringWidth(test_line, font, size)

            if test_w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

    return lines

def wrap(text, font, size, width):
    if not text:
        return []
    return wrap_text(_modern_canvas, text, font, size, width)

def check_overflow(c, y, space_needed, sidebar_color):
    if y - space_needed < BOTTOM_MARGIN:
        c.showPage()
        c.setFillColor(sidebar_color)
        c.rect(0, 0, SIDEBAR_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)
        return PAGE_HEIGHT - 20 * mm
    return y

# ============================================================
# PDF GENERATOR WITH OPTIMIZED TYPOGRAPHY & FIXED SPACING
# ============================================================
def modern(data, file):
    c = canvas.Canvas(file, pagesize=A4)
    global _modern_canvas
    _modern_canvas = c
    c.setTitle("CV - " + (data.get("name") or "KEDIR ABDELA"))

    sidebar_color = colors.HexColor(data.get("sidebar_color") or "#02353C")
    gold = colors.HexColor(data.get("accent_color") or "#E5A93C")
    white = colors.white
    dark = colors.HexColor("#02353C")
    text_dark = colors.HexColor("#2C3E50")

    # Initial Sidebar Background
    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)
    c.setFillColor(sidebar_color)
    c.rect(0, 0, SIDEBAR_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)

    # 1. Profile Photo
    photo = data.get("photo")
    photo_size = 48 * mm
    photo_x = (SIDEBAR_WIDTH - photo_size) / 2
    photo_y = PAGE_HEIGHT - 60 * mm

    if photo and os.path.exists(photo):
        try:
            c.setFillColor(gold)
            c.circle(photo_x + photo_size / 2, photo_y + photo_size / 2, photo_size / 2 + 2 * mm, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.circle(photo_x + photo_size / 2, photo_y + photo_size / 2, photo_size / 2 + 0.8 * mm, stroke=0, fill=1)

            c.saveState()
            path = c.beginPath()
            path.circle(photo_x + photo_size / 2, photo_y + photo_size / 2, photo_size / 2)
            c.clipPath(path, stroke=0, fill=0)
            c.drawImage(ImageReader(photo), photo_x, photo_y, width=photo_size, height=photo_size, preserveAspectRatio=True, anchor="c", mask="auto")
            c.restoreState()
        except Exception as e:
            print(f"Photo error: {e}")

    # 2. Rendering Helper Functions with Fixed Line Height
    def draw_lines(value, x, y, width, font="Helvetica", size=9, leading=LINE_LEADING, color=text_dark, bullet=False):
        if not value:
            return y
        c.setFillColor(color)
        c.setFont(font, size)

        for line_item in value.splitlines():
            line_item = line_item.strip()
            if not line_item:
                continue

            clean_item = strip_bullets(line_item) if bullet else line_item
            wrapped = wrap(clean_item, font, size, width - (4 * mm if bullet else 0))

            for idx, line in enumerate(wrapped):
                if bullet and idx == 0:
                    c.drawString(x, y, "•")
                    c.drawString(x + 3.5 * mm, y, line)
                else:
                    c.drawString(x + (3.5 * mm if bullet else 0), y, line)
                y -= leading
        return y

    def main_section_header(title, icon_type, x, y):
        y -= SECTION_GAP  # Standardized uniform margin before header
        draw_circle_icon(c, x + 5 * mm, y + 1.5 * mm, 5 * mm, dark, icon_type)
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", 11.5)
        c.drawString(x + 12 * mm, y, title.upper())
        c.setStrokeColor(gold)
        c.setLineWidth(1.2)
        c.line(x + 12 * mm, y - 3.5 * mm, x + MAIN_WIDTH, y - 3.5 * mm)
        return y - HEADER_GAP

    def sidebar_section_header(title, icon_type, x, y):
        sw = SIDEBAR_WIDTH - 16 * mm
        draw_circle_icon(c, x + 3 * mm, y + 1.2 * mm, 4 * mm, gold, icon_type)
        c.setFillColor(gold)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 9 * mm, y, title.upper())
        c.setStrokeColor(gold)
        c.setLineWidth(1)
        c.line(x, y - 3 * mm, x + sw, y - 3 * mm)
        return y - 7 * mm

    # 3. Sidebar Content
    sx = 8 * mm
    sw = SIDEBAR_WIDTH - 16 * mm
    sy = PAGE_HEIGHT - 72 * mm

    sy = sidebar_section_header("Contact", "contact", sx, sy)
    contacts = [
        ("phone", data.get("phone")),
        ("email", data.get("email")),
        ("location", data.get("location")),
        ("linkedin", data.get("linkedin")),
        ("website", data.get("website")),
    ]

    for icon, val in contacts:
        if val:
            draw_sidebar_contact_icon(c, sx + 2 * mm, sy + 1.2 * mm, icon, gold)
            sy = draw_lines(val, sx + 6 * mm, sy, sw - 6 * mm, size=8.5, leading=4.2 * mm, color=white)
            sy -= 1.5 * mm

    for title, key, icon in [("Skills", "skills", "skills"), ("Languages", "languages", "languages"), ("Interests", "hobbies", "interests")]:
        if data.get(key):
            sy -= 2 * mm
            sy = check_overflow(c, sy, 20 * mm, sidebar_color)
            sy = sidebar_section_header(title, icon, sx, sy)
            for item in data[key].splitlines():
                if item.strip():
                    sy = draw_lines(item.strip(), sx, sy, sw, size=8.5, leading=4.2 * mm, color=white, bullet=True)

    # 4. Main Body Header
    name_font = "Montserrat-ExtraBold" if HAS_MONTSERRAT else "Helvetica-Bold"
    name = (data.get("name") or "KEDIR ABDELA").upper()

    c.setFillColor(dark)
    c.setFont(name_font, 22)
    c.drawString(MAIN_MARGIN_LEFT, PAGE_HEIGHT - 22 * mm, name)

    title = (data.get("title") or "BUSINESS MARKETING").upper()
    c.setFillColor(gold)
    c.setFont("Helvetica-Bold", 11.5)
    c.drawString(MAIN_MARGIN_LEFT, PAGE_HEIGHT - 28 * mm, title)

    my = PAGE_HEIGHT - 38 * mm

    # 5. Professional Summary
    if data.get("summary"):
        my = draw_lines(data["summary"], MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=9, leading=LINE_LEADING, color=text_dark)

    # 6. Work Experience Section
    if data.get("experience"):
        my = check_overflow(c, my, 25 * mm, sidebar_color)
        my = main_section_header("Experience", "experience", MAIN_MARGIN_LEFT, my)

        entries = data["experience"].split("\n")
        for line in entries:
            line = line.strip()
            if not line:
                continue

            if "|" in line:
                my -= ITEM_GAP
                my = draw_lines(line, MAIN_MARGIN_LEFT, my, MAIN_WIDTH, font="Helvetica-Bold", size=9.5, leading=LINE_LEADING, color=dark, bullet=False)
                my -= 1 * mm
            else:
                my = draw_lines(line, MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=8.8, leading=LINE_LEADING, color=text_dark, bullet=True)

    # 7. Education Section
    if data.get("education"):
        my = check_overflow(c, my, 20 * mm, sidebar_color)
        my = main_section_header("Education", "education", MAIN_MARGIN_LEFT, my)
        for line in data["education"].splitlines():
            if line.strip():
                if "|" in line:
                    my -= ITEM_GAP
                    my = draw_lines(line.strip(), MAIN_MARGIN_LEFT, my, MAIN_WIDTH, font="Helvetica-Bold", size=9.5, leading=LINE_LEADING, color=dark, bullet=False)
                    my -= 1 * mm
                else:
                    my = draw_lines(line.strip(), MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=8.8, leading=LINE_LEADING, color=text_dark, bullet=True)

    # 8. Certificates Section
    if data.get("certificates"):
        my = check_overflow(c, my, 20 * mm, sidebar_color)
        my = main_section_header("Certificates", "certificates", MAIN_MARGIN_LEFT, my)
        for line in data["certificates"].splitlines():
            if line.strip():
                my = draw_lines(line.strip(), MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=8.8, leading=LINE_LEADING, color=text_dark, bullet=True)

    # 9. References Section & Signature
    if data.get("references"):
        my = check_overflow(c, my, 20 * mm, sidebar_color)
        my = main_section_header("References", "references", MAIN_MARGIN_LEFT, my)
        my = draw_lines(data["references"], MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=8.8, leading=LINE_LEADING, color=text_dark, bullet=True)

    sig_font = "DancingScript" if HAS_DANCING else "Helvetica-Oblique"
    c.setFillColor(dark)
    c.setFont(sig_font, 22)
    c.drawString(MAIN_MARGIN_LEFT, my - 6 * mm, name.title())
    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.line(MAIN_MARGIN_LEFT, my - 8 * mm, MAIN_MARGIN_LEFT + 60 * mm, my - 8 * mm)

    c.save()

# ============================================================
# PDF TO IMAGE PREVIEW
# ============================================================
def pdf_to_base64_images(pdf_path):
    image_list = []
    doc = fitz.open(pdf_path)
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        base64_encoded = base64.b64encode(img_bytes).decode("utf-8")
        image_list.append(base64_encoded)
    doc.close()
    return image_list

# ============================================================
# FLASK CONTROLLERS
# ============================================================
@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/generate", methods=["GET", "POST"])
def generate():
    if request.method == "GET":
        return redirect(url_for("home"))

    photo = request.files.get("photo")
    data = {
        "name": request.form.get("name", "KEDIR ABDELA"),
        "title": request.form.get("title", "BUSINESS MARKETING"),
        "phone": request.form.get("phone", "+251 90 870 6534"),
        "email": request.form.get("email", "rentallah85@gmail.com"),
        "location": request.form.get("location", "Los Angeles, USA"),
        "linkedin": request.form.get("linkedin", "linkedin.com/in/kedirmohammed"),
        "website": request.form.get("website", "www.kedir.dev"),
        "summary": request.form.get("summary", ""),
        "experience": request.form.get("experience", ""),
        "education": request.form.get("education", ""),
        "skills": request.form.get("skills", ""),
        "certificates": request.form.get("certificates", ""),
        "languages": request.form.get("languages", ""),
        "hobbies": request.form.get("hobbies", ""),
        "references": request.form.get("references", ""),
        "accent_color": request.form.get("accent_color", "#E5A93C"),
        "sidebar_color": request.form.get("sidebar_color", "#02353C"),
    }

    if photo and photo.filename:
        photo_path = os.path.join(tempfile.gettempdir(), "CV_" + uuid.uuid4().hex + "_" + photo.filename)
        photo.save(photo_path)
        data["photo"] = photo_path

    token = str(uuid.uuid4())
    pdf_path = os.path.join(tempfile.gettempdir(), f"CV_{token}.pdf")

    modern(data, pdf_path)
    page_images = pdf_to_base64_images(pdf_path)

    return render_template_string(PREVIEW_HTML, token=token, pages=page_images)

@app.route("/download/<token>")
def download_pdf(token):
    filename = os.path.join(tempfile.gettempdir(), f"CV_{token}.pdf")
    if not os.path.exists(filename):
        return "CV not found.", 404
    return send_file(filename, as_attachment=True, download_name="KEDIR_ABDELA_CV.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
