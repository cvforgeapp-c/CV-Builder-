import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, SimpleDocTemplate, PageTemplate, Frame, Paragraph,
    Spacer, Flowable, FrameBreak
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
# CUSTOM DRAWABLE FLOWABLES (ICONS & LINES)
# ==========================================
class HRFlowable(Flowable):
    """Horizontal rule with customizable color and margin padding."""
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
    """Flowable row rendering a vector icon followed by styled text."""
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
        
        # 1. Draw circular icon background
        x, y = 6, self.height / 2
        self.canv.setFillColor(colors.HexColor(self.bg_hex))
        self.canv.circle(x, y, 6, fill=1, stroke=0)
        
        # 2. Draw vector glyphs
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
        elif self.icon_type in ['certificates', 'projects', 'references']:
            self.canv.circle(x, y, 1.5, fill=1, stroke=0)

        self.canv.restoreState()
        
        # 3. Draw text paragraph next to icon
        self.paragraph.drawOn(self.canv, 16, (self.height - self.paragraph.height) / 2)


# ==========================================
# STYLES CONFIGURATION
# ==========================================
def get_common_styles(accent_hex, sidebar_hex):
    styles = getSampleStyleSheet()
    accent = colors.HexColor(accent_hex)
    dark = colors.HexColor('#1A252C')

    # Resolve Name & Title overlap with distinct leading and spaceAfter
    styles.add(ParagraphStyle(
        'CVName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#173F49'),
        spaceBefore=0,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'CVTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=accent,
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
        spaceBefore=10,
        spaceAfter=2,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'MainBodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=dark,
        spaceBefore=3,
        spaceAfter=3
    ))

    styles.add(ParagraphStyle(
        'SidebarHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.white,
        spaceBefore=10,
        spaceAfter=2,
        keepWithNext=True
    ))

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

    # Frame 1: Sidebar Column
    sidebar_frame = Frame(
        8 * mm, 10 * mm, sidebar_w - 16 * mm, height - 20 * mm,
        id='sidebar_frame', topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0
    )

    # Frame 2: Main Column
    main_frame = Frame(
        sidebar_w + 10 * mm, 15 * mm, width - sidebar_w - 20 * mm, height - 30 * mm,
        id='main_frame', topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0
    )

    def draw_background(canvas_obj, document):
        canvas_obj.saveState()
        
        # Draw full sidebar background on every page
        canvas_obj.setFillColor(colors.HexColor(sidebar_hex))
        canvas_obj.rect(0, 0, sidebar_w, height, fill=1, stroke=0)

        # Draw profile photo on page 1
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

    # ------------------------------------
    # A. SIDEBAR COLUMN CONTENT
    # ------------------------------------
    top_spacer_height = 70 * mm if photo_path else 15 * mm
    story.append(Spacer(1, top_spacer_height))

    sidebar_inner_w = sidebar_w - 16 * mm

    # Contact Details with Icons
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

    # Helper for Sidebar Lists with Divider Lines
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

    # Move from Sidebar Frame into Main Frame
    story.append(FrameBreak())

    # ------------------------------------
    # B. MAIN COLUMN CONTENT
    # ------------------------------------
    name = data.get("name", "YOUR NAME").upper()
    title = data.get("title", "PROFESSIONAL TITLE").upper()

    story.append(Paragraph(name, styles['CVName']))
    story.append(Paragraph(title, styles['CVTitle']))

    if data.get("summary"):
        story.append(Paragraph(data["summary"], styles['MainBodyText']))
        story.append(Spacer(1, 6))

    main_column_w = width - sidebar_w - 20 * mm

    # Helper for Main Column Sections with Icons and Divider Lines
    def add_main_section(title_text, content_key, icon_type):
        if data.get(content_key):
            heading_p = Paragraph(title_text, styles['MainSectionHeading'])
            story.append(IconParagraph(icon_type, heading_p, bg_hex=sidebar_hex, icon_color="#FFFFFF"))
            story.append(HRFlowable(main_column_w, color='#D0D7D9'))
            
            # Target Spacing below section line
            story.append(Spacer(1, 6))

            for line in data[content_key].split("\n"):
                if line.strip():
                    formatted = line.strip() if line.strip().startswith("•") else f"• {line.strip()}"
                    story.append(Paragraph(formatted, styles['MainBodyText']))
            story.append(Spacer(1, 8))

    add_main_section("EXPERIENCE", "experience", "experience")
    add_main_section("PROJECTS", "projects", "projects")
    add_main_section("EDUCATION", "education", "education")
    add_main_section("CERTIFICATES", "certificates", "certificates")
    add_main_section("REFERENCES", "references", "references")

    # Signature
    if data.get("name"):
        sig_font = 'DancingScript' if 'DancingScript' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Oblique'
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"<font fontName='{sig_font}' size=16 color='#173F49'>{data['name']}</font>", styles['Normal']))

    doc.build(story)


# ==========================================
# 2. CLASSIC TEMPLATE
# ==========================================
def generate_classic(data, filename):
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = get_common_styles("#173F49", "#173F49")
    story = []

    name = data.get("name", "YOUR NAME").upper()
    title = data.get("title", "PROFESSIONAL TITLE").upper()
    story.append(Paragraph(name, styles['CVName']))
    story.append(Paragraph(title, styles['CVTitle']))
    
    contact_info = " | ".join(filter(None, [data.get("phone"), data.get("email"), data.get("location"), data.get("linkedin")]))
    if contact_info:
        story.append(Paragraph(contact_info, styles['MainBodyText']))
    story.append(Spacer(1, 10))

    def add_classic_section(title_text, content_key):
        if data.get(content_key):
            story.append(Paragraph(title_text, styles['MainSectionHeading']))
            story.append(HRFlowable(A4[0] - 30 * mm, color='#173F49'))
            story.append(Spacer(1, 6))
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

    doc.build(story)


# ==========================================
# 3. ATS TEMPLATE
# ==========================================
def generate_ats(data, filename):
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = get_common_styles("#000000", "#000000")
    story = []

    name = data.get("name", "YOUR NAME").upper()
    story.append(Paragraph(name, styles['CVName']))
    
    contacts = [data.get("phone"), data.get("email"), data.get("location"), data.get("linkedin")]
    story.append(Paragraph(" • ".join(filter(None, contacts)), styles['MainBodyText']))
    story.append(Spacer(1, 12))

    def add_ats_section(title_text, content_key):
        if data.get(content_key):
            story.append(Paragraph(title_text.upper(), styles['MainSectionHeading']))
            story.append(HRFlowable(A4[0] - 30 * mm, color="#000000"))
            story.append(Spacer(1, 6))
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
