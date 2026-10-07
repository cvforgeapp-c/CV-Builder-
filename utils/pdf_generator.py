import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, SimpleDocTemplate, PageTemplate, Frame, Paragraph,
    Spacer, Flowable, FrameBreak, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Custom Fonts
try:
    pdfmetrics.registerFont(TTFont('Montserrat-ExtraBold', 'fonts/Montserrat-ExtraBold.ttf'))
    pdfmetrics.registerFont(TTFont('DancingScript', 'fonts/DancingScript-Regular.ttf'))
except Exception:
    pass


# ==========================================
# CUSTOM DRAWABLE FLOWABLES
# ==========================================
class HRFlowable(Flowable):
    """Horizontal divider line with customizable width, color, and margin padding."""
    def __init__(self, width, color='#D0D7D9', thickness=0.75):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness
        self.height = 6

    def draw(self):
        self.canv.saveState()
        self.canv.setStrokeColor(colors.HexColor(self.color))
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.width, 2)
        self.canv.restoreState()


class IconParagraph(Flowable):
    """Renders a vector icon circle alongside styled paragraph text for Modern template."""
    def __init__(self, icon_type, paragraph, bg_hex="#173F49", icon_color="#FFFFFF"):
        super().__init__()
        self.icon_type = icon_type
        self.paragraph = paragraph
        self.bg_hex = bg_hex
        self.icon_color = icon_color
        self.width = 0
        self.height = 0

    def wrap(self, availWidth, availHeight):
        p_w, p_h = self.paragraph.wrap(availWidth - 18, availHeight)
        self.width = availWidth
        self.height = max(14, p_h)
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        
        # Circular icon background
        x, y = 6, self.height / 2
        self.canv.setFillColor(colors.HexColor(self.bg_hex))
        self.canv.circle(x, y, 6, fill=1, stroke=0)
        
        # Vector glyphs
        self.canv.setStrokeColor(colors.HexColor(self.icon_color))
        self.canv.setFillColor(colors.HexColor(self.icon_color))
        self.canv.setLineWidth(0.8)
        
        if self.icon_type == 'phone':
            self.canv.rect(x - 1.5, y - 2.5, 3, 5, fill=0, stroke=1)
        elif self.icon_type == 'email':
            self.canv.rect(x - 2.5, y - 1.8, 5, 3.6, fill=0, stroke=1)
        elif self.icon_type == 'location':
            self.canv.circle(x, y + 0.8, 1.2, fill=0, stroke=1)
            self.canv.line(x, y - 0.5, x, y - 2.5)
        elif self.icon_type == 'linkedin':
            self.canv.setFont("Helvetica-Bold", 5)
            self.canv.drawString(x - 2, y - 1.8, "in")
        elif self.icon_type == 'website':
            self.canv.circle(x, y, 2.2, fill=0, stroke=1)
            self.canv.line(x - 2.2, y, x + 2.2, y)
        elif self.icon_type == 'experience':
            self.canv.rect(x - 2.5, y - 2, 5, 4, fill=0, stroke=1)
        elif self.icon_type == 'education':
            self.canv.line(x - 3, y - 1, x, y + 2)
            self.canv.line(x, y + 2, x + 3, y - 1)
        elif self.icon_type in ['certificates', 'projects', 'references', 'skills', 'summary']:
            self.canv.circle(x, y, 1.5, fill=1, stroke=0)

        self.canv.restoreState()
        self.paragraph.drawOn(self.canv, 16, (self.height - self.paragraph.height) / 2)


# ==========================================
# STYLES CONFIGURATION
# ==========================================
def get_common_styles(accent_hex, sidebar_hex):
    styles = getSampleStyleSheet()
    accent = colors.HexColor(accent_hex)
    dark = colors.HexColor('#1A252C')

    # Candidate Name (Header)
    styles.add(ParagraphStyle(
        'CVName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#173F49'),
        spaceBefore=0,
        spaceAfter=3,
        alignment=0
    ))

    # Candidate Title
    styles.add(ParagraphStyle(
        'CVTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=accent,
        spaceBefore=0,
        spaceAfter=8,
        alignment=0
    ))

    # Contact Bar
    styles.add(ParagraphStyle(
        'ContactBar',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#4A5568'),
        spaceBefore=0,
        spaceAfter=10
    ))

    # Section Headings
    styles.add(ParagraphStyle(
        'MainSectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#173F49'),
        spaceBefore=12,
        spaceAfter=2,
        keepWithNext=True
    ))

    # Subheaders for Jobs / Degrees (Title | Company | Dates)
    styles.add(ParagraphStyle(
        'JobSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13.5,
        textColor=dark,
        spaceBefore=5,
        spaceAfter=2,
        keepWithNext=True
    ))

    # Standard Paragraph Text
    styles.add(ParagraphStyle(
        'MainBodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=dark,
        spaceBefore=2,
        spaceAfter=3
    ))

    # Achievement Bullets
    styles.add(ParagraphStyle(
        'MainBulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=dark,
        leftIndent=12,
        spaceBefore=1,
        spaceAfter=2
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
        spaceAfter=3,
        keepWithNext=True
    ))

    # Sidebar Text
    styles.add(ParagraphStyle(
        'SidebarBodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#E0E6E8'),
        spaceBefore=2,
        spaceAfter=2
    ))

    return styles


# ==========================================
# 1. MULTI-PAGE MODERN TEMPLATE
# ==========================================
def generate_modern(data, filename):
    width, height = A4
    sidebar_w = 75 * mm
    accent_hex = data.get("accent_color", "#F2B632")
    sidebar_hex = data.get("sidebar_color", "#173F49")
    photo_path = data.get("photo")

    doc = BaseDocTemplate(filename, pagesize=A4, leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0)

    sidebar_frame = Frame(
        8 * mm, 10 * mm, sidebar_w - 16 * mm, height - 20 * mm,
        id='sidebar_frame', topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0
    )
    main_frame = Frame(
        sidebar_w + 10 * mm, 15 * mm, width - sidebar_w - 20 * mm, height - 30 * mm,
        id='main_frame', topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0
    )

    def draw_background(canvas_obj, document):
        canvas_obj.saveState()
        canvas_obj.setFillColor(colors.HexColor(sidebar_hex))
        canvas_obj.rect(0, 0, sidebar_w, height, fill=1, stroke=0)

        if document.page == 1 and photo_path and os.path.exists(photo_path):
            try:
                canvas_obj.saveState()
                path = canvas_obj.beginPath()
                path.circle(sidebar_w / 2, height - 45 * mm, 22 * mm)
                canvas_obj.clipPath(path, stroke=0)
                canvas_obj.drawImage(
                    photo_path,
                    sidebar_w / 2 - 22 * mm,
                    height - 67 * mm,
                    width=44 * mm,
                    height=44 * mm,
                    preserveAspectRatio=True
                )
                canvas_obj.restoreState()
                canvas_obj.setStrokeColor(colors.white)
                canvas_obj.setLineWidth(2)
                canvas_obj.circle(sidebar_w / 2, height - 45 * mm, 22 * mm, fill=0, stroke=1)
            except Exception:
                pass

        canvas_obj.restoreState()

    template = PageTemplate(id='two_column', frames=[sidebar_frame, main_frame], onPage=draw_background)
    doc.addPageTemplates([template])

    styles = get_common_styles(accent_hex, sidebar_hex)
    story = []

    # Sidebar Content
    top_spacer_height = 70 * mm if photo_path else 15 * mm
    story.append(Spacer(1, top_spacer_height))
    sidebar_inner_w = sidebar_w - 16 * mm

    contact_items = [
        ("phone", data.get("phone")),
        ("email", data.get("email")),
        ("location", data.get("location")),
        ("linkedin", data.get("linkedin")),
        ("website", data.get("website"))
    ]
    active_contacts = [item for item in contact_items if item[1]]
    
    if active_contacts:
        story.append(Paragraph("CONTACT", styles['SidebarHeading']))
        story.append(HRFlowable(sidebar_inner_w, color='#FFFFFF'))
        story.append(Spacer(1, 4))
        for icon_type, val in active_contacts:
            p = Paragraph(val, styles['SidebarBodyText'])
            story.append(IconParagraph(icon_type, p, bg_hex=accent_hex, icon_color="#FFFFFF"))
            story.append(Spacer(1, 2))
        story.append(Spacer(1, 6))

    def add_sidebar_section(title, content_key):
        if data.get(content_key):
            story.append(Paragraph(title, styles['SidebarHeading']))
            story.append(HRFlowable(sidebar_inner_w, color='#FFFFFF'))
            story.append(Spacer(1, 4))
            for item in data[content_key].split("\n"):
                if item.strip():
                    story.append(Paragraph(f"• {item.strip()}", styles['SidebarBodyText']))
            story.append(Spacer(1, 6))

    add_sidebar_section("SKILLS", "skills")
    add_sidebar_section("LANGUAGES", "languages")
    add_sidebar_section("INTERESTS", "hobbies")

    story.append(FrameBreak())

    # Main Column Content
    name = data.get("name", "YOUR NAME").upper()
    title = data.get("title", "PROFESSIONAL TITLE").upper()

    story.append(Paragraph(name, styles['CVName']))
    story.append(Paragraph(title, styles['CVTitle']))

    if data.get("summary"):
        story.append(Paragraph(data["summary"], styles['MainBodyText']))
        story.append(Spacer(1, 6))

    main_column_w = width - sidebar_w - 20 * mm

    def add_main_section(title_text, content_key, icon_type):
        if data.get(content_key):
            heading_p = Paragraph(title_text, styles['MainSectionHeading'])
            story.append(IconParagraph(icon_type, heading_p, bg_hex=sidebar_hex, icon_color="#FFFFFF"))
            story.append(HRFlowable(main_column_w, color='#D0D7D9'))
            story.append(Spacer(1, 6))

            for line in data[content_key].split("\n"):
                line_str = line.strip()
                if line_str:
                    if "|" in line_str:
                        story.append(Paragraph(f"<b>{line_str}</b>", styles['JobSubHeader']))
                    elif line_str.startswith("•"):
                        story.append(Paragraph(line_str, styles['MainBulletText']))
                    else:
                        story.append(Paragraph(f"• {line_str}", styles['MainBulletText']))
            story.append(Spacer(1, 8))

    add_main_section("EXPERIENCE", "experience", "experience")
    add_main_section("PROJECTS", "projects", "projects")
    add_main_section("EDUCATION", "education", "education")
    add_main_section("CERTIFICATES", "certificates", "certificates")
    add_main_section("REFERENCES", "references", "references")

    if data.get("name"):
        sig_font = 'DancingScript' if 'DancingScript' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Oblique'
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"<font fontName='{sig_font}' size=16 color='#173F49'>{data['name']}</font>", styles['Normal']))

    doc.build(story)


# ==========================================
# 2. INTERNATIONAL CLASSIC TEMPLATE
# ==========================================
def generate_classic(data, filename):
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm
    )
    styles = get_common_styles("#173F49", "#173F49")
    story = []

    name = data.get("name", "YOUR NAME").upper()
    title = data.get("title", "").upper()

    # Clean Classic Header
    story.append(Paragraph(name, styles['CVName']))
    if title:
        story.append(Paragraph(title, styles['CVTitle']))

    contact_info = " | ".join(filter(None, [
        data.get("phone"),
        data.get("email"),
        data.get("location"),
        data.get("linkedin"),
        data.get("website")
    ]))
    if contact_info:
        story.append(Paragraph(contact_info, styles['ContactBar']))

    page_w = A4[0] - 36 * mm

    def add_classic_section(title_text, content_key):
        if data.get(content_key):
            story.append(Paragraph(title_text.upper(), styles['MainSectionHeading']))
            story.append(HRFlowable(page_w, color='#173F49', thickness=1.0))
            story.append(Spacer(1, 6))

            for line in data[content_key].split("\n"):
                line_str = line.strip()
                if line_str:
                    if "|" in line_str:
                        story.append(Paragraph(line_str, styles['JobSubHeader']))
                    elif line_str.startswith("•"):
                        story.append(Paragraph(line_str, styles['MainBulletText']))
                    elif content_key in ["summary", "references"]:
                        story.append(Paragraph(line_str, styles['MainBodyText']))
                    else:
                        story.append(Paragraph(f"• {line_str}", styles['MainBulletText']))
            story.append(Spacer(1, 8))

    add_classic_section("Summary", "summary")
    add_classic_section("Experience", "experience")
    add_classic_section("Education", "education")
    add_classic_section("Skills", "skills")
    add_classic_section("Certificates", "certificates")
    add_classic_section("References", "references")

    doc.build(story)


# ==========================================
# 3. INTERNATIONAL ATS CLEAN TEMPLATE
# ==========================================
def generate_ats(data, filename):
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm
    )
    styles = get_common_styles("#000000", "#000000")
    
    # Custom high-readability ATS Heading Override
    styles['CVName'].textColor = colors.HexColor('#000000')
    styles['CVName'].fontSize = 20
    styles['CVName'].leading = 24
    styles['CVName'].alignment = 0

    styles['MainSectionHeading'].textColor = colors.HexColor('#000000')
    styles['MainSectionHeading'].fontSize = 11
    styles['MainSectionHeading'].leading = 14

    styles['JobSubHeader'].textColor = colors.HexColor('#000000')

    story = []

    # 1. Clean Top Header
    name = data.get("name", "YOUR NAME").upper()
    story.append(Paragraph(name, styles['CVName']))

    title = data.get("title", "").upper()
    if title:
        styles.add(ParagraphStyle('ATSTitle', parent=styles['CVTitle'], textColor=colors.HexColor('#333333')))
        story.append(Paragraph(title, styles['ATSTitle']))

    contacts = [data.get("phone"), data.get("email"), data.get("location"), data.get("linkedin"), data.get("website")]
    active_contacts = [c for c in contacts if c]
    if active_contacts:
        story.append(Paragraph(" • ".join(active_contacts), styles['ContactBar']))

    page_w = A4[0] - 36 * mm

    # 2. Section Helper
    def add_ats_section(title_text, content_key):
        if data.get(content_key):
            # Clean Section Heading Without Any Bullets
            story.append(Paragraph(title_text.upper(), styles['MainSectionHeading']))
            story.append(HRFlowable(page_w, color="#000000", thickness=0.8))
            story.append(Spacer(1, 6))

            lines = [l.strip() for l in data[content_key].split("\n") if l.strip()]

            # Handle Skills as 2-column table grid for space optimization
            if content_key == "skills" and len(lines) > 2:
                table_data = []
                for i in range(0, len(lines), 2):
                    col1 = Paragraph(f"• {lines[i].lstrip('• ')}", styles['MainBodyText'])
                    col2 = Paragraph(f"• {lines[i+1].lstrip('• ')}", styles['MainBodyText']) if i + 1 < len(lines) else ""
                    table_data.append([col1, col2])
                
                t = Table(table_data, colWidths=[page_w * 0.5, page_w * 0.5])
                t.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                ]))
                story.append(t)
            else:
                for line_str in lines:
                    if "|" in line_str:
                        # Job Header Line (e.g. Title | Company | Location | Dates)
                        story.append(Paragraph(line_str, styles['JobSubHeader']))
                    elif line_str.startswith("•"):
                        story.append(Paragraph(line_str, styles['MainBulletText']))
                    elif content_key in ["summary", "references"]:
                        story.append(Paragraph(line_str, styles['MainBodyText']))
                    else:
                        story.append(Paragraph(f"• {line_str}", styles['MainBulletText']))

            story.append(Spacer(1, 8))

    add_ats_section("Professional Summary", "summary")
    add_ats_section("Work Experience", "experience")
    add_ats_section("Education", "education")
    add_ats_section("Skills", "skills")
    add_ats_section("Certifications", "certificates")
    add_ats_section("References", "references")

    doc.build(story)


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
