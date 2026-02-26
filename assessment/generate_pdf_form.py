#!/usr/bin/env python3
"""
Generate a fillable PDF assessment form for Claw Agents Provisioner.

Creates a professional AcroForm PDF with text fields and checkboxes
matching the assessment JSON schema (v3.0). Clients fill it in any PDF reader
(Acrobat, Foxit, Preview, Chrome, etc.), then run pdf_to_json.py to convert.

Usage:
    python assessment/generate_pdf_form.py                          # default output
    python assessment/generate_pdf_form.py -o my-assessment.pdf     # custom output
    python assessment/generate_pdf_form.py --prefill example.json   # pre-fill from JSON

Requirements:
    pip install reportlab
"""

import argparse
import json
import sys

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
except ImportError:
    print("ERROR: reportlab is required. Install it with: pip install reportlab", file=sys.stderr)
    sys.exit(1)


# ── Constants ────────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4
MARGIN_L = 25 * mm
MARGIN_R = 25 * mm
MARGIN_T = 20 * mm
MARGIN_B = 20 * mm
USABLE_W = PAGE_W - MARGIN_L - MARGIN_R

BRAND_DARK = HexColor("#1a1a2e")
BRAND_ACCENT = HexColor("#0f3460")
FIELD_BG = HexColor("#ffffff")
FIELD_BORDER = HexColor("#cccccc")
LABEL_COLOR = HexColor("#333333")

FIELD_H = 18
CHECKBOX_SIZE = 12
LINE_GAP = 6

# ── Schema enums (for hint text and checkbox grids) ──────────────────────────

INDUSTRIES = [
    "real-estate", "e-commerce", "healthcare", "legal", "finance",
    "technology", "education", "manufacturing", "retail", "hospitality",
    "agriculture", "energy", "telecommunications", "government", "nonprofit",
    "automotive", "insurance", "logistics", "food-service", "entertainment",
    "cybersecurity", "consulting", "media", "fitness", "other"
]

COMPANY_SIZES = ["solo", "2-10", "11-50", "51-200", "201-1000", "1000+"]
DEVICES = ["desktop", "laptop", "mobile", "tablet", "raspberry-pi", "server", "iot-device"]
OS_OPTIONS = ["linux", "macos", "windows", "android", "ios", "embedded", "any"]
SERVICE_PACKAGES = ["private", "enterprise", "managed", "ongoing"]

USE_CASES = [
    "customer-support", "real-estate", "e-commerce", "healthcare", "legal",
    "personal-finance", "code-review", "email-management", "calendar-scheduling",
    "meeting-summarization", "sales-crm", "hr-recruitment", "it-helpdesk",
    "content-writing", "social-media", "translation-multilingual",
    "education-tutoring", "research-summarization", "data-analysis",
    "project-management", "accounting-bookkeeping", "insurance-claims",
    "travel-hospitality", "food-restaurant", "fitness-wellness",
    "automotive-vehicle", "supply-chain-logistics", "manufacturing-qa",
    "agriculture-farming", "energy-utilities", "telecommunications",
    "government-public-services", "nonprofit-fundraising", "event-planning",
    "cybersecurity-threat-intel", "devops-infrastructure",
    "api-integration-webhooks", "database-administration", "iot-smart-home",
    "chatbot-conversational", "document-processing", "knowledge-base-faq",
    "compliance-regulatory", "onboarding-training", "sentiment-analysis",
    "creative-writing", "music-entertainment", "gaming-virtual-worlds",
    "mental-health-counseling", "personal-finance-budgeting"
]

TONES = ["formal", "professional", "casual", "friendly", "technical", "empathetic"]
VERBOSITY = ["concise", "balanced", "detailed", "verbose"]
RESPONSE_FORMATS = ["plain-text", "markdown", "html", "bullet-points", "numbered-lists", "tables"]
SENSITIVITY = ["low", "medium", "high", "critical"]
STORAGE = ["local-only", "private-cloud", "any-cloud"]
PII_HANDLING = ["none", "anonymize", "encrypt", "no-store"]
RESPONSE_TIME = ["instant", "fast", "moderate", "relaxed"]
AVAILABILITY = ["best-effort", "business-hours", "24-7"]
CONTEXT_LENGTH = ["short", "medium", "long", "maximum"]
COST_PRIORITY = ["minimize-cost", "balance", "maximize-quality"]
CHANNELS = ["telegram", "whatsapp", "discord", "slack", "web-chat", "email", "sms", "api-only", "cli"]
REGULATIONS = ["none", "gdpr", "hipaa", "soc2", "pci-dss", "ccpa", "ferpa", "iso27001"]
FT_METHODS = ["lora", "qlora", "prompt-only"]
LORA_RANKS = ["8", "16", "32", "64"]


class PDFFormBuilder:
    """Builds a multi-page fillable PDF assessment form."""

    def __init__(self, output_path: str, prefill: dict = None):
        self.output_path = output_path
        self.prefill = prefill or {}
        self.c = canvas.Canvas(output_path, pagesize=A4)
        self.c.setTitle("Claw Agents Provisioner - Client Assessment Form")
        self.c.setAuthor("Amenthyx AI")
        self.c.setSubject("Client Needs Assessment v3.0")
        self.y = PAGE_H - MARGIN_T
        self.page_num = 0

    def _new_page(self):
        if self.page_num > 0:
            self._draw_footer()
            self.c.showPage()
        self.page_num += 1
        self.y = PAGE_H - MARGIN_T

    def _draw_footer(self):
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(HexColor("#999999"))
        self.c.drawString(MARGIN_L, 15 * mm,
                          f"Claw Agents Provisioner - Client Assessment v3.0 - Page {self.page_num}")
        self.c.drawRightString(PAGE_W - MARGIN_R, 15 * mm, "Amenthyx AI")
        self.c.setFillColor(black)

    def _check_space(self, needed: float):
        if self.y - needed < MARGIN_B + 20:
            self._draw_footer()
            self.c.showPage()
            self.page_num += 1
            self.y = PAGE_H - MARGIN_T

    def _draw_header(self):
        self.c.setFillColor(BRAND_DARK)
        self.c.rect(0, PAGE_H - 55 * mm, PAGE_W, 55 * mm, fill=True, stroke=False)
        self.c.setFillColor(white)
        self.c.setFont("Helvetica-Bold", 22)
        self.c.drawString(MARGIN_L, PAGE_H - 22 * mm, "Claw Agents Provisioner")
        self.c.setFont("Helvetica", 14)
        self.c.drawString(MARGIN_L, PAGE_H - 30 * mm, "Client Needs Assessment Form")
        self.c.setFont("Helvetica", 10)
        self.c.setFillColor(HexColor("#cccccc"))
        self.c.drawString(MARGIN_L, PAGE_H - 38 * mm,
                          "Version 3.0 - Fill all required fields (*), save, and submit.")
        self.c.drawString(MARGIN_L, PAGE_H - 45 * mm,
                          "Convert: python assessment/pdf_to_json.py <this-file>.pdf -o client-assessment.json")
        self.c.setFillColor(black)
        self.y = PAGE_H - 60 * mm

    def _section_header(self, number: int, title: str):
        self._check_space(30)
        self.y -= 8
        self.c.setFillColor(BRAND_ACCENT)
        self.c.roundRect(MARGIN_L, self.y - 20, USABLE_W, 24, 4, fill=True, stroke=False)
        self.c.setFillColor(white)
        self.c.setFont("Helvetica-Bold", 12)
        self.c.drawString(MARGIN_L + 10, self.y - 15, f"Section {number}: {title}")
        self.c.setFillColor(black)
        self.y -= 30

    def _label(self, text: str, required: bool = False):
        self._check_space(20)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.setFillColor(LABEL_COLOR)
        self.c.drawString(MARGIN_L, self.y, f"{text} *" if required else text)
        self.c.setFillColor(black)
        self.y -= 14

    def _hint(self, text: str):
        """Small hint text below label showing valid options."""
        self.c.setFont("Helvetica", 7)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y + 2, text)
        self.c.setFillColor(black)

    def _text_field(self, name: str, width: float = None, height: float = None,
                    tooltip: str = "", value: str = ""):
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

    def _text_area(self, name: str, height: float = 50, tooltip: str = "", value: str = ""):
        self._check_space(height + 4)
        self.c.acroForm.textfield(
            name=name, tooltip=tooltip,
            x=MARGIN_L, y=self.y - height, width=USABLE_W, height=height,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            textColor=black, fontSize=9, fieldFlags="multiline", value=value,
        )
        self.y -= (height + LINE_GAP)

    def _inline_text(self, name: str, x: float, width: float = 120,
                     tooltip: str = "", value: str = ""):
        self.c.acroForm.textfield(
            name=name, tooltip=tooltip,
            x=x, y=self.y - FIELD_H, width=width, height=FIELD_H,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            textColor=black, fontSize=9, value=value,
        )

    def _select_field(self, name: str, options: list, width: float = None,
                      tooltip: str = "", value: str = ""):
        """Text field with hint showing valid options (dropdown replacement)."""
        self._check_space(FIELD_H + 4)
        w = width or USABLE_W
        hint = f"Options: {', '.join(options)}"
        self._hint(hint[:int(w / 3.5)])
        full_tooltip = f"{tooltip}\nValid: {', '.join(options)}" if tooltip else f"Valid: {', '.join(options)}"
        self.c.acroForm.textfield(
            name=name, tooltip=full_tooltip,
            x=MARGIN_L, y=self.y - FIELD_H, width=w, height=FIELD_H,
            borderColor=FIELD_BORDER, fillColor=HexColor("#f8f8ff"),
            textColor=black, fontSize=9, value=value,
        )
        self.y -= (FIELD_H + LINE_GAP)

    def _inline_select(self, name: str, options: list, x: float, width: float = 120,
                       tooltip: str = "", value: str = ""):
        """Inline text field for selection at specific x position."""
        full_tooltip = f"{tooltip}\nValid: {', '.join(options)}" if tooltip else f"Valid: {', '.join(options)}"
        self.c.acroForm.textfield(
            name=name, tooltip=full_tooltip,
            x=x, y=self.y - FIELD_H, width=width, height=FIELD_H,
            borderColor=FIELD_BORDER, fillColor=HexColor("#f8f8ff"),
            textColor=black, fontSize=9, value=value,
        )

    def _checkbox(self, name: str, label: str, x: float, checked: bool = False):
        self.c.acroForm.checkbox(
            name=name, tooltip=label,
            x=x, y=self.y - CHECKBOX_SIZE, size=CHECKBOX_SIZE,
            borderColor=FIELD_BORDER, fillColor=FIELD_BG,
            buttonStyle="check", checked=checked,
        )
        self.c.setFont("Helvetica", 8)
        self.c.drawString(x + CHECKBOX_SIZE + 3, self.y - CHECKBOX_SIZE + 2, label)

    def _checkbox_grid(self, prefix: str, items: list, cols: int = 3,
                       checked_items: list = None):
        checked_items = checked_items or []
        col_w = USABLE_W / cols
        row_items = [items[i:i + cols] for i in range(0, len(items), cols)]
        for row in row_items:
            self._check_space(CHECKBOX_SIZE + 6)
            for j, item in enumerate(row):
                x = MARGIN_L + j * col_w
                field_name = f"{prefix}_{item.replace('-', '_')}"
                self._checkbox(field_name, item, x, checked=item in checked_items)
            self.y -= (CHECKBOX_SIZE + 6)

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

    # ── Page builders ────────────────────────────────────────────────────

    def _build_page1_header_and_profile(self):
        self._new_page()
        self._draw_header()

        # Meta fields
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Assessment Date (YYYY-MM-DD)")
        self.c.drawString(MARGIN_L + 200, self.y, "Consultant ID")
        self.y -= 14
        self._inline_text("assessment_date", MARGIN_L, width=180,
                          tooltip="YYYY-MM-DD",
                          value=self._get_prefill("assessment_date"))
        self._inline_text("consultant_id", MARGIN_L + 200, width=USABLE_W - 200,
                          tooltip="Amenthyx consultant ID",
                          value=self._get_prefill("consultant_id"))
        self.y -= (FIELD_H + LINE_GAP)

        # Section 1
        self._section_header(1, "Client Profile")

        self._label("Company Name", required=True)
        self._text_field("cp_company_name", tooltip="Legal or trading name",
                         value=self._get_prefill("client_profile", "company_name"))

        self._label("Contact Name", required=True)
        self._text_field("cp_contact_name", tooltip="Primary contact person",
                         value=self._get_prefill("client_profile", "contact_name"))

        self._label("Contact Email")
        self._text_field("cp_contact_email", tooltip="Primary contact email",
                         value=self._get_prefill("client_profile", "contact_email"))

        # Industry + Company Size
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Industry *")
        half_w = USABLE_W / 2 - 5
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Company Size *")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, f"({', '.join(INDUSTRIES[:12])}...)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, f"({', '.join(COMPANY_SIZES)})")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("cp_industry", INDUSTRIES, MARGIN_L, width=half_w,
                            tooltip="Primary industry",
                            value=self._get_prefill("client_profile", "industry"))
        self._inline_select("cp_company_size", COMPANY_SIZES, MARGIN_L + half_w + 15,
                            width=half_w, tooltip="Number of employees",
                            value=self._get_prefill("client_profile", "company_size"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Industry (if 'other')")
        self._text_field("cp_industry_other", tooltip="Specify if industry is 'other'",
                         value=self._get_prefill("client_profile", "industry_other"))

        # Tech Savvy + OS
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Tech Savviness (1-5) *")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Operating System")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, "(1=non-technical, 5=developer)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, f"({', '.join(OS_OPTIONS)})")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("cp_tech_savvy", ["1", "2", "3", "4", "5"], MARGIN_L, width=half_w,
                            tooltip="1=non-technical, 5=developer/sysadmin",
                            value=self._get_prefill("client_profile", "tech_savvy"))
        self._inline_select("cp_operating_system", OS_OPTIONS, MARGIN_L + half_w + 15,
                            width=half_w, tooltip="Primary OS",
                            value=self._get_prefill("client_profile", "operating_system"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Service Package")
        self._select_field("cp_service_package", SERVICE_PACKAGES,
                           tooltip="Amenthyx service tier",
                           value=self._get_prefill("client_profile", "service_package"))

        self._label("Primary Devices *  (check all that apply)")
        devices_checked = self._get_prefill("client_profile", "primary_devices", default=[])
        if isinstance(devices_checked, str):
            devices_checked = []
        self._checkbox_grid("cp_device", DEVICES, cols=4, checked_items=devices_checked)

    def _build_page2_use_cases(self):
        self._new_page()
        self._section_header(2, "Use Cases")

        self._label("Primary Use Cases *  (check all that apply)")
        self.c.setFont("Helvetica", 7)
        self.c.setFillColor(HexColor("#666666"))
        self.c.drawString(MARGIN_L, self.y + 2, "Select 1 or more from the 50 supported use cases")
        self.c.setFillColor(black)

        uc_checked = self._get_prefill("use_cases", "primary_use_cases", default=[])
        if isinstance(uc_checked, str):
            uc_checked = []
        self._checkbox_grid("uc", USE_CASES, cols=3, checked_items=uc_checked)

        self._label("Secondary Use Cases (comma-separated, free text)")
        secondary = self._get_prefill("use_cases", "secondary_use_cases", default=[])
        if isinstance(secondary, list):
            secondary = ", ".join(secondary)
        self._text_field("uc_secondary", tooltip="Additional use cases not in list above",
                         value=secondary)

        # Priority + Complexity
        half_w = USABLE_W / 2 - 5
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Use Case Priority")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Complexity Level")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, "(single-focus, multi-task, generalist)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "(simple, moderate, complex, expert)")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("uc_priority", ["single-focus", "multi-task", "generalist"],
                            MARGIN_L, width=half_w,
                            value=self._get_prefill("use_cases", "use_case_priority"))
        self._inline_select("uc_complexity", ["simple", "moderate", "complex", "expert"],
                            MARGIN_L + half_w + 15, width=half_w,
                            value=self._get_prefill("use_cases", "complexity_level"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Domain-Specific Requirements")
        self._text_area("uc_domain_requirements", height=55,
                        tooltip="Industry-specific needs not captured above",
                        value=self._get_prefill("use_cases", "domain_specific_requirements"))

    def _build_page3_communication(self):
        self._section_header(3, "Communication Preferences")
        half_w = USABLE_W / 2 - 5

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Languages * (comma-separated ISO codes)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Primary Language")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, "(e.g., en, it, de, pt-BR)")
        self.c.setFillColor(black)
        self.y -= 6
        langs = self._get_prefill("communication_preferences", "languages", default=[])
        if isinstance(langs, list):
            langs = ", ".join(langs)
        self._inline_text("comm_languages", MARGIN_L, width=half_w,
                          tooltip="ISO 639-1 codes", value=langs)
        self._inline_text("comm_primary_language", MARGIN_L + half_w + 15, width=half_w,
                          tooltip="e.g., en",
                          value=self._get_prefill("communication_preferences", "primary_language"))
        self.y -= (FIELD_H + LINE_GAP)

        # Tone + Verbosity
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Tone *")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Verbosity")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, f"({', '.join(TONES)})")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, f"({', '.join(VERBOSITY)})")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("comm_tone", TONES, MARGIN_L, width=half_w,
                            value=self._get_prefill("communication_preferences", "tone"))
        self._inline_select("comm_verbosity", VERBOSITY, MARGIN_L + half_w + 15, width=half_w,
                            value=self._get_prefill("communication_preferences", "verbosity"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Persona Name")
        self._text_field("comm_persona_name", tooltip="Custom agent name (e.g., Sara, Alex)",
                         value=self._get_prefill("communication_preferences", "persona_name"))

        self._label("Persona Description")
        self._text_area("comm_persona_description", height=45,
                        value=self._get_prefill("communication_preferences", "persona_description"))

        self._label("Greeting Message")
        self._text_area("comm_greeting", height=35,
                        value=self._get_prefill("communication_preferences", "greeting_message"))

        self._label("Response Format Preferences (check all that apply)")
        fmt_checked = self._get_prefill("communication_preferences",
                                        "response_format_preferences", default=[])
        if isinstance(fmt_checked, str):
            fmt_checked = []
        self._checkbox_grid("comm_fmt", RESPONSE_FORMATS, cols=3, checked_items=fmt_checked)

    def _build_page4_privacy_performance(self):
        self._section_header(4, "Data Privacy & Security")
        half_w = USABLE_W / 2 - 5

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Data Sensitivity *")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Storage Preference *")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, f"({', '.join(SENSITIVITY)})")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, f"({', '.join(STORAGE)})")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("dp_sensitivity", SENSITIVITY, MARGIN_L, width=half_w,
                            value=self._get_prefill("data_privacy", "sensitivity"))
        self._inline_select("dp_storage", STORAGE, MARGIN_L + half_w + 15, width=half_w,
                            value=self._get_prefill("data_privacy", "storage_preference"))
        self.y -= (FIELD_H + LINE_GAP)

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Data Retention (days, 0=none)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "PII Handling")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L + half_w + 15, self.y, f"({', '.join(PII_HANDLING)})")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_text("dp_retention_days", MARGIN_L, width=half_w,
                          tooltip="0-3650 days",
                          value=self._get_prefill("data_privacy", "data_retention_days"))
        self._inline_select("dp_pii", PII_HANDLING, MARGIN_L + half_w + 15, width=half_w,
                            value=self._get_prefill("data_privacy", "pii_handling"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Data Residency (e.g., EU, US, any)")
        self._text_field("dp_residency", width=half_w,
                         value=self._get_prefill("data_privacy", "data_residency"))

        self._check_space(CHECKBOX_SIZE + 10)
        enc = self._get_prefill("data_privacy", "encryption_required", default=False)
        audit = self._get_prefill("data_privacy", "audit_logging_required", default=False)
        self._checkbox("dp_encryption", "Encryption Required", MARGIN_L,
                       checked=enc is True or enc == "True")
        self._checkbox("dp_audit_logging", "Audit Logging Required", MARGIN_L + USABLE_W / 2,
                       checked=audit is True or audit == "True")
        self.y -= (CHECKBOX_SIZE + 10)

        # Section 5
        self._section_header(5, "Performance & Scale")

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Daily Requests *")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Peak Concurrent Users")
        self.y -= 14
        self._inline_text("ps_daily_requests", MARGIN_L, width=half_w,
                          tooltip="Expected interactions per day",
                          value=self._get_prefill("performance_scale", "daily_requests"))
        self._inline_text("ps_peak_users", MARGIN_L + half_w + 15, width=half_w,
                          tooltip="Max simultaneous users",
                          value=self._get_prefill("performance_scale", "peak_concurrent_users"))
        self.y -= (FIELD_H + LINE_GAP)

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Response Time Target *")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Availability Target")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, "(instant=<2s, fast=<5s, moderate=<15s, relaxed=<60s)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, f"({', '.join(AVAILABILITY)})")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("ps_response_time", RESPONSE_TIME, MARGIN_L, width=half_w,
                            value=self._get_prefill("performance_scale", "response_time_target"))
        self._inline_select("ps_availability", AVAILABILITY, MARGIN_L + half_w + 15, width=half_w,
                            value=self._get_prefill("performance_scale", "availability_target"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Max Context Length")
        self._select_field("ps_context_length", CONTEXT_LENGTH, width=half_w,
                           tooltip="short=4K, medium=32K, long=128K, maximum=1M+",
                           value=self._get_prefill("performance_scale", "max_context_length"))

    def _build_page5_budget_channels(self):
        self._section_header(6, "Budget")
        half_w = USABLE_W / 2 - 5

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Monthly API Budget (USD) *")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Infrastructure Budget (USD/mo)")
        self.y -= 14
        self._inline_text("bgt_monthly_api", MARGIN_L, width=half_w,
                          tooltip="Max monthly LLM API spend",
                          value=self._get_prefill("budget", "monthly_api_budget"))
        self._inline_text("bgt_infrastructure", MARGIN_L + half_w + 15, width=half_w,
                          tooltip="Monthly hosting costs",
                          value=self._get_prefill("budget", "infrastructure_budget"))
        self.y -= (FIELD_H + LINE_GAP)

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "One-Time Setup Budget (USD)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Fine-Tuning Budget (USD)")
        self.y -= 14
        self._inline_text("bgt_setup", MARGIN_L, width=half_w,
                          value=self._get_prefill("budget", "one_time_setup_budget"))
        self._inline_text("bgt_finetune", MARGIN_L + half_w + 15, width=half_w,
                          value=self._get_prefill("budget", "fine_tuning_budget"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Cost Optimization Priority")
        self._select_field("bgt_cost_priority", COST_PRIORITY, width=half_w,
                           value=self._get_prefill("budget", "cost_optimization_priority"))

        # Section 7
        self._section_header(7, "Communication Channels")

        self._label("Primary Channel *")
        self._select_field("ch_primary", CHANNELS, width=half_w,
                           value=self._get_prefill("channels", "primary_channel"))

        self._label("Secondary Channels (check all that apply)")
        sec_channels = self._get_prefill("channels", "secondary_channels", default=[])
        if isinstance(sec_channels, str):
            sec_channels = []
        self._checkbox_grid("ch_sec", CHANNELS, cols=3, checked_items=sec_channels)

        self._label("Channel Config - WhatsApp")
        self._check_space(CHECKBOX_SIZE + 10)
        wa_biz = self._get_prefill("channels", "channel_specific_config", "whatsapp",
                                   "business_account", default=False)
        self._checkbox("ch_wa_business", "Business Account", MARGIN_L,
                       checked=wa_biz is True or wa_biz == "True")
        self.y -= (CHECKBOX_SIZE + 6)

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "WhatsApp Phone Number")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Telegram Bot Name")
        self.y -= 14
        self._inline_text("ch_wa_phone", MARGIN_L, width=half_w,
                          value=self._get_prefill("channels", "channel_specific_config",
                                                  "whatsapp", "phone_number"))
        self._inline_text("ch_tg_bot_name", MARGIN_L + half_w + 15, width=half_w,
                          value=self._get_prefill("channels", "channel_specific_config",
                                                  "telegram", "bot_name"))
        self.y -= (FIELD_H + LINE_GAP)

        self._check_space(CHECKBOX_SIZE + 10)
        tg_group = self._get_prefill("channels", "channel_specific_config",
                                     "telegram", "group_mode", default=False)
        self._checkbox("ch_tg_group_mode", "Telegram Group Mode", MARGIN_L,
                       checked=tg_group is True or tg_group == "True")
        self.y -= (CHECKBOX_SIZE + 10)

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Discord Server ID")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Slack Workspace Name")
        self.y -= 14
        self._inline_text("ch_discord_server", MARGIN_L, width=half_w,
                          value=self._get_prefill("channels", "channel_specific_config",
                                                  "discord", "server_id"))
        self._inline_text("ch_slack_workspace", MARGIN_L + half_w + 15, width=half_w,
                          value=self._get_prefill("channels", "channel_specific_config",
                                                  "slack", "workspace_name"))
        self.y -= (FIELD_H + LINE_GAP)

    def _build_page6_compliance_finetuning(self):
        self._section_header(8, "Compliance & Regulations")

        self._label("Applicable Regulations * (check all that apply)")
        reg_checked = self._get_prefill("compliance", "regulations", default=[])
        if isinstance(reg_checked, str):
            reg_checked = []
        self._checkbox_grid("comp_reg", REGULATIONS, cols=4, checked_items=reg_checked)

        self._check_space(CHECKBOX_SIZE * 2 + 20)
        dpa = self._get_prefill("compliance", "data_processing_agreement_required", default=False)
        rtd = self._get_prefill("compliance", "right_to_deletion", default=False)
        self._checkbox("comp_dpa", "Data Processing Agreement Required", MARGIN_L,
                       checked=dpa is True or dpa == "True")
        self._checkbox("comp_right_deletion", "Right to Deletion", MARGIN_L + USABLE_W / 2,
                       checked=rtd is True or rtd == "True")
        self.y -= (CHECKBOX_SIZE + 6)

        consent = self._get_prefill("compliance", "consent_management", default=False)
        audit_trail = self._get_prefill("compliance", "audit_trail_required", default=False)
        self._checkbox("comp_consent", "Consent Management", MARGIN_L,
                       checked=consent is True or consent == "True")
        self._checkbox("comp_audit_trail", "Audit Trail Required", MARGIN_L + USABLE_W / 2,
                       checked=audit_trail is True or audit_trail == "True")
        self.y -= (CHECKBOX_SIZE + 10)

        self._label("Custom Compliance Notes")
        self._text_area("comp_notes", height=45,
                        value=self._get_prefill("compliance", "custom_compliance_notes"))

        # Fine-Tuning
        self._section_header(9, "Fine-Tuning (Optional)")
        half_w = USABLE_W / 2 - 5

        self._check_space(CHECKBOX_SIZE + 10)
        ft_enabled = self._get_prefill("fine_tuning", "enabled", default=False)
        ft_prebuilt = self._get_prefill("fine_tuning", "use_pre_built_adapter", default=False)
        self._checkbox("ft_enabled", "Enable Fine-Tuning", MARGIN_L,
                       checked=ft_enabled is True or ft_enabled == "True")
        self._checkbox("ft_prebuilt", "Use Pre-Built Adapter", MARGIN_L + USABLE_W / 2,
                       checked=ft_prebuilt is True or ft_prebuilt == "True")
        self.y -= (CHECKBOX_SIZE + 10)

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Method")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "LoRA Rank")
        self.y -= 10
        self.c.setFont("Helvetica", 6)
        self.c.setFillColor(HexColor("#888888"))
        self.c.drawString(MARGIN_L, self.y, f"({', '.join(FT_METHODS)})")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, f"({', '.join(LORA_RANKS)})")
        self.c.setFillColor(black)
        self.y -= 6
        self._inline_select("ft_method", FT_METHODS, MARGIN_L, width=half_w,
                            value=self._get_prefill("fine_tuning", "method"))
        self._inline_select("ft_lora_rank", LORA_RANKS, MARGIN_L + half_w + 15, width=half_w,
                            value=self._get_prefill("fine_tuning", "lora_rank"))
        self.y -= (FIELD_H + LINE_GAP)

        self._label("Base Model (HuggingFace ID)")
        self._text_field("ft_base_model", tooltip="e.g., mistralai/Mistral-7B-v0.3",
                         value=self._get_prefill("fine_tuning", "base_model"))

        self._label("Adapter Use Case (e.g., 02-real-estate)")
        self._text_field("ft_adapter_use_case",
                         value=self._get_prefill("fine_tuning", "adapter_use_case"))

        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(MARGIN_L, self.y, "Training Epochs (1-20)")
        self.c.drawString(MARGIN_L + half_w + 15, self.y, "Custom Training Data Path")
        self.y -= 14
        self._inline_text("ft_epochs", MARGIN_L, width=half_w,
                          value=self._get_prefill("fine_tuning", "training_epochs"))
        self._inline_text("ft_custom_data", MARGIN_L + half_w + 15, width=half_w,
                          value=self._get_prefill("fine_tuning", "custom_training_data_path"))
        self.y -= (FIELD_H + LINE_GAP)

    def build(self):
        self._build_page1_header_and_profile()
        self._build_page2_use_cases()
        self._build_page3_communication()
        self._build_page4_privacy_performance()
        self._build_page5_budget_channels()
        self._build_page6_compliance_finetuning()
        self._draw_footer()
        self.c.save()


def main():
    parser = argparse.ArgumentParser(
        description="Generate a fillable PDF assessment form for Claw Agents Provisioner"
    )
    parser.add_argument("-o", "--output", default="claw-client-assessment.pdf",
                        help="Output PDF path (default: claw-client-assessment.pdf)")
    parser.add_argument("--prefill",
                        help="Path to a JSON file to pre-fill the form with existing values")
    args = parser.parse_args()

    prefill = {}
    if args.prefill:
        with open(args.prefill, "r", encoding="utf-8") as f:
            prefill = json.load(f)
        print(f"Pre-filling form from: {args.prefill}")

    builder = PDFFormBuilder(args.output, prefill=prefill)
    builder.build()
    print(f"Fillable PDF generated: {args.output}")
    print(f"  Pages: {builder.page_num}")
    print(f"  Open in any PDF reader, fill out, save, then convert:")
    print(f"  python assessment/pdf_to_json.py {args.output} -o client-assessment.json")


if __name__ == "__main__":
    main()
