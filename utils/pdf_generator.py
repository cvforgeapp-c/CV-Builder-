import os
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

if os.path.exists(MONTSERRAT_EXTRA_BOLD):
    try:
        pdfmetrics.registerFont(TTFont("Montserrat-ExtraBold", MONTSERRAT_EXTRA_BOLD))
    except Exception as e:
        print(f"Warning: Could not register Montserrat font: {e}")

if os.path.exists(DANCING_SCRIPT):
    try:
        pdfmetrics.registerFont(TTFont("DancingScript", DANCING_SCRIPT))
    except Exception as e:
        print(f"Warning: Could not register DancingScript font: {e}")

_modern_canvas = None
PAGE_HEIGHT = 297 * mm
PAGE_WIDTH = 210 * mm
BOTTOM_MARGIN = 20 * mm

def clean(text):
    return str(text).strip() if text else ""

def wrap_text(c, text, font, size, max_width):
    words = clean(text).split()
    lines = []
    current = ""
    if c:
        c.setFont(font, size)

    for word in words:
        test = word if not current else current + " " + word
        width = c.stringWidth(test, font, size) if c else stringWidth(test, font, size)
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines

def wrap(text, font, size, width):
    if not text:
        return []
    return wrap_text(_modern_canvas, text, font, size, width)

def check_page_overflow(c, y, required_space, template_type, sidebar_color, accent_color):
    if y - required_space < BOTTOM_MARGIN:
        c.showPage()
        new_y = PAGE_HEIGHT - 20 * mm
        if template_type == "modern":
            c.setFillColor(sidebar_color)
            c.rect(0, 0, 78 * mm, PAGE_HEIGHT, fill=True, stroke=False)
        elif template_type == "classic":
            c.setFillColor(accent_color)
            c.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, fill=True, stroke=False)
        return new_y
    return y

def modern(data, file_stream):
    W, H = A4
    c = canvas.Canvas(file_stream, pagesize=A4)
    global _modern_canvas
    _modern_canvas = c
    c.setTitle("CV - " + (data.get("name") or "My CV"))

    teal = colors.HexColor("#053D47")
    sidebar_color = colors.HexColor(data.get("sidebar_color") or "#173F49")
    gold = colors.HexColor(data.get("accent_color") or "#F2B632")
    white = colors.white
    dark = colors.HexColor("#123F4A")
    muted = colors.HexColor("#5E6F73")

    sidebar_w = 78 * mm
    main_x = sidebar_w + 14 * mm
    main_w = W - main_x - 13 * mm

    c.setFillColor(colors.HexColor("#FAFCFB"))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(sidebar_color)
    c.rect(0, 0, sidebar_w, H, stroke=0, fill=1)

    photo_stream = data.get("photo_stream")
    if photo_stream:
        try:
            photo_size = 48 * mm
            photo_x = (sidebar_w - photo_size) / 2
            photo_y = H - 63 * mm

            c.setFillColor(gold)
            c.circle(photo_x + photo_size / 2, photo_y + photo_size / 2, photo_size / 2 + 2.2 * mm, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.circle(photo_x + photo_size / 2, photo_y + photo_size / 2, photo_size / 2 + 0.8 * mm, stroke=0, fill=1)

            c.saveState()
            path = c.beginPath()
            path.circle(photo_x + photo_size / 2, photo_y + photo_size / 2, photo_size / 2)
            c.clipPath(path, stroke=0, fill=0)
            c.drawImage(ImageReader(photo_stream), photo_x, photo_y, width=photo_size, height=photo_size, preserveAspectRatio=True, anchor="c", mask="auto")
            c.restoreState()
        except Exception as e:
            print(f"Error drawing photo: {e}")

    def draw_lines(value, x, y, width, font="Helvetica", size=8.8, leading=4.6 * mm, color=dark, bullet=False):
        if not value:
            return y
        c.setFillColor(color)
        c.setFont(font, size)

        for paragraph in value.splitlines():
            paragraph = paragraph.strip()
            if not paragraph:
                y -= leading * 0.55
                continue

            lines = wrap(paragraph, font, size, width)
            for index, line in enumerate(lines):
                prefix = "• " if (bullet and index == 0) else ("  " if bullet else "")
                c.drawString(x, y, prefix + line)
                y -= leading
        return y

    def main_section(title, x, y, width):
        c.setFillColor(teal)
        c.circle(x + 5 * mm, y + 1 * mm, 5.2 * mm, stroke=0, fill=1)
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", 11.5)
        c.drawString(x + 14 * mm, y, title.upper())
        c.setStrokeColor(gold)
        c.setLineWidth(1.1)
        c.line(x + 12 * mm, y - 4.5 * mm, x + width, y - 4.5 * mm)
        return y - 11.5 * mm

    def sidebar_section(title, x, y, width):
        c.setFillColor(gold)
        c.setFont("Helvetica-Bold", 10.5)
        title_x = x + 2 * mm
        c.drawString(title_x, y, title.upper())
        c.setStrokeColor(gold)
        c.setLineWidth(1)
        c.line(title_x, y - 2.2 * mm, x + width, y - 2.2 * mm)
        return y - 9 * mm

    sx = 10 * mm
    sw = sidebar_w - 20 * mm
    sy = H - 78 * mm

    sy = check_page_overflow(c, sy, 6 * mm, "modern", sidebar_color, gold)
    sy = sidebar_section("Contact", sx, sy, sw)

    contact_items = [
        data.get("phone"),
        data.get("email"),
        data.get("location"),
        data.get("linkedin"),
        data.get("website")
    ]

    for val in contact_items:
        if val:
            sy = draw_lines(val, sx + 2 * mm, sy, sw - 2 * mm, size=8.2, leading=4.8 * mm, color=white)
    sy -= 2.0 * mm

    if data.get("skills"):
        sy = check_page_overflow(c, sy, 6 * mm, "modern", sidebar_color, gold)
        sy -= 4 * mm
        sy = sidebar_section("Skills", sx, sy, sw)
        for skill in data["skills"].splitlines():
            if skill.strip():
                sy = draw_lines(skill.strip(), sx, sy, sw, size=9, leading=5 * mm, color=white, bullet=True)

    if data.get("languages"):
        sy = check_page_overflow(c, sy, 6 * mm, "modern", sidebar_color, gold)
        sy -= 4 * mm
        sy = sidebar_section("Languages", sx, sy, sw)
        for lang in data["languages"].splitlines():
            if lang.strip():
                sy = draw_lines(lang.strip(), sx, sy, sw, size=9, leading=5 * mm, color=white, bullet=True)

    name = (data.get("name") or "My CV").upper()
    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(main_x, H - 23 * mm, name[:45])

    title = data.get("title") or ""
    if title:
        c.setFillColor(gold)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(main_x, H - 31 * mm, title[:70].upper())

    y = H - 43 * mm

    if data.get("summary"):
        y = draw_lines(data["summary"], main_x, y, main_w, size=9.5, leading=4.8 * mm, color=muted)
        y -= 7 * mm

    if data.get("experience"):
        y = check_page_overflow(c, y, 15 * mm, "modern", sidebar_color, gold)
        y = main_section("Experience", main_x, y, main_w)
        y = draw_lines(data["experience"], main_x, y, main_w, size=8.8, leading=5.0 * mm, color=muted)
        y -= 5 * mm

    if data.get("projects"):
        y = check_page_overflow(c, y, 15 * mm, "modern", sidebar_color, gold)
        y = main_section("Projects", main_x, y, main_w)
        y = draw_lines(data["projects"], main_x, y, main_w, size=8.8, leading=5.0 * mm, color=muted)
        y -= 5 * mm

    if data.get("education"):
        y = check_page_overflow(c, y, 15 * mm, "modern", sidebar_color, gold)
        y = main_section("Education", main_x, y, main_w)
        y = draw_lines(data["education"], main_x, y, main_w, size=8.8, leading=5.0 * mm, color=muted)
        y -= 5 * mm

    if data.get("certificates"):
        y = check_page_overflow(c, y, 15 * mm, "modern", sidebar_color, gold)
        y = main_section("Certificates", main_x, y, main_w)
        y = draw_lines(data["certificates"], main_x, y, main_w, size=8.8, leading=5.0 * mm, color=muted)
        y -= 5 * mm

    if data.get("references"):
        y = check_page_overflow(c, y, 15 * mm, "modern", sidebar_color, gold)
        y = main_section("References", main_x, y, main_w)
        y = draw_lines(data["references"], main_x, y, main_w, size=8.8, leading=5.0 * mm, color=muted)

    c.save()

def classic(data, file_stream):
    W, H = A4
    c = canvas.Canvas(file_stream, pagesize=A4)
    global _modern_canvas
    _modern_canvas = c
    c.setTitle("CV - " + (data.get("name") or "My CV"))

    accent = colors.HexColor(data.get("accent_color") or "#F2B632")
    primary = colors.HexColor("#0D4F4F")
    dark = colors.HexColor("#222222")

    x = 18 * mm
    w = W - 36 * mm
    y = H - 22 * mm

    c.setFillColor(primary)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(x, y, (data.get("name") or "My CV").upper())
    y -= 7 * mm

    if data.get("title"):
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x, y, data["title"].upper())
        y -= 7 * mm

    c.setStrokeColor(primary)
    c.setLineWidth(1.5)
    c.line(x, y, x + w, y)
    y -= 6 * mm

    contacts = [val for val in [data.get("phone"), data.get("email"), data.get("location"), data.get("linkedin")] if val]
    if contacts:
        c.setFillColor(dark)
        c.setFont("Helvetica", 8.5)
        c.drawString(x, y, " | ".join(contacts))
        y -= 8 * mm

    def section(title, current_y):
        c.setFillColor(primary)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, current_y, title.upper())
        c.setStrokeColor(accent)
        c.setLineWidth(1)
        c.line(x, current_y - 3 * mm, x + w, current_y - 3 * mm)
        return current_y - 8 * mm

    def draw_block(text, current_y):
        if not text:
            return current_y
        c.setFillColor(dark)
        c.setFont("Helvetica", 9)
        for line in wrap(text, "Helvetica", 9, w):
            c.drawString(x, current_y, line)
            current_y -= 4.5 * mm
        return current_y

    sections = [
        ("Summary", data.get("summary")),
        ("Experience", data.get("experience")),
        ("Projects", data.get("projects")),
        ("Education", data.get("education")),
        ("Skills", data.get("skills")),
        ("Certificates", data.get("certificates")),
        ("Languages", data.get("languages")),
        ("References", data.get("references")),
    ]

    for title, content in sections:
        if content:
            y = check_page_overflow(c, y, 14 * mm, "classic", primary, accent)
            y = section(title, y)
            y = draw_block(content, y)
            y -= 4 * mm

    c.save()

def ats(data, file_stream):
    W, H = A4
    c = canvas.Canvas(file_stream, pagesize=A4)
    global _modern_canvas
    _modern_canvas = c
    c.setTitle("CV - " + (data.get("name") or "My CV"))

    dark = colors.HexColor("#111111")
    x = 18 * mm
    w = W - 36 * mm
    y = H - 20 * mm

    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(x, y, (data.get("name") or "My CV"))
    y -= 6 * mm

    if data.get("title"):
        c.setFont("Helvetica", 11)
        c.drawString(x, y, data["title"])
        y -= 6 * mm

    contacts = [val for val in [data.get("phone"), data.get("email"), data.get("location"), data.get("linkedin")] if val]
    if contacts:
        c.setFont("Helvetica", 8.5)
        c.drawString(x, y, " • ".join(contacts))
        y -= 7 * mm

    c.setStrokeColor(dark)
    c.setLineWidth(0.8)
    c.line(x, y, x + w, y)
    y -= 8 * mm

    def draw_section(title, content, current_y):
        if not content:
            return current_y
        current_y = check_page_overflow(c, current_y, 12 * mm, "ats", dark, dark)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, current_y, title.upper())
        current_y -= 4.5 * mm

        c.setFont("Helvetica", 8.5)
        for line in wrap(content, "Helvetica", 8.5, w):
            c.drawString(x, current_y, line)
            current_y -= 4 * mm
        return current_y - 4 * mm

    sections = [
        ("Summary", data.get("summary")),
        ("Experience", data.get("experience")),
        ("Projects", data.get("projects")),
        ("Education", data.get("education")),
        ("Skills", data.get("skills")),
        ("Certificates", data.get("certificates")),
        ("Languages", data.get("languages")),
        ("References", data.get("references")),
    ]

    for title, content in sections:
        y = draw_section(title, content, y)

    c.save()

def generate_pdf(data, file_stream):
    template = clean(data.get("template")).lower()
    if template == "classic":
        classic(data, file_stream)
    elif template == "ats":
        ats(data, file_stream)
    else:
        modern(data, file_stream)
