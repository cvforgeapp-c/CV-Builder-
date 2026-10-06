import os
import math
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
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

_modern_canvas = None
PAGE_WIDTH, PAGE_HEIGHT = A4
SIDEBAR_WIDTH = 75 * mm
MAIN_MARGIN_LEFT = SIDEBAR_WIDTH + 10 * mm
MAIN_WIDTH = PAGE_WIDTH - MAIN_MARGIN_LEFT - 10 * mm
BOTTOM_MARGIN = 15 * mm

SECTION_GAP = 7 * mm
HEADER_GAP = 6 * mm
ITEM_GAP = 3.5 * mm
LINE_LEADING = 4.5 * mm

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

def generate_modern(data, file):
    c = canvas.Canvas(file, pagesize=A4)
    global _modern_canvas
    _modern_canvas = c
    c.setTitle("CV - " + (data.get("name") or "CV"))

    sidebar_color = colors.HexColor(data.get("sidebar_color") or "#173F49")
    gold = colors.HexColor(data.get("accent_color") or "#F2B632")
    white = colors.white
    dark = colors.HexColor("#173F49")
    text_dark = colors.HexColor("#2C3E50")

    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)
    c.setFillColor(sidebar_color)
    c.rect(0, 0, SIDEBAR_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)

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
        y -= SECTION_GAP
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

    name_font = "Montserrat-ExtraBold" if HAS_MONTSERRAT else "Helvetica-Bold"
    name = (data.get("name") or "CV").upper()

    c.setFillColor(dark)
    c.setFont(name_font, 22)
    c.drawString(MAIN_MARGIN_LEFT, PAGE_HEIGHT - 22 * mm, name)

    title = (data.get("title") or "").upper()
    c.setFillColor(gold)
    c.setFont("Helvetica-Bold", 11.5)
    c.drawString(MAIN_MARGIN_LEFT, PAGE_HEIGHT - 28 * mm, title)

    my = PAGE_HEIGHT - 38 * mm

    if data.get("summary"):
        my = draw_lines(data["summary"], MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=9, leading=LINE_LEADING, color=text_dark)

    if data.get("experience"):
        my = check_overflow(c, my, 25 * mm, sidebar_color)
        my = main_section_header("Experience", "experience", MAIN_MARGIN_LEFT, my)
        for line in data["experience"].split("\n"):
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                my -= ITEM_GAP
                my = draw_lines(line, MAIN_MARGIN_LEFT, my, MAIN_WIDTH, font="Helvetica-Bold", size=9.5, leading=LINE_LEADING, color=dark)
                my -= 1 * mm
            else:
                my = draw_lines(line, MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=8.8, leading=LINE_LEADING, color=text_dark, bullet=True)

    if data.get("education"):
        my = check_overflow(c, my, 20 * mm, sidebar_color)
        my = main_section_header("Education", "education", MAIN_MARGIN_LEFT, my)
        for line in data["education"].splitlines():
            if line.strip():
                if "|" in line:
                    my -= ITEM_GAP
                    my = draw_lines(line.strip(), MAIN_MARGIN_LEFT, my, MAIN_WIDTH, font="Helvetica-Bold", size=9.5, leading=LINE_LEADING, color=dark)
                    my -= 1 * mm
                else:
                    my = draw_lines(line.strip(), MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=8.8, leading=LINE_LEADING, color=text_dark, bullet=True)

    if data.get("certificates"):
        my = check_overflow(c, my, 20 * mm, sidebar_color)
        my = main_section_header("Certificates", "certificates", MAIN_MARGIN_LEFT, my)
        for line in data["certificates"].splitlines():
            if line.strip():
                my = draw_lines(line.strip(), MAIN_MARGIN_LEFT, my, MAIN_WIDTH, size=8.8, leading=LINE_LEADING, color=text_dark, bullet=True)

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

def generate_classic(data, file):
    c = canvas.Canvas(file, pagesize=A4)
    c.setTitle("CV - " + (data.get("name") or "CV"))
    
    accent_color = colors.HexColor(data.get("accent_color") or "#1769AA")
    dark_text = colors.HexColor("#222222")
    margin = 15 * mm
    width = PAGE_WIDTH - (2 * margin)
    y = PAGE_HEIGHT - margin

    c.setFillColor(dark_text)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(margin, y, (data.get("name") or "FULL NAME").upper())
    y -= 7 * mm

    c.setFillColor(accent_color)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, (data.get("title") or "").upper())
    y -= 6 * mm

    c.setFont("Helvetica", 8.5)
    c.setFillColor(dark_text)
    contact_info = [data.get(k) for k in ["phone", "email", "location", "linkedin", "website"] if data.get(k)]
    c.drawString(margin, y, "  |  ".join(contact_info))
    y -= 4 * mm
    
    c.setStrokeColor(accent_color)
    c.setLineWidth(1)
    c.line(margin, y, margin + width, y)
    y -= 8 * mm

    def draw_section(title, text_key):
        nonlocal y
        if not data.get(text_key):
            return
        
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(accent_color)
        c.drawString(margin, y, title.upper())
        y -= 2 * mm
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.5)
        c.line(margin, y, margin + width, y)
        y -= 5 * mm

        c.setFont("Helvetica", 9)
        c.setFillColor(dark_text)
        for line in str(data[text_key]).splitlines():
            if line.strip():
                lines = wrap_text(c, line.strip(), "Helvetica", 9, width)
                for l in lines:
                    c.drawString(margin, y, l)
                    y -= LINE_LEADING
        y -= 4 * mm

    draw_section("Professional Summary", "summary")
    draw_section("Work Experience", "experience")
    draw_section("Education", "education")
    draw_section("Skills", "skills")
    draw_section("Certificates", "certificates")
    draw_section("Languages", "languages")

    c.save()

def generate_ats(data, file):
    c = canvas.Canvas(file, pagesize=A4)
    c.setTitle("CV - " + (data.get("name") or "CV"))
    
    dark_text = colors.HexColor("#000000")
    margin = 18 * mm
    width = PAGE_WIDTH - (2 * margin)
    y = PAGE_HEIGHT - margin

    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(dark_text)
    c.drawString(margin, y, (data.get("name") or "").upper())
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(margin, y, data.get("title") or "")
    y -= 5 * mm

    contact_info = [data.get(k) for k in ["phone", "email", "location", "linkedin", "website"] if data.get(k)]
    c.setFont("Helvetica", 8.5)
    c.drawString(margin, y, " • ".join(contact_info))
    y -= 4 * mm

    c.setStrokeColor(colors.black)
    c.setLineWidth(0.75)
    c.line(margin, y, margin + width, y)
    y -= 7 * mm

    def draw_ats_section(title, text_key):
        nonlocal y
        if not data.get(text_key):
            return
        
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(margin, y, title.upper())
        y -= 2 * mm
        c.line(margin, y, margin + width, y)
        y -= 4 * mm

        c.setFont("Helvetica", 9)
        for line in str(data[text_key]).splitlines():
            if line.strip():
                lines = wrap_text(c, line.strip(), "Helvetica", 9, width)
                for l in lines:
                    c.drawString(margin, y, l)
                    y -= 4.2 * mm
        y -= 3 * mm

    draw_ats_section("Summary", "summary")
    draw_ats_section("Experience", "experience")
    draw_ats_section("Education", "education")
    draw_ats_section("Skills", "skills")
    draw_ats_section("Certificates", "certificates")

    c.save()

def generate_cv(template_type, data, output_path):
    template_type = (template_type or "modern").lower()

    if template_type == "classic":
        generate_classic(data, output_path)
    elif template_type == "ats":
        generate_ats(data, output_path)
    else:
        generate_modern(data, output_path)
