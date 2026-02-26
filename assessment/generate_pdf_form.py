#!/usr/bin/env python3
"""
Generate fillable PDF assessment forms for Claw Agents Provisioner.

Creates professional AcroForm PDFs in two tiers:
  - Private:    Simple, warm, non-technical. For small businesses and individuals.
  - Enterprise: Complete and technical, split into Part A (client) and Part B (Amenthyx).

Both tiers produce the same JSON schema output via pdf_to_json.py.

Usage:
    python assessment/generate_pdf_form.py --tier private
    python assessment/generate_pdf_form.py --tier enterprise
    python assessment/generate_pdf_form.py --tier private  --prefill assessment/client-assessment.example.json
    python assessment/generate_pdf_form.py --tier enterprise --prefill assessment/client-assessment.example.json -o custom.pdf

Requirements:
    pip install reportlab
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
except ImportError:
    print("ERROR: reportlab is required.  pip install reportlab", file=sys.stderr)
    sys.exit(1)


# ── Page Constants ───────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4
MARGIN_L = 25 * mm
MARGIN_R = 25 * mm
MARGIN_T = 20 * mm
MARGIN_B = 22 * mm
USABLE_W = PAGE_W - MARGIN_L - MARGIN_R

FIELD_H = 20
CHECKBOX_SIZE = 12
LINE_GAP = 10          # generous gap after every field
SECTION_GAP = 14       # extra gap before each section header
LABEL_FIELD_GAP = 4    # gap between label text and its input field


# ── Color Palette ────────────────────────────────────────────────────────────

HEADER_DARK    = HexColor("#1B2A4A")
HEADER_LIGHT   = HexColor("#2D4A7A")
SECTION_BLUE   = HexColor("#2D4A7A")
SECTION_PURPLE = HexColor("#7C3AED")
LABEL_COLOR    = HexColor("#374151")
HINT_COLOR     = HexColor("#9CA3AF")
FIELD_BORDER   = HexColor("#D1D5DB")
FIELD_BG       = HexColor("#FFFFFF")
SELECT_BG      = HexColor("#F9FAFB")
CATEGORY_CLR   = HexColor("#6B7280")
MUTED_BLUE     = HexColor("#B0C4DE")


# ── Human-Readable Labels ───────────────────────────────────────────────────

LABEL_MAP = {
    # Industries
    "real-estate": "Real Estate", "e-commerce": "E-Commerce",
    "healthcare": "Healthcare", "legal": "Legal", "finance": "Finance",
    "technology": "Technology", "education": "Education",
    "manufacturing": "Manufacturing", "retail": "Retail",
    "hospitality": "Hospitality", "agriculture": "Agriculture",
    "energy": "Energy", "telecommunications": "Telecom",
    "government": "Government", "nonprofit": "Nonprofit",
    "automotive": "Automotive", "insurance": "Insurance",
    "logistics": "Logistics", "food-service": "Food & Restaurant",
    "entertainment": "Entertainment", "cybersecurity": "Cybersecurity",
    "consulting": "Consulting", "media": "Media", "fitness": "Fitness",
    "other": "Other",
    # Company sizes
    "solo": "Solo / Freelancer", "2-10": "2\u201310 employees",
    "11-50": "11\u201350 employees", "51-200": "51\u2013200 employees",
    "201-1000": "201\u20131000 employees", "1000+": "1000+ employees",
    # Devices
    "desktop": "Desktop", "laptop": "Laptop", "mobile": "Mobile Phone",
    "tablet": "Tablet", "raspberry-pi": "Raspberry Pi", "server": "Server",
    "iot-device": "IoT Device",
    # OS
    "linux": "Linux", "macos": "macOS", "windows": "Windows",
    "android": "Android", "ios": "iOS", "embedded": "Embedded", "any": "Any",
    # Tones
    "formal": "Formal", "professional": "Professional", "casual": "Casual",
    "friendly": "Friendly", "technical": "Technical", "empathetic": "Empathetic",
    # Verbosity
    "concise": "Concise", "balanced": "Balanced",
    "detailed": "Detailed", "verbose": "Verbose",
    # Sensitivity
    "low": "Low", "medium": "Medium", "high": "High", "critical": "Critical",
    # Storage
    "local-only": "On Your Computer Only",
    "private-cloud": "Private Cloud", "any-cloud": "Any Cloud",
    # PII
    "none": "None", "anonymize": "Anonymize",
    "encrypt": "Encrypt", "no-store": "Do Not Store",
    # Response time
    "instant": "Instant", "fast": "Fast",
    "moderate": "Moderate", "relaxed": "Relaxed",
    # Availability
    "best-effort": "Best Effort", "business-hours": "Business Hours",
    "24-7": "24/7",
    # Context length
    "short": "Short (4K)", "medium": "Medium (32K)",
    "long": "Long (128K)", "maximum": "Maximum (1M+)",
    # Cost priority
    "minimize-cost": "Minimize Cost", "balance": "Balance",
    "maximize-quality": "Maximize Quality",
    # Channels
    "telegram": "Telegram", "whatsapp": "WhatsApp", "discord": "Discord",
    "slack": "Slack", "web-chat": "Web Chat", "email": "Email",
    "sms": "SMS", "api-only": "API Only", "cli": "CLI",
    # Regulations
    "none": "None", "gdpr": "GDPR", "hipaa": "HIPAA", "soc2": "SOC 2",
    "pci-dss": "PCI-DSS", "ccpa": "CCPA", "ferpa": "FERPA",
    "iso27001": "ISO 27001",
    # Priority / Complexity
    "single-focus": "Single Focus", "multi-task": "Multi-Task",
    "generalist": "Generalist",
    "simple": "Simple", "complex": "Complex", "expert": "Expert",
    # Service packages
    "private": "Private", "enterprise": "Enterprise",
    "managed": "Managed", "ongoing": "Ongoing",
    # Response formats
    "plain-text": "Plain Text", "markdown": "Markdown", "html": "HTML",
    "bullet-points": "Bullet Points", "numbered-lists": "Numbered Lists",
    "tables": "Tables",
    # Fine-tuning methods
    "lora": "LoRA", "qlora": "QLoRA", "prompt-only": "Prompt Only",
    # Use cases (50)
    "customer-support": "Customer Support", "sales-crm": "Sales & CRM",
    "personal-finance": "Personal Finance", "code-review": "Code Review",
    "email-management": "Email Management",
    "calendar-scheduling": "Calendar & Scheduling",
    "meeting-summarization": "Meeting Summarization",
    "hr-recruitment": "HR & Recruitment", "it-helpdesk": "IT Helpdesk",
    "content-writing": "Content Writing", "social-media": "Social Media",
    "translation-multilingual": "Translation",
    "education-tutoring": "Education & Tutoring",
    "research-summarization": "Research & Summarization",
    "data-analysis": "Data Analysis",
    "project-management": "Project Management",
    "accounting-bookkeeping": "Accounting",
    "insurance-claims": "Insurance Claims",
    "travel-hospitality": "Travel & Hospitality",
    "food-restaurant": "Food & Restaurant",
    "fitness-wellness": "Fitness & Wellness",
    "automotive-vehicle": "Automotive",
    "supply-chain-logistics": "Supply Chain",
    "manufacturing-qa": "Manufacturing QA",
    "agriculture-farming": "Agriculture",
    "energy-utilities": "Energy & Utilities",
    "cybersecurity-threat-intel": "Cybersecurity",
    "devops-infrastructure": "DevOps",
    "api-integration-webhooks": "API Integration",
    "database-administration": "Database Admin",
    "iot-smart-home": "IoT & Smart Home",
    "chatbot-conversational": "Chatbot",
    "document-processing": "Document Processing",
    "knowledge-base-faq": "Knowledge Base",
    "compliance-regulatory": "Compliance",
    "onboarding-training": "Onboarding & Training",
    "sentiment-analysis": "Sentiment Analysis",
    "creative-writing": "Creative Writing",
    "music-entertainment": "Music & Entertainment",
    "gaming-virtual-worlds": "Gaming",
    "mental-health-counseling": "Mental Health",
    "personal-finance-budgeting": "Personal Budgeting",
    "event-planning": "Event Planning",
    "nonprofit-fundraising": "Nonprofit & Fundraising",
    "government-public-services": "Government Services",
}


# ── Use Case Categories (50 total) ──────────────────────────────────────────

USE_CASE_CATEGORIES = [
    ("Customer & Sales", [
        "customer-support", "sales-crm", "e-commerce", "personal-finance",
    ]),
    ("Professional Services", [
        "real-estate", "healthcare", "legal", "insurance-claims",
        "accounting-bookkeeping",
    ]),
    ("Communication & Content", [
        "email-management", "content-writing", "social-media",
        "translation-multilingual", "creative-writing",
    ]),
    ("Operations & Management", [
        "calendar-scheduling", "meeting-summarization", "project-management",
        "hr-recruitment", "event-planning", "onboarding-training",
        "supply-chain-logistics",
    ]),
    ("Data & Analytics", [
        "data-analysis", "research-summarization", "sentiment-analysis",
        "document-processing",
    ]),
    ("Technical", [
        "code-review", "it-helpdesk", "devops-infrastructure",
        "api-integration-webhooks", "database-administration",
        "iot-smart-home", "cybersecurity-threat-intel",
    ]),
    ("Industry-Specific", [
        "education-tutoring", "travel-hospitality", "food-restaurant",
        "fitness-wellness", "automotive-vehicle", "manufacturing-qa",
        "agriculture-farming", "energy-utilities", "telecommunications",
        "government-public-services", "nonprofit-fundraising",
    ]),
    ("Other", [
        "chatbot-conversational", "knowledge-base-faq",
        "compliance-regulatory", "gaming-virtual-worlds",
        "mental-health-counseling", "music-entertainment",
        "personal-finance-budgeting",
    ]),
]


# ── Enum Constants ───────────────────────────────────────────────────────────

INDUSTRIES = [
    "real-estate", "e-commerce", "healthcare", "legal", "finance",
    "technology", "education", "manufacturing", "retail", "hospitality",
    "agriculture", "energy", "telecommunications", "government", "nonprofit",
    "automotive", "insurance", "logistics", "food-service", "entertainment",
    "cybersecurity", "consulting", "media", "fitness", "other",
]

COMPANY_SIZES    = ["solo", "2-10", "11-50", "51-200", "201-1000", "1000+"]
DEVICES          = ["desktop", "laptop", "mobile", "tablet", "raspberry-pi", "server", "iot-device"]
OS_OPTIONS       = ["linux", "macos", "windows", "android", "ios", "embedded", "any"]
SERVICE_PACKAGES = ["private", "enterprise", "managed", "ongoing"]
TONES            = ["formal", "professional", "casual", "friendly", "technical", "empathetic"]
VERBOSITY        = ["concise", "balanced", "detailed", "verbose"]
RESPONSE_FORMATS = ["plain-text", "markdown", "html", "bullet-points", "numbered-lists", "tables"]
SENSITIVITY      = ["low", "medium", "high", "critical"]
STORAGE          = ["local-only", "private-cloud", "any-cloud"]
PII_HANDLING     = ["none", "anonymize", "encrypt", "no-store"]
RESPONSE_TIME    = ["instant", "fast", "moderate", "relaxed"]
AVAILABILITY     = ["best-effort", "business-hours", "24-7"]
CONTEXT_LENGTH   = ["short", "medium", "long", "maximum"]
COST_PRIORITY    = ["minimize-cost", "balance", "maximize-quality"]
CHANNELS         = ["telegram", "whatsapp", "discord", "slack", "web-chat", "email", "sms", "api-only", "cli"]
REGULATIONS      = ["none", "gdpr", "hipaa", "soc2", "pci-dss", "ccpa", "ferpa", "iso27001"]
FT_METHODS       = ["lora", "qlora", "prompt-only"]
LORA_RANKS       = ["8", "16", "32", "64"]


def _labels(items):
    """Return human-readable labels for a list of enum values."""
    return [LABEL_MAP.get(i, i.replace("-", " ").title()) for i in items]


# ═════════════════════════════════════════════════════════════════════════════
#  PDFFormBuilder
# ═════════════════════════════════════════════════════════════════════════════

class PDFFormBuilder:
    """Builds a multi-page fillable PDF assessment form (Private or Enterprise)."""

    def __init__(self, output_path: str, tier: str = "private", prefill: dict = None):
        self.output_path = output_path
        self.tier = tier
        self.prefill = prefill or {}
        self.c = canvas.Canvas(output_path, pagesize=A4)
        self.c.setTitle(f"AI Agent Assessment \u2014 {tier.title()}")
        self.c.setAuthor("Amenthyx AI")
        self.c.setSubject("Claw Agents Assessment v3.0")
        self.y = PAGE_H - MARGIN_T
        self.page_num = 0

    # ── Drawing Utilities ─────────────────────────────────────────────────

    def _new_page(self):
        if self.page_num > 0:
            self._draw_footer()
            self.c.showPage()
        self.page_num += 1
        self.y = PAGE_H - MARGIN_T

    def _draw_footer(self):
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(
            MARGIN_L, 12 * mm,
            f"Claw Agents Provisioner \u2014 Amenthyx AI  \u00b7  Page {self.page_num}",
        )
        self.c.setFillColor(black)

    def _check_space(self, needed: float):
        if self.y - needed < MARGIN_B + 10:
            self._draw_footer()
            self.c.showPage()
            self.page_num += 1
            self.y = PAGE_H - MARGIN_T

    def _draw_gradient_rect(self, x, y, w, h, color1, color2, steps=20):
        """Simulate a top-to-bottom gradient with horizontal strips."""
        strip_h = h / steps
        r1, g1, b1 = color1.red, color1.green, color1.blue
        r2, g2, b2 = color2.red, color2.green, color2.blue
        for i in range(steps):
            t = i / max(steps - 1, 1)
            r = r1 + (r2 - r1) * t
            g = g1 + (g2 - g1) * t
            b = b1 + (b2 - b1) * t
            c = HexColor(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
            self.c.setFillColor(c)
            self.c.rect(x, y + h - (i + 1) * strip_h, w, strip_h + 0.5,
                        fill=True, stroke=False)

    def _draw_header(self):
        header_h = 48 * mm
        self._draw_gradient_rect(0, PAGE_H - header_h, PAGE_W, header_h,
                                 HEADER_DARK, HEADER_LIGHT)

        self.c.setFillColor(white)
        self.c.setFont("Helvetica-Bold", 24)
        self.c.drawString(MARGIN_L, PAGE_H - 20 * mm, "AI Agent Assessment")

        self.c.setFont("Helvetica", 13)
        subtitle = (
            "Let\u2019s design your perfect AI assistant"
            if self.tier == "private"
            else "Enterprise AI Agent Configuration"
        )
        self.c.drawString(MARGIN_L, PAGE_H - 28 * mm, subtitle)

        self.c.setFont("Helvetica", 9)
        self.c.setFillColor(MUTED_BLUE)
        self.c.drawString(
            MARGIN_L, PAGE_H - 36 * mm,
            f"Version 3.0  |  {self.tier.title()} Tier  |  {date.today().isoformat()}",
        )
        self.c.setFillColor(black)
        self.y = PAGE_H - header_h - 10 * mm

    def _section_header(self, number, title, accent=None):
        self._check_space(50)
        self.y -= SECTION_GAP
        color = accent or SECTION_BLUE
        self.c.setFillColor(color)
        self.c.roundRect(MARGIN_L, self.y - 22, USABLE_W, 26, 5,
                         fill=True, stroke=False)
        self.c.setFillColor(white)
        self.c.setFont("Helvetica-Bold", 12)
        self.c.drawString(MARGIN_L + 12, self.y - 16,
                          f"Section {number}: {title}")
        self.c.setFillColor(black)
        self.y -= 38

    def _part_divider(self, title, subtitle):
        """Draw Part B banner on a fresh page."""
        self._new_page()
        self.y -= 6
        self.c.setFillColor(SECTION_PURPLE)
        self.c.roundRect(MARGIN_L, self.y - 48, USABLE_W, 52, 6,
                         fill=True, stroke=False)
        self.c.setFillColor(white)
        self.c.setFont("Helvetica-Bold", 16)
        self.c.drawString(MARGIN_L + 16, self.y - 22, title)
        self.c.setFont("Helvetica", 10)
        self.c.drawString(MARGIN_L + 16, self.y - 40, subtitle)
        self.c.setFillColor(black)
        self.y -= 68

    def _category_label(self, text):
        self._check_space(20)
        self.y -= 6
        self.c.setFont("Helvetica-Bold", 8)
        self.c.setFillColor(CATEGORY_CLR)
        self.c.drawString(MARGIN_L + 2, self.y, text)
        self.c.setFillColor(black)
        self.y -= 14

    # ── Field Primitives (all single-column, full width) ──────────────────

    def _label(self, text: str, required: bool = False):
        self._check_space(FIELD_H + 20)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, f"{text} *" if required else text)
        self.c.setFillColor(black)
        self.y -= (10 + LABEL_FIELD_GAP)

    def _hint_line(self, text: str):
        """Draw a hint line below the label, above the field."""
        self.c.setFont("Helvetica", 7)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y + 2, text)
        self.c.setFillColor(black)

    def _text_field(self, name, width=None, height=None, tooltip="", value=""):
        h = height or FIELD_H
        self._check_space(h + 4)
        w = width or USABLE_W
        self.c.acroForm.textfield(
            name=name, tooltip=tooltip,
            x=MARGIN_L, y=self.y - h, width=w, height=h,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            textColor=black, fontSize=9, fieldFlags="", value=value,
        )
        self.y -= (h + LINE_GAP)

    def _text_area(self, name, height=55, tooltip="", value=""):
        self._check_space(height + 4)
        self.c.acroForm.textfield(
            name=name, tooltip=tooltip,
            x=MARGIN_L, y=self.y - height, width=USABLE_W, height=height,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            textColor=black, fontSize=9, fieldFlags="multiline", value=value,
        )
        self.y -= (height + LINE_GAP)

    def _select_field(self, name, options, width=None, tooltip="", value=""):
        """Full-width text field with hint showing valid options."""
        w = width or USABLE_W
        self._check_space(FIELD_H + 4)
        labels = ", ".join(_labels(options))
        max_chars = int(w / 3.2)
        if len(labels) > max_chars:
            labels = labels[:max_chars] + "\u2026"
        self._hint_line(labels)
        valid = ", ".join(options)
        tip = f"{tooltip}\nType one of: {valid}" if tooltip else f"Type one of: {valid}"
        self.c.acroForm.textfield(
            name=name, tooltip=tip,
            x=MARGIN_L, y=self.y - FIELD_H, width=w, height=FIELD_H,
            borderColor=FIELD_BORDER, fillColor=SELECT_BG,
            textColor=black, fontSize=9, value=value,
        )
        self.y -= (FIELD_H + LINE_GAP)

    def _checkbox(self, name, label, x, checked=False):
        self.c.acroForm.checkbox(
            name=name, tooltip=label,
            x=x, y=self.y - CHECKBOX_SIZE, size=CHECKBOX_SIZE,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            buttonStyle="check", checked=checked,
        )
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(x + CHECKBOX_SIZE + 4, self.y - CHECKBOX_SIZE + 2,
                          label)
        self.c.setFillColor(black)

    def _checkbox_row(self, name, label, checked=False):
        """Single checkbox on its own row, full width."""
        self._check_space(CHECKBOX_SIZE + 10)
        self._checkbox(name, label, MARGIN_L, checked=checked)
        self.y -= (CHECKBOX_SIZE + 10)

    def _checkbox_grid(self, prefix, items, cols=3, checked_items=None):
        checked_items = checked_items or []
        col_w = USABLE_W / cols
        rows = [items[i:i + cols] for i in range(0, len(items), cols)]
        for row in rows:
            self._check_space(CHECKBOX_SIZE + 8)
            for j, item in enumerate(row):
                x = MARGIN_L + j * col_w
                field_name = f"{prefix}_{item.replace('-', '_')}"
                label = LABEL_MAP.get(item, item.replace("-", " ").title())
                self._checkbox(field_name, label, x, checked=item in checked_items)
            self.y -= (CHECKBOX_SIZE + 8)

    def _categorized_use_cases(self, checked_items=None):
        checked_items = checked_items or []
        for cat_name, items in USE_CASE_CATEGORIES:
            self._category_label(cat_name)
            self._checkbox_grid("uc", items, cols=3, checked_items=checked_items)

    # ── Prefill Helpers ───────────────────────────────────────────────────

    def _get_prefill(self, *keys, default=""):
        val = self.prefill
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, list):
            return val
        return str(val) if val is not None else default

    def _pf_list(self, *keys):
        v = self._get_prefill(*keys, default=[])
        return v if isinstance(v, list) else []

    def _pf_bool(self, *keys):
        v = self._get_prefill(*keys, default=False)
        return v is True or v == "True"

    # ══════════════════════════════════════════════════════════════════════
    #  FIELD BUILDERS  (every question gets its own full-width row)
    # ══════════════════════════════════════════════════════════════════════

    def _build_profile_fields(self, enterprise=False):
        self._label("Company Name", required=True)
        self._text_field("cp_company_name", tooltip="Legal or trading name",
                         value=self._get_prefill("client_profile", "company_name"))

        self._label("Contact Name", required=True)
        self._text_field("cp_contact_name", tooltip="Primary contact person",
                         value=self._get_prefill("client_profile", "contact_name"))

        self._label("Contact Email")
        self._text_field("cp_contact_email", tooltip="Primary contact email",
                         value=self._get_prefill("client_profile", "contact_email"))

        self._label("Industry", required=True)
        self._select_field("cp_industry", INDUSTRIES,
                           tooltip="Primary industry",
                           value=self._get_prefill("client_profile", "industry"))

        self._label("Industry (if 'other')")
        self._text_field("cp_industry_other",
                         tooltip="Specify if industry is 'other'",
                         value=self._get_prefill("client_profile", "industry_other"))

        self._label("Company Size", required=True)
        self._select_field("cp_company_size", COMPANY_SIZES,
                           tooltip="Number of employees",
                           value=self._get_prefill("client_profile", "company_size"))

        if enterprise:
            self._label("Service Package", required=True)
            self._select_field("cp_service_package", SERVICE_PACKAGES,
                               value=self._get_prefill("client_profile", "service_package"))

            self._label("Operating System")
            self._select_field("cp_operating_system", OS_OPTIONS,
                               value=self._get_prefill("client_profile", "operating_system"))

        self._label("Primary Devices (check all that apply)", required=True)
        self._checkbox_grid("cp_device", DEVICES, cols=4,
                            checked_items=self._pf_list("client_profile",
                                                        "primary_devices"))

    def _build_use_case_fields(self):
        self._label("Primary Use Cases (check all that apply)", required=True)
        self._categorized_use_cases(
            checked_items=self._pf_list("use_cases", "primary_use_cases"))

        self._label("Secondary Use Cases (comma-separated, free text)")
        secondary = self._get_prefill("use_cases", "secondary_use_cases",
                                      default=[])
        if isinstance(secondary, list):
            secondary = ", ".join(secondary)
        self._text_field("uc_secondary",
                         tooltip="Additional use cases not in list above",
                         value=secondary)

        self._label("Priority")
        self._select_field("uc_priority",
                           ["single-focus", "multi-task", "generalist"],
                           value=self._get_prefill("use_cases",
                                                   "use_case_priority"))

        self._label("Complexity")
        self._select_field("uc_complexity",
                           ["simple", "moderate", "complex", "expert"],
                           value=self._get_prefill("use_cases",
                                                   "complexity_level"))

        self._label("Specific Requirements")
        self._text_area("uc_domain_requirements", height=60,
                        tooltip="Industry-specific needs",
                        value=self._get_prefill("use_cases",
                                                "domain_specific_requirements"))

    def _build_communication_fields(self, enterprise=False):
        self._label("Languages", required=True)
        self._check_space(FIELD_H + 4)
        self._hint_line("e.g., English, Italian, German  \u2014  or ISO codes: en, it, de")
        langs = self._get_prefill("communication_preferences", "languages",
                                  default=[])
        if isinstance(langs, list):
            langs = ", ".join(langs)
        self._text_field("comm_languages",
                         tooltip="Languages your agent should speak",
                         value=langs)

        self._label("Primary Language")
        self._text_field("comm_primary_language",
                         tooltip="Main language (e.g., en, it)",
                         value=self._get_prefill("communication_preferences",
                                                 "primary_language"))

        self._label("Tone", required=True)
        self._select_field("comm_tone", TONES,
                           value=self._get_prefill("communication_preferences",
                                                   "tone"))

        self._label("Verbosity")
        self._select_field("comm_verbosity", VERBOSITY,
                           value=self._get_prefill("communication_preferences",
                                                   "verbosity"))

        self._label("Agent Name")
        self._text_field("comm_persona_name",
                         tooltip="Give your AI agent a name (e.g., Sara, Alex)",
                         value=self._get_prefill("communication_preferences",
                                                 "persona_name"))

        self._label("Agent Description")
        self._text_area("comm_persona_description", height=50,
                        tooltip="Describe your agent's personality",
                        value=self._get_prefill("communication_preferences",
                                                "persona_description"))

        self._label("Greeting Message")
        self._text_area("comm_greeting", height=40,
                        tooltip="First message your agent sends",
                        value=self._get_prefill("communication_preferences",
                                                "greeting_message"))

        if enterprise:
            self._label("Response Formats (check all that apply)")
            self._checkbox_grid(
                "comm_fmt", RESPONSE_FORMATS, cols=3,
                checked_items=self._pf_list("communication_preferences",
                                            "response_format_preferences"))

    def _build_privacy_fields(self, enterprise=False):
        self._label("Data Sensitivity", required=True)
        self._select_field("dp_sensitivity", SENSITIVITY,
                           value=self._get_prefill("data_privacy", "sensitivity"))

        storage_lbl = ("Where Should Data Be Stored?"
                       if self.tier == "private"
                       else "Storage Preference")
        self._label(storage_lbl, required=True)
        self._select_field("dp_storage", STORAGE,
                           value=self._get_prefill("data_privacy",
                                                   "storage_preference"))

        self._label("Data Location Requirement")
        self._check_space(FIELD_H + 4)
        self._hint_line("e.g., EU, US, Any")
        self._text_field("dp_residency",
                         tooltip="e.g., EU, US, Any",
                         value=self._get_prefill("data_privacy",
                                                 "data_residency"))

        if enterprise:
            self._label("Data Retention Period (days)")
            self._check_space(FIELD_H + 4)
            self._hint_line("0\u20133650 days")
            self._text_field("dp_retention_days",
                             tooltip="Data retention in days",
                             value=self._get_prefill("data_privacy",
                                                     "data_retention_days"))

            self._label("PII Handling Policy")
            self._select_field("dp_pii", PII_HANDLING,
                               value=self._get_prefill("data_privacy",
                                                       "pii_handling"))

            self._checkbox_row("dp_encryption", "Encryption Required",
                               checked=self._pf_bool("data_privacy",
                                                     "encryption_required"))

            self._checkbox_row("dp_audit_logging", "Audit Logging Required",
                               checked=self._pf_bool("data_privacy",
                                                     "audit_logging_required"))

    def _build_performance_fields(self, enterprise=False):
        dr_label = ("How Many Requests Per Day?"
                    if self.tier == "private" else "Daily Requests")
        self._label(dr_label, required=True)
        self._text_field("ps_daily_requests",
                         tooltip="Expected interactions per day",
                         value=self._get_prefill("performance_scale",
                                                 "daily_requests"))

        self._label("Peak Simultaneous Users")
        self._text_field("ps_peak_users",
                         tooltip="Max simultaneous users",
                         value=self._get_prefill("performance_scale",
                                                 "peak_concurrent_users"))

        self._label("Response Speed", required=True)
        self._select_field("ps_response_time", RESPONSE_TIME,
                           value=self._get_prefill("performance_scale",
                                                   "response_time_target"))

        self._label("Availability")
        self._select_field("ps_availability", AVAILABILITY,
                           value=self._get_prefill("performance_scale",
                                                   "availability_target"))

        if enterprise:
            self._label("Max Context Length")
            self._select_field("ps_context_length", CONTEXT_LENGTH,
                               tooltip="short=4K, medium=32K, long=128K, maximum=1M+",
                               value=self._get_prefill("performance_scale",
                                                       "max_context_length"))

    def _build_budget_fields(self):
        self._label("Monthly API Budget ($ / month)", required=True)
        self._text_field("bgt_monthly_api",
                         tooltip="Max monthly LLM API spend in USD",
                         value=self._get_prefill("budget", "monthly_api_budget"))

        self._label("Infrastructure Budget ($ / month)")
        self._text_field("bgt_infrastructure",
                         tooltip="Monthly hosting costs in USD",
                         value=self._get_prefill("budget",
                                                 "infrastructure_budget"))

        self._label("One-Time Setup Budget ($)")
        self._text_field("bgt_setup",
                         value=self._get_prefill("budget",
                                                 "one_time_setup_budget"))

        self._label("Fine-Tuning Budget ($)")
        self._text_field("bgt_finetune",
                         value=self._get_prefill("budget",
                                                 "fine_tuning_budget"))

        self._label("Cost Priority")
        self._select_field("bgt_cost_priority", COST_PRIORITY,
                           value=self._get_prefill("budget",
                                                   "cost_optimization_priority"))

    def _build_channel_fields(self):
        self._label("Primary Channel", required=True)
        self._select_field("ch_primary", CHANNELS,
                           value=self._get_prefill("channels",
                                                   "primary_channel"))

        self._label("Secondary Channels (check all that apply)")
        self._checkbox_grid("ch_sec", CHANNELS, cols=3,
                            checked_items=self._pf_list("channels",
                                                        "secondary_channels"))

        self._label("WhatsApp \u2014 Business Account")
        self._checkbox_row("ch_wa_business", "Yes, this is a Business Account",
                           checked=self._pf_bool("channels",
                                                 "channel_specific_config",
                                                 "whatsapp",
                                                 "business_account"))

        self._label("WhatsApp Phone Number")
        self._text_field("ch_wa_phone",
                         value=self._get_prefill("channels",
                                                 "channel_specific_config",
                                                 "whatsapp", "phone_number"))

        self._label("Telegram Bot Name")
        self._text_field("ch_tg_bot_name",
                         value=self._get_prefill("channels",
                                                 "channel_specific_config",
                                                 "telegram", "bot_name"))

        self._checkbox_row("ch_tg_group_mode", "Telegram Group Mode",
                           checked=self._pf_bool("channels",
                                                 "channel_specific_config",
                                                 "telegram", "group_mode"))

        self._label("Discord Server ID")
        self._text_field("ch_discord_server",
                         value=self._get_prefill("channels",
                                                 "channel_specific_config",
                                                 "discord", "server_id"))

        self._label("Slack Workspace Name")
        self._text_field("ch_slack_workspace",
                         value=self._get_prefill("channels",
                                                 "channel_specific_config",
                                                 "slack", "workspace_name"))

    def _build_compliance_fields(self):
        self._label("Applicable Regulations (check all that apply)",
                    required=True)
        self._checkbox_grid("comp_reg", REGULATIONS, cols=4,
                            checked_items=self._pf_list("compliance",
                                                        "regulations"))

        self._checkbox_row(
            "comp_dpa", "Data Processing Agreement Required",
            checked=self._pf_bool("compliance",
                                  "data_processing_agreement_required"))

        self._checkbox_row(
            "comp_right_deletion", "Right to Deletion",
            checked=self._pf_bool("compliance", "right_to_deletion"))

        self._checkbox_row(
            "comp_consent", "Consent Management",
            checked=self._pf_bool("compliance", "consent_management"))

        self._checkbox_row(
            "comp_audit_trail", "Audit Trail Required",
            checked=self._pf_bool("compliance", "audit_trail_required"))

        self._label("Additional Notes")
        self._text_area("comp_notes", height=50,
                        value=self._get_prefill("compliance",
                                                "custom_compliance_notes"))

    # ── Enterprise Part B Field Builders ──────────────────────────────────

    def _build_partb_metadata(self):
        self._label("Assessment Date")
        self._check_space(FIELD_H + 4)
        self._hint_line("Format: YYYY-MM-DD")
        self._text_field("assessment_date", tooltip="YYYY-MM-DD",
                         value=self._get_prefill("assessment_date"))

        self._label("Consultant ID")
        self._text_field("consultant_id",
                         tooltip="Amenthyx consultant ID",
                         value=self._get_prefill("consultant_id"))

    def _build_partb_technical(self):
        self._label("Client Tech Savviness (1\u20135)")
        self._check_space(FIELD_H + 4)
        self._hint_line("1 = non-technical, 5 = developer / sysadmin")
        self._select_field("cp_tech_savvy", ["1", "2", "3", "4", "5"],
                           tooltip="1=non-technical, 5=developer/sysadmin",
                           value=self._get_prefill("client_profile",
                                                   "tech_savvy"))

        self._label("Assessment Version")
        self._check_space(FIELD_H + 4)
        self._hint_line("Hardcoded: 3.0")
        self._text_field("assessment_version", value="3.0")

    def _build_partb_finetuning(self):
        self._checkbox_row("ft_enabled", "Enable Fine-Tuning",
                           checked=self._pf_bool("fine_tuning", "enabled"))

        self._checkbox_row("ft_prebuilt", "Use Pre-Built Adapter",
                           checked=self._pf_bool("fine_tuning",
                                                 "use_pre_built_adapter"))

        self._label("Method")
        self._select_field("ft_method", FT_METHODS,
                           value=self._get_prefill("fine_tuning", "method"))

        self._label("LoRA Rank")
        self._select_field("ft_lora_rank", LORA_RANKS,
                           value=self._get_prefill("fine_tuning", "lora_rank"))

        self._label("Base Model (HuggingFace ID)")
        self._check_space(FIELD_H + 4)
        self._hint_line("e.g., mistralai/Mistral-7B-v0.3")
        self._text_field("ft_base_model",
                         tooltip="e.g., mistralai/Mistral-7B-v0.3",
                         value=self._get_prefill("fine_tuning", "base_model"))

        self._label("Adapter Use Case")
        self._check_space(FIELD_H + 4)
        self._hint_line("e.g., 02-real-estate")
        self._text_field("ft_adapter_use_case",
                         tooltip="e.g., 02-real-estate",
                         value=self._get_prefill("fine_tuning",
                                                 "adapter_use_case"))

        self._label("Training Epochs (1\u201320)")
        self._text_field("ft_epochs",
                         value=self._get_prefill("fine_tuning",
                                                 "training_epochs"))

        self._label("Custom Training Data Path")
        self._text_field("ft_custom_data",
                         value=self._get_prefill("fine_tuning",
                                                 "custom_training_data_path"))

    # ══════════════════════════════════════════════════════════════════════
    #  MAIN BUILD ORCHESTRATORS
    # ══════════════════════════════════════════════════════════════════════

    def _build_private(self):
        """Build the Private tier assessment."""
        self._new_page()
        self._draw_header()

        self._section_header(1, "About You & Your Business")
        self._build_profile_fields(enterprise=False)

        self._section_header(2, "What Will Your AI Agent Do?")
        self._build_use_case_fields()

        self._section_header(3, "Your Agent\u2019s Personality")
        self._build_communication_fields(enterprise=False)

        self._section_header(4, "Data & Privacy")
        self._build_privacy_fields(enterprise=False)

        self._section_header(5, "Expected Usage")
        self._build_performance_fields(enterprise=False)

        self._section_header(6, "Budget")
        self._build_budget_fields()

        self._section_header(7, "Communication Channels")
        self._build_channel_fields()

        self._section_header(8, "Compliance & Regulations")
        self._build_compliance_fields()

    def _build_enterprise(self):
        """Build the Enterprise tier assessment."""
        self._new_page()
        self._draw_header()

        # Part A indicator
        self.c.setFont("Helvetica-Bold", 10)
        self.c.setFillColor(SECTION_BLUE)
        self.c.drawString(MARGIN_L, self.y,
                          "Part A \u2014 Company Defines")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(
            MARGIN_L, self.y,
            "Fill in the following sections with your business requirements.")
        self.c.setFillColor(black)
        self.y -= 12

        self._section_header(1, "Company Profile")
        self._build_profile_fields(enterprise=True)

        self._section_header(2, "Use Cases")
        self._build_use_case_fields()

        self._section_header(3, "Communication Preferences")
        self._build_communication_fields(enterprise=True)

        self._section_header(4, "Data & Privacy")
        self._build_privacy_fields(enterprise=True)

        self._section_header(5, "Performance & Scale")
        self._build_performance_fields(enterprise=True)

        self._section_header(6, "Budget")
        self._build_budget_fields()

        self._section_header(7, "Communication Channels")
        self._build_channel_fields()

        self._section_header(8, "Compliance & Regulations")
        self._build_compliance_fields()

        # ── Part B starts on a fresh page ──
        self._part_divider(
            "Part B \u2014 Amenthyx Defines",
            "The following sections are completed by Amenthyx engineers "
            "after consultation.",
        )

        self._section_header("A", "Assessment Metadata",
                             accent=SECTION_PURPLE)
        self._build_partb_metadata()

        self._section_header("B", "Technical Assessment",
                             accent=SECTION_PURPLE)
        self._build_partb_technical()

        self._section_header("C", "Fine-Tuning Configuration",
                             accent=SECTION_PURPLE)
        self._build_partb_finetuning()

    def build(self):
        if self.tier == "private":
            self._build_private()
        else:
            self._build_enterprise()
        self._draw_footer()
        self.c.save()


# ═════════════════════════════════════════════════════════════════════════════
#  CLI
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Generate fillable PDF assessment forms for "
                    "Claw Agents Provisioner",
    )
    parser.add_argument(
        "--tier", choices=["private", "enterprise"], default="private",
        help="Assessment tier (default: private)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output PDF path (auto-generated if not specified)",
    )
    parser.add_argument(
        "--prefill",
        help="Path to a JSON file to pre-fill the form",
    )
    args = parser.parse_args()

    # Auto-generate output path in the same directory as this script
    if not args.output:
        suffix = "prefilled" if args.prefill else "blank"
        script_dir = Path(__file__).resolve().parent
        args.output = str(
            script_dir / f"claw-assessment-{args.tier}-{suffix}.pdf")

    prefill = {}
    if args.prefill:
        with open(args.prefill, "r", encoding="utf-8") as f:
            prefill = json.load(f)
        print(f"Pre-filling from: {args.prefill}")

    builder = PDFFormBuilder(args.output, tier=args.tier, prefill=prefill)
    builder.build()
    print(f"\nGenerated: {args.output}")
    print(f"  Tier:  {args.tier.title()}")
    print(f"  Pages: {builder.page_num}")


if __name__ == "__main__":
    main()
