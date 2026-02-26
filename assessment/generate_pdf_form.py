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
MARGIN_B = 20 * mm
USABLE_W = PAGE_W - MARGIN_L - MARGIN_R

FIELD_H = 18
CHECKBOX_SIZE = 12
LINE_GAP = 6


# ── Color Palette ────────────────────────────────────────────────────────────

HEADER_DARK   = HexColor("#1B2A4A")
HEADER_LIGHT  = HexColor("#2D4A7A")
SECTION_BLUE  = HexColor("#2D4A7A")
SECTION_PURPLE = HexColor("#7C3AED")
LABEL_COLOR   = HexColor("#374151")
HINT_COLOR    = HexColor("#9CA3AF")
FIELD_BORDER  = HexColor("#D1D5DB")
FIELD_BG      = HexColor("#FFFFFF")
SELECT_BG     = HexColor("#F9FAFB")
CATEGORY_CLR  = HexColor("#6B7280")
MUTED_BLUE    = HexColor("#B0C4DE")


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
        if self.y - needed < MARGIN_B + 15:
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
        self.y = PAGE_H - header_h - 8 * mm

    def _section_header(self, number, title, accent=None):
        self._check_space(40)
        self.y -= 10
        color = accent or SECTION_BLUE
        self.c.setFillColor(color)
        self.c.roundRect(MARGIN_L, self.y - 22, USABLE_W, 26, 5,
                         fill=True, stroke=False)
        self.c.setFillColor(white)
        self.c.setFont("Helvetica-Bold", 12)
        self.c.drawString(MARGIN_L + 12, self.y - 16,
                          f"Section {number}: {title}")
        self.c.setFillColor(black)
        self.y -= 34

    def _part_divider(self, title, subtitle):
        self._check_space(60)
        self.y -= 12
        self.c.setFillColor(SECTION_PURPLE)
        self.c.roundRect(MARGIN_L, self.y - 42, USABLE_W, 46, 6,
                         fill=True, stroke=False)
        self.c.setFillColor(white)
        self.c.setFont("Helvetica-Bold", 15)
        self.c.drawString(MARGIN_L + 14, self.y - 18, title)
        self.c.setFont("Helvetica", 10)
        self.c.drawString(MARGIN_L + 14, self.y - 34, subtitle)
        self.c.setFillColor(black)
        self.y -= 58

    def _category_label(self, text):
        self._check_space(16)
        self.y -= 4
        self.c.setFont("Helvetica-Bold", 8)
        self.c.setFillColor(CATEGORY_CLR)
        self.c.drawString(MARGIN_L + 2, self.y, text)
        self.c.setFillColor(black)
        self.y -= 12

    # ── Field Primitives ──────────────────────────────────────────────────

    def _label(self, text: str, required: bool = False):
        self._check_space(20)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, f"{text} *" if required else text)
        self.c.setFillColor(black)
        self.y -= 14

    def _hint(self, text: str):
        self.c.setFont("Helvetica", 7)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y + 2, text)
        self.c.setFillColor(black)

    def _text_field(self, name, width=None, height=None, tooltip="", value=""):
        self._check_space((height or FIELD_H) + 4)
        w = width or USABLE_W
        h = height or FIELD_H
        self.c.acroForm.textfield(
            name=name, tooltip=tooltip,
            x=MARGIN_L, y=self.y - h, width=w, height=h,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            textColor=black, fontSize=9, fieldFlags="", value=value,
        )
        self.y -= (h + LINE_GAP)

    def _text_area(self, name, height=50, tooltip="", value=""):
        self._check_space(height + 4)
        self.c.acroForm.textfield(
            name=name, tooltip=tooltip,
            x=MARGIN_L, y=self.y - height, width=USABLE_W, height=height,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            textColor=black, fontSize=9, fieldFlags="multiline", value=value,
        )
        self.y -= (height + LINE_GAP)

    def _inline_text(self, name, x, width=120, tooltip="", value=""):
        self.c.acroForm.textfield(
            name=name, tooltip=tooltip,
            x=x, y=self.y - FIELD_H, width=width, height=FIELD_H,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            textColor=black, fontSize=9, value=value,
        )

    def _select_field(self, name, options, width=None, tooltip="", value=""):
        """Text field whose hint shows human-readable option labels."""
        self._check_space(FIELD_H + 4)
        w = width or USABLE_W
        labels = ", ".join(_labels(options))
        max_chars = int(w / 3.5)
        if len(labels) > max_chars:
            labels = labels[:max_chars] + "\u2026"
        self._hint(labels)
        valid = ", ".join(options)
        tip = f"{tooltip}\nType one of: {valid}" if tooltip else f"Type one of: {valid}"
        self.c.acroForm.textfield(
            name=name, tooltip=tip,
            x=MARGIN_L, y=self.y - FIELD_H, width=w, height=FIELD_H,
            borderColor=FIELD_BORDER, fillColor=SELECT_BG,
            textColor=black, fontSize=9, value=value,
        )
        self.y -= (FIELD_H + LINE_GAP)

    def _inline_select(self, name, options, x, width=120, tooltip="", value=""):
        valid = ", ".join(options)
        tip = f"{tooltip}\nType one of: {valid}" if tooltip else f"Type one of: {valid}"
        self.c.acroForm.textfield(
            name=name, tooltip=tip,
            x=x, y=self.y - FIELD_H, width=width, height=FIELD_H,
            borderColor=FIELD_BORDER, fillColor=SELECT_BG,
            textColor=black, fontSize=9, value=value,
        )

    def _checkbox(self, name, label, x, checked=False):
        self.c.acroForm.checkbox(
            name=name, tooltip=label,
            x=x, y=self.y - CHECKBOX_SIZE, size=CHECKBOX_SIZE,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            buttonStyle="check", checked=checked,
        )
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(x + CHECKBOX_SIZE + 3, self.y - CHECKBOX_SIZE + 2, label)
        self.c.setFillColor(black)

    def _checkbox_grid(self, prefix, items, cols=3, checked_items=None):
        checked_items = checked_items or []
        col_w = USABLE_W / cols
        rows = [items[i:i + cols] for i in range(0, len(items), cols)]
        for row in rows:
            self._check_space(CHECKBOX_SIZE + 6)
            for j, item in enumerate(row):
                x = MARGIN_L + j * col_w
                field_name = f"{prefix}_{item.replace('-', '_')}"
                label = LABEL_MAP.get(item, item.replace("-", " ").title())
                self._checkbox(field_name, label, x, checked=item in checked_items)
            self.y -= (CHECKBOX_SIZE + 6)

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
        """Return prefill value as list, or []."""
        v = self._get_prefill(*keys, default=[])
        return v if isinstance(v, list) else []

    def _pf_bool(self, *keys):
        v = self._get_prefill(*keys, default=False)
        return v is True or v == "True"

    # ── Shared Field Builders ─────────────────────────────────────────────

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

        half = USABLE_W / 2 - 5

        # Industry + Company Size
        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Industry *")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Company Size *")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y,
                          ", ".join(_labels(INDUSTRIES[:10])) + "\u2026")
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          ", ".join(_labels(COMPANY_SIZES)))
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("cp_industry", INDUSTRIES, MARGIN_L, width=half,
                            tooltip="Primary industry",
                            value=self._get_prefill("client_profile", "industry"))
        self._inline_select("cp_company_size", COMPANY_SIZES,
                            MARGIN_L + half + 15, width=half,
                            tooltip="Number of employees",
                            value=self._get_prefill("client_profile", "company_size"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Industry (if 'other')")
        self._text_field("cp_industry_other",
                         tooltip="Specify if industry is 'other'",
                         value=self._get_prefill("client_profile", "industry_other"))

        if enterprise:
            # Service Package + Operating System
            self._check_space(FIELD_H + 22)
            self.c.setFont("Helvetica-Bold", 9)
            self.c.setFillColor(LABEL_COLOR)
            self.c.drawString(MARGIN_L, self.y, "Service Package *")
            self.c.drawString(MARGIN_L + half + 15, self.y, "Operating System")
            self.c.setFillColor(black)
            self.y -= 10
            self.c.setFont("Helvetica", 6)
            self.c.setFillColor(HINT_COLOR)
            self.c.drawString(MARGIN_L, self.y,
                              ", ".join(_labels(SERVICE_PACKAGES)))
            self.c.drawString(MARGIN_L + half + 15, self.y,
                              ", ".join(_labels(OS_OPTIONS)))
            self.c.setFillColor(black)
            self.y -= 6
            self._inline_select("cp_service_package", SERVICE_PACKAGES,
                                MARGIN_L, width=half,
                                value=self._get_prefill("client_profile", "service_package"))
            self._inline_select("cp_operating_system", OS_OPTIONS,
                                MARGIN_L + half + 15, width=half,
                                value=self._get_prefill("client_profile", "operating_system"))
            self.y -= (FIELD_H + LINE_GAP)

        self._label("Primary Devices (check all that apply)", required=True)
        self._checkbox_grid("cp_device", DEVICES, cols=4,
                            checked_items=self._pf_list("client_profile", "primary_devices"))

    def _build_use_case_fields(self):
        self._label("Primary Use Cases (check all that apply)", required=True)
        self.c.setFont("Helvetica", 7)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y + 2,
                          "Select one or more from the 50 supported use cases")
        self.c.setFillColor(black)
        self._categorized_use_cases(
            checked_items=self._pf_list("use_cases", "primary_use_cases"))

        self._label("Secondary Use Cases (comma-separated, free text)")
        secondary = self._get_prefill("use_cases", "secondary_use_cases", default=[])
        if isinstance(secondary, list):
            secondary = ", ".join(secondary)
        self._text_field("uc_secondary",
                         tooltip="Additional use cases not in list above",
                         value=secondary)

        half = USABLE_W / 2 - 5
        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Priority")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Complexity")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y,
                          "Single Focus, Multi-Task, Generalist")
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          "Simple, Moderate, Complex, Expert")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("uc_priority",
                            ["single-focus", "multi-task", "generalist"],
                            MARGIN_L, width=half,
                            value=self._get_prefill("use_cases", "use_case_priority"))
        self._inline_select("uc_complexity",
                            ["simple", "moderate", "complex", "expert"],
                            MARGIN_L + half + 15, width=half,
                            value=self._get_prefill("use_cases", "complexity_level"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Specific Requirements")
        self._text_area("uc_domain_requirements", height=55,
                        tooltip="Industry-specific needs",
                        value=self._get_prefill("use_cases",
                                                "domain_specific_requirements"))

    def _build_communication_fields(self, enterprise=False):
        half = USABLE_W / 2 - 5

        # Languages + Primary Language
        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Languages *")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Primary Language")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y, "e.g., English, Italian, German")
        self.c.setFillColor(black)
        self.y -= 6
        langs = self._get_prefill("communication_preferences", "languages",
                                  default=[])
        if isinstance(langs, list):
            langs = ", ".join(langs)
        self._inline_text("comm_languages", MARGIN_L, width=half,
                          tooltip="Languages your agent should speak",
                          value=langs)
        self._inline_text("comm_primary_language", MARGIN_L + half + 15,
                          width=half, tooltip="Main language",
                          value=self._get_prefill("communication_preferences",
                                                  "primary_language"))
        self.y -= (FIELD_H + LINE_GAP)

        # Tone + Verbosity
        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Tone *")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Verbosity")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y, ", ".join(_labels(TONES)))
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          ", ".join(_labels(VERBOSITY)))
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("comm_tone", TONES, MARGIN_L, width=half,
                            value=self._get_prefill("communication_preferences",
                                                    "tone"))
        self._inline_select("comm_verbosity", VERBOSITY,
                            MARGIN_L + half + 15, width=half,
                            value=self._get_prefill("communication_preferences",
                                                    "verbosity"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Agent Name")
        self._text_field("comm_persona_name",
                         tooltip="Give your AI agent a name (e.g., Sara, Alex)",
                         value=self._get_prefill("communication_preferences",
                                                 "persona_name"))

        self._label("Agent Description")
        self._text_area("comm_persona_description", height=45,
                        tooltip="Describe your agent's personality",
                        value=self._get_prefill("communication_preferences",
                                                "persona_description"))

        self._label("Greeting Message")
        self._text_area("comm_greeting", height=35,
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
        half = USABLE_W / 2 - 5

        # Sensitivity + Storage
        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Data Sensitivity *")
        storage_lbl = ("Where Should Data Be Stored? *"
                       if self.tier == "private"
                       else "Storage Preference *")
        self.c.drawString(MARGIN_L + half + 15, self.y, storage_lbl)
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y, ", ".join(_labels(SENSITIVITY)))
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          ", ".join(_labels(STORAGE)))
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("dp_sensitivity", SENSITIVITY, MARGIN_L,
                            width=half,
                            value=self._get_prefill("data_privacy", "sensitivity"))
        self._inline_select("dp_storage", STORAGE, MARGIN_L + half + 15,
                            width=half,
                            value=self._get_prefill("data_privacy",
                                                    "storage_preference"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Data Location Requirement")
        self._text_field("dp_residency", width=half,
                         tooltip="e.g., EU, US, Any",
                         value=self._get_prefill("data_privacy", "data_residency"))

        if enterprise:
            # Retention + PII
            self._check_space(FIELD_H + 22)
            self.c.setFont("Helvetica-Bold", 9)
            self.c.setFillColor(LABEL_COLOR)
            self.c.drawString(MARGIN_L, self.y, "Data Retention Period (days)")
            self.c.drawString(MARGIN_L + half + 15, self.y, "PII Handling Policy")
            self.c.setFillColor(black)
            self.y -= 10
            self.c.setFont("Helvetica", 6)
            self.c.setFillColor(HINT_COLOR)
            self.c.drawString(MARGIN_L, self.y, "0\u20133650 days")
            self.c.drawString(MARGIN_L + half + 15, self.y,
                              ", ".join(_labels(PII_HANDLING)))
            self.c.setFillColor(black)
            self.y -= 6
            self._inline_text("dp_retention_days", MARGIN_L, width=half,
                              tooltip="Data retention in days",
                              value=self._get_prefill("data_privacy",
                                                      "data_retention_days"))
            self._inline_select("dp_pii", PII_HANDLING,
                                MARGIN_L + half + 15, width=half,
                                value=self._get_prefill("data_privacy",
                                                        "pii_handling"))
            self.y -= (FIELD_H + LINE_GAP)

            # Encryption + Audit checkboxes
            self._check_space(CHECKBOX_SIZE + 10)
            self._checkbox("dp_encryption", "Encryption Required", MARGIN_L,
                           checked=self._pf_bool("data_privacy",
                                                 "encryption_required"))
            self._checkbox("dp_audit_logging", "Audit Logging Required",
                           MARGIN_L + USABLE_W / 2,
                           checked=self._pf_bool("data_privacy",
                                                 "audit_logging_required"))
            self.y -= (CHECKBOX_SIZE + 10)

    def _build_performance_fields(self, enterprise=False):
        half = USABLE_W / 2 - 5

        # Daily Requests + Peak Users
        self._check_space(FIELD_H + 16)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        dr_label = ("How Many Requests Per Day? *"
                    if self.tier == "private" else "Daily Requests *")
        self.c.drawString(MARGIN_L, self.y, dr_label)
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          "Peak Simultaneous Users")
        self.c.setFillColor(black)
        self.y -= 14
        self._inline_text("ps_daily_requests", MARGIN_L, width=half,
                          tooltip="Expected interactions per day",
                          value=self._get_prefill("performance_scale",
                                                  "daily_requests"))
        self._inline_text("ps_peak_users", MARGIN_L + half + 15, width=half,
                          tooltip="Max simultaneous users",
                          value=self._get_prefill("performance_scale",
                                                  "peak_concurrent_users"))
        self.y -= (FIELD_H + LINE_GAP)

        # Response Time + Availability
        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Response Speed *")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Availability")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y, ", ".join(_labels(RESPONSE_TIME)))
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          ", ".join(_labels(AVAILABILITY)))
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("ps_response_time", RESPONSE_TIME, MARGIN_L,
                            width=half,
                            value=self._get_prefill("performance_scale",
                                                    "response_time_target"))
        self._inline_select("ps_availability", AVAILABILITY,
                            MARGIN_L + half + 15, width=half,
                            value=self._get_prefill("performance_scale",
                                                    "availability_target"))
        self.y -= (FIELD_H + LINE_GAP)

        if enterprise:
            self._label("Max Context Length")
            self._select_field("ps_context_length", CONTEXT_LENGTH, width=half,
                               tooltip="short=4K, medium=32K, long=128K, maximum=1M+",
                               value=self._get_prefill("performance_scale",
                                                       "max_context_length"))

    def _build_budget_fields(self):
        half = USABLE_W / 2 - 5

        self._check_space(FIELD_H + 16)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y,
                          "Monthly API Budget ($ / month) *")
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          "Infrastructure Budget ($ / month)")
        self.c.setFillColor(black)
        self.y -= 14
        self._inline_text("bgt_monthly_api", MARGIN_L, width=half,
                          tooltip="Max monthly LLM API spend in USD",
                          value=self._get_prefill("budget", "monthly_api_budget"))
        self._inline_text("bgt_infrastructure", MARGIN_L + half + 15,
                          width=half, tooltip="Monthly hosting costs in USD",
                          value=self._get_prefill("budget",
                                                  "infrastructure_budget"))
        self.y -= (FIELD_H + LINE_GAP)

        self._check_space(FIELD_H + 16)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "One-Time Setup Budget ($)")
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          "Fine-Tuning Budget ($)")
        self.c.setFillColor(black)
        self.y -= 14
        self._inline_text("bgt_setup", MARGIN_L, width=half,
                          value=self._get_prefill("budget",
                                                  "one_time_setup_budget"))
        self._inline_text("bgt_finetune", MARGIN_L + half + 15, width=half,
                          value=self._get_prefill("budget",
                                                  "fine_tuning_budget"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Cost Priority")
        self._select_field("bgt_cost_priority", COST_PRIORITY, width=half,
                           value=self._get_prefill("budget",
                                                   "cost_optimization_priority"))

    def _build_channel_fields(self):
        half = USABLE_W / 2 - 5

        self._label("Primary Channel", required=True)
        self._select_field("ch_primary", CHANNELS, width=half,
                           value=self._get_prefill("channels", "primary_channel"))

        self._label("Secondary Channels (check all that apply)")
        self._checkbox_grid("ch_sec", CHANNELS, cols=3,
                            checked_items=self._pf_list("channels",
                                                        "secondary_channels"))

        # WhatsApp config
        self._label("WhatsApp Configuration")
        self._check_space(CHECKBOX_SIZE + 10)
        self._checkbox("ch_wa_business", "Business Account", MARGIN_L,
                       checked=self._pf_bool("channels",
                                             "channel_specific_config",
                                             "whatsapp", "business_account"))
        self.y -= (CHECKBOX_SIZE + 6)

        self._check_space(FIELD_H + 16)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "WhatsApp Phone Number")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Telegram Bot Name")
        self.c.setFillColor(black)
        self.y -= 14
        self._inline_text("ch_wa_phone", MARGIN_L, width=half,
                          value=self._get_prefill("channels",
                                                  "channel_specific_config",
                                                  "whatsapp", "phone_number"))
        self._inline_text("ch_tg_bot_name", MARGIN_L + half + 15, width=half,
                          value=self._get_prefill("channels",
                                                  "channel_specific_config",
                                                  "telegram", "bot_name"))
        self.y -= (FIELD_H + LINE_GAP)

        self._check_space(CHECKBOX_SIZE + 10)
        self._checkbox("ch_tg_group_mode", "Telegram Group Mode", MARGIN_L,
                       checked=self._pf_bool("channels",
                                             "channel_specific_config",
                                             "telegram", "group_mode"))
        self.y -= (CHECKBOX_SIZE + 10)

        self._check_space(FIELD_H + 16)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Discord Server ID")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Slack Workspace Name")
        self.c.setFillColor(black)
        self.y -= 14
        self._inline_text("ch_discord_server", MARGIN_L, width=half,
                          value=self._get_prefill("channels",
                                                  "channel_specific_config",
                                                  "discord", "server_id"))
        self._inline_text("ch_slack_workspace", MARGIN_L + half + 15,
                          width=half,
                          value=self._get_prefill("channels",
                                                  "channel_specific_config",
                                                  "slack", "workspace_name"))
        self.y -= (FIELD_H + LINE_GAP)

    def _build_compliance_fields(self):
        self._label("Applicable Regulations (check all that apply)",
                    required=True)
        self._checkbox_grid("comp_reg", REGULATIONS, cols=4,
                            checked_items=self._pf_list("compliance",
                                                        "regulations"))

        self._check_space(CHECKBOX_SIZE * 2 + 20)
        self._checkbox("comp_dpa",
                       "Data Processing Agreement Required", MARGIN_L,
                       checked=self._pf_bool("compliance",
                                             "data_processing_agreement_required"))
        self._checkbox("comp_right_deletion", "Right to Deletion",
                       MARGIN_L + USABLE_W / 2,
                       checked=self._pf_bool("compliance",
                                             "right_to_deletion"))
        self.y -= (CHECKBOX_SIZE + 6)

        self._checkbox("comp_consent", "Consent Management", MARGIN_L,
                       checked=self._pf_bool("compliance",
                                             "consent_management"))
        self._checkbox("comp_audit_trail", "Audit Trail Required",
                       MARGIN_L + USABLE_W / 2,
                       checked=self._pf_bool("compliance",
                                             "audit_trail_required"))
        self.y -= (CHECKBOX_SIZE + 10)

        self._label("Additional Notes")
        self._text_area("comp_notes", height=45,
                        value=self._get_prefill("compliance",
                                                "custom_compliance_notes"))

    # ── Enterprise Part B Field Builders ──────────────────────────────────

    def _build_partb_metadata(self):
        half = USABLE_W / 2 - 5
        self._check_space(FIELD_H + 16)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Assessment Date (YYYY-MM-DD)")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Consultant ID")
        self.c.setFillColor(black)
        self.y -= 14
        self._inline_text("assessment_date", MARGIN_L, width=half,
                          tooltip="YYYY-MM-DD",
                          value=self._get_prefill("assessment_date"))
        self._inline_text("consultant_id", MARGIN_L + half + 15, width=half,
                          tooltip="Amenthyx consultant ID",
                          value=self._get_prefill("consultant_id"))
        self.y -= (FIELD_H + LINE_GAP)

    def _build_partb_technical(self):
        half = USABLE_W / 2 - 5

        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Client Tech Savviness (1\u20135)")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Assessment Version")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y,
                          "1 = non-technical, 5 = developer/sysadmin")
        self.c.drawString(MARGIN_L + half + 15, self.y, "Hardcoded: 3.0")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("cp_tech_savvy", ["1", "2", "3", "4", "5"],
                            MARGIN_L, width=half,
                            tooltip="1=non-technical, 5=developer/sysadmin",
                            value=self._get_prefill("client_profile",
                                                    "tech_savvy"))
        self._inline_text("assessment_version", MARGIN_L + half + 15,
                          width=half, value="3.0")
        self.y -= (FIELD_H + LINE_GAP)

    def _build_partb_finetuning(self):
        half = USABLE_W / 2 - 5

        self._check_space(CHECKBOX_SIZE + 10)
        self._checkbox("ft_enabled", "Enable Fine-Tuning", MARGIN_L,
                       checked=self._pf_bool("fine_tuning", "enabled"))
        self._checkbox("ft_prebuilt", "Use Pre-Built Adapter",
                       MARGIN_L + USABLE_W / 2,
                       checked=self._pf_bool("fine_tuning",
                                             "use_pre_built_adapter"))
        self.y -= (CHECKBOX_SIZE + 10)

        # Method + LoRA Rank
        self._check_space(FIELD_H + 22)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Method")
        self.c.drawString(MARGIN_L + half + 15, self.y, "LoRA Rank")
        self.c.setFillColor(black)
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y, ", ".join(_labels(FT_METHODS)))
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          ", ".join(LORA_RANKS))
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("ft_method", FT_METHODS, MARGIN_L, width=half,
                            value=self._get_prefill("fine_tuning", "method"))
        self._inline_select("ft_lora_rank", LORA_RANKS,
                            MARGIN_L + half + 15, width=half,
                            value=self._get_prefill("fine_tuning", "lora_rank"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Base Model (HuggingFace ID)")
        self._text_field("ft_base_model",
                         tooltip="e.g., mistralai/Mistral-7B-v0.3",
                         value=self._get_prefill("fine_tuning", "base_model"))

        self._label("Adapter Use Case")
        self._text_field("ft_adapter_use_case",
                         tooltip="e.g., 02-real-estate",
                         value=self._get_prefill("fine_tuning",
                                                 "adapter_use_case"))

        # Epochs + Custom Data
        self._check_space(FIELD_H + 16)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, "Training Epochs (1\u201320)")
        self.c.drawString(MARGIN_L + half + 15, self.y,
                          "Custom Training Data Path")
        self.c.setFillColor(black)
        self.y -= 14
        self._inline_text("ft_epochs", MARGIN_L, width=half,
                          value=self._get_prefill("fine_tuning",
                                                  "training_epochs"))
        self._inline_text("ft_custom_data", MARGIN_L + half + 15, width=half,
                          value=self._get_prefill("fine_tuning",
                                                  "custom_training_data_path"))
        self.y -= (FIELD_H + LINE_GAP)

    # ── Main Build Orchestrators ──────────────────────────────────────────

    def _build_private(self):
        """Build the Private tier assessment (~3-4 pages)."""
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
        """Build the Enterprise tier assessment (~5-7 pages)."""
        self._new_page()
        self._draw_header()

        # Part A indicator
        self.c.setFont("Helvetica-Bold", 10)
        self.c.setFillColor(SECTION_BLUE)
        self.c.drawString(MARGIN_L, self.y, "Part A \u2014 Company Defines")
        self.c.setFillColor(black)
        self.y -= 8
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(HINT_COLOR)
        self.c.drawString(MARGIN_L, self.y,
                          "Fill in the following sections with your business requirements.")
        self.c.setFillColor(black)
        self.y -= 14

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

        # ── Part B ──
        self._part_divider(
            "Part B \u2014 Amenthyx Defines",
            "The following sections are completed by Amenthyx after consultation.",
        )

        self._section_header("A", "Assessment Metadata", accent=SECTION_PURPLE)
        self._build_partb_metadata()

        self._section_header("B", "Technical Assessment", accent=SECTION_PURPLE)
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
        description="Generate fillable PDF assessment forms for Claw Agents Provisioner",
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
        args.output = str(script_dir / f"claw-assessment-{args.tier}-{suffix}.pdf")

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
