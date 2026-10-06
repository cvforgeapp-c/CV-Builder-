import os
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Spacer, Frame, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Fonts
try:
    pdfmetrics.registerFont(TTFont('Montserrat-ExtraBold', 'fonts/Montserrat-ExtraBold.ttf'))
    pdfmetrics.registerFont(TTFont('DancingScript', 'fonts/DancingScript-Regular.ttf'))
except Exception:
    pass  # Fallback to Helvetica if custom fonts are missing in environment


def draw_circle_icon(c, x, y, radius, bg_hex, icon_type):
    """Draws custom vector contact and section icons in the sidebar."""
    c.saveState()
    c.setFillColor(colors.HexColor(bg_hex))
    c.circle(x, y, radius, fill=1, stroke=0)
    c.setStrokeColor(colors.white)
    c.setFillColor(colors.white)
    c.setLineWidth(1)
    
    # Simple vector representations for sidebar icons
    if icon_type == 'phone':
        c.rect(x - 2, y - 3, 4, 6, fill=0, stroke=1)
    elif icon_type == 'email':
        c.rect(x - 3, y - 2, 6, 4, fill=0, stroke=1)
    elif icon_type == 'location':
        c.circle(x, y + 1, 1.5, fill=0, stroke=1)
    elif icon_type == 'linkedin':
        c.drawString(x - 2, y - 2, "in")
    elif icon_type == 'website':
        c.circle(x, y, 2.5, fill=0, stroke=1)
    c.restoreState()


def get_common_styles(accent_hex, sidebar_hex):
    styles = getSampleStyleSheet()
    accent = colors.HexColor(accent_hex)
    dark = colors.HexColor('#1A252C')
    
    # Modern Main Column Section Headings
    styles.add(ParagraphStyle(
        'MainSectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#173F49'),
        spaceBefore=10,
        spaceAfter=2,
        keepWithNext=True
    ))

    # Standard Main Column Text
    styles.add(ParagraphStyle(
        'MainBodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=dark,
        spaceBefore=4,   # Extra space directly under section headers/lines
        spaceAfter=3
    ))

    # Sidebar Headings
    styles.add(ParagraphStyle(
        'SidebarHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.white,
        spaceBefore=12,
        spaceAfter=6
    ))

    # Sidebar Body Text
    styles.add(ParagraphStyle(
        'SidebarBodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#E0E6E8')
    ))

    return styles


# ==========================================
# 1. MODERN TEMPLATE
# ==========================================
def generate_modern(data, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    sidebar_w = 75 * mm
    accent_hex = data.get("accent_color", "#F2B632")
    sidebar_hex = data.get("sidebar_color", "#173F49")

    # Draw Sidebar Background
    c.setFillColor(colors.HexColor(sidebar_hex))
    c.rect(0, 0, sidebar_w, height, fill=1, stroke=0)

    # Draw Photo if exists
    photo_path = data.get("photo")
    if photo_path and os.path.exists(photo_path):
        try:
            c.saveState()
            # Circular clip path for photo
            path = c.beginPath()
            path.circle(sidebar_w / 2, height - 45 * mm, 22 * mm)
            c.clipPath(path, stroke=0)
            c.drawImage(photo_path, sidebar_w / 2 - 22 * mm, height - 67 * mm, width=44 * mm, height=44 * mm, preserveAspectRatio=True)
            c.restoreState()
            
            # White border circle around photo
            c.setStrokeColor(colors.white)
            c.setLineWidth(2)
            c.circle(sidebar_w / 2, height - 45 * mm, 22 * mm, fill=0, stroke=1)
        except Exception:
            pass

    # Build Main Column Flowables
    styles = get_common_styles(accent_hex, sidebar_hex)
    main_story = []

    # Candidate Name & Title Header
    name = data.get("name", "YOUR NAME").upper()
    title = data.get("title", "PROFESSIONAL TITLE").upper()
    
    main_story.append(Paragraph(f"<b><font size=18 color='#173F49'>{name}</font></b>", styles['Normal']))
    main_story.append(Paragraph(f"<b><font size=10 color='{accent_hex}'>{title}</font></b>", styles['Normal']))
    main_story.append(Spacer(1, 10))

    if data.get("summary"):
        main_story.append(Paragraph(data["summary"], styles['MainBodyText']))
        main_story.append(Spacer(1, 8))

    # Helper function to add sections with lines and clear spacing
    def add_section(title_text, content_key):
        if data.get(content_key):
            main_story.append(Paragraph(f"<b>{title_text}</b>", styles['MainSectionHeading']))
            # Adding Spacer ensures text does not collide with drawn line beneath section title
            main_story.append(Spacer(1, 4))
            for line in data[content_key].split("\n"):
                if line.strip():
                    formatted = line.strip() if line.strip().startswith("•") else f"• {line.strip()}"
                    main_story.append(Paragraph(formatted, styles['MainBodyText']))
            main_story.append(Spacer(1, 8))

    add_section("EXPERIENCE", "experience")
    add_section("PROJECTS", "projects")
    add_section("EDUCATION", "education")
    add_section("CERTIFICATES", "certificates")
    add_section("REFERENCES", "references")

    # Add Signature if present
    if data.get("name"):
        sig_font = 'DancingScript' if 'DancingScript' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Oblique'
        main_story.append(Spacer(1, 10))
        main_story.append(Paragraph(f"<font fontName='{sig_font}' size=16 color='#173F49'>{data['name']}</font>", styles['Normal']))

    # Frame for Main Content
    main_frame = Frame(sidebar_w + 10 * mm, 15 * mm, width - sidebar_w - 20 * mm, height - 30 * mm, topPadding=0, bottomPadding=0)
    main_frame.addFromList(main_story, c)

    c.save()


# ==========================================
# 2. CLASSIC TEMPLATE
# ==========================================
def generate_classic(data, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    styles = get_common_styles("#173F49", "#173F49")
    story = []

    # Full Header
    name = data.get("name", "YOUR NAME").upper()
    title = data.get("title", "PROFESSIONAL TITLE").upper()
    story.append(Paragraph(f"<font size=20 color='#173F49'><b>{name}</b></font>", styles['Normal']))
    story.append(Paragraph(f"<font size=11 color='#555555'><b>{title}</b></font>", styles['Normal']))
    
    contact_info = " | ".join(filter(None, [data.get("phone"), data.get("email"), data.get("location"), data.get("linkedin")]))
    if contact_info:
        story.append(Paragraph(f"<font size=8.5 color='#333333'>{contact_info}</font>", styles['Normal']))
    story.append(Spacer(1, 10))

    def add_classic_section(title_text, content_key):
        if data.get(content_key):
            story.append(Paragraph(f"<b><font color='#173F49'>{title_text}</font></b>", styles['MainSectionHeading']))
            story.append(Spacer(1, 4))
            for line in data[content_key].split("\n"):
                if line.strip():
                    story.append(Paragraph(line.strip(), styles['MainBodyText']))
            story.append(Spacer(1, 8))

    add_classic_section("SUMMARY", "summary")
    add_classic_section("EXPERIENCE", "experience")
    add_classic_section("EDUCATION", "education")
    add_classic_section("SKILLS", "skills")
    add_classic_section("CERTIFICATES", "certificates")
    add_classic_section("REFERENCES", "references")

    frame = Frame(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm)
    frame.addFromList(story, c)
    c.save()


# ==========================================
# 3. ATS CLEAN TEMPLATE
# ==========================================
def generate_ats(data, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    styles = get_common_styles("#000000", "#000000")
    story = []

    name = data.get("name", "YOUR NAME").upper()
    story.append(Paragraph(f"<font size=18><b>{name}</b></font>", styles['Normal']))
    
    contacts = [data.get("phone"), data.get("email"), data.get("location"), data.get("linkedin")]
    story.append(Paragraph(" • ".join(filter(None, contacts)), styles['Normal']))
    story.append(Spacer(1, 12))

    def add_ats_section(title_text, content_key):
        if data.get(content_key):
            story.append(Paragraph(f"<b>{title_text.upper()}</b>", styles['MainSectionHeading']))
            story.append(Spacer(1, 4))
            for line in data[content_key].split("\n"):
                if line.strip():
                    story.append(Paragraph(f"• {line.strip()}", styles['MainBodyText']))
            story.append(Spacer(1, 8))

    add_ats_section("Professional Summary", "summary")
    add_ats_section("Work Experience", "experience")
    add_ats_section("Education", "education")
    add_ats_section("Skills", "skills")
    add_ats_section("Certifications", "certificates")
    add_ats_section("References", "references")

    frame = Frame(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm)
    frame.addFromList(story, c)
    c.save()


# ==========================================
# 4. DISPATCHER ROUTER
# ==========================================
def generate_cv(template_type, data, filename):
    template = template_type.lower()
    if template == "classic":
        generate_classic(data, filename)
    elif template in ["ats", "atls"]:
        generate_ats(data, filename)
    else:
        generate_modern(data, filename)
