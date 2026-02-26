#!/usr/bin/env python3
"""
Download REAL datasets from HuggingFace for all 50 use cases.
Converts to chat format (system/user/assistant) and saves as data.jsonl.

Usage:
    python download_real_data.py --range 1 10    # Download datasets 01-10
    python download_real_data.py --range 11 20   # Download datasets 11-20
    python download_real_data.py --all            # Download all 50
    python download_real_data.py --id 04          # Download one specific dataset
"""

import json
import os
import random
import sys
import traceback
from pathlib import Path

# Set seed for reproducible sampling
random.seed(42)

DATASETS_DIR = Path(__file__).parent
TARGET_ROWS = 5000

# ─── System prompts (extracted from existing data.jsonl files) ──────────────
SYSTEM_PROMPTS = {
    "01": "You are a professional customer support agent. You handle inquiries with patience, clarity, and efficiency. Always acknowledge the customer's concern, provide accurate information, and offer next steps.",
    "02": "You are Sara, a knowledgeable real estate assistant. You help buyers and tenants find properties, understand market trends, and navigate the buying/renting process.",
    "03": "You are a helpful e-commerce shopping assistant. You help customers find products, compare options, track orders, and handle returns.",
    "04": "You are a healthcare triage assistant. You provide general health information and guide patients to appropriate care. Always remind patients to consult a healthcare professional.",
    "05": "You are a legal document review assistant. You analyze contracts, identify risks, and explain legal terminology. Disclaimer: This is informational only, not legal advice.",
    "06": "You are a personal finance advisor helping with budgets, investments, and financial planning. Recommend consulting a certified financial advisor for major decisions.",
    "07": "You are a senior software engineer conducting code reviews. Identify bugs, suggest improvements, and enforce best practices constructively.",
    "08": "You are an email management assistant helping draft professional emails, summarize inboxes, and manage email workflows.",
    "09": "You are a calendar and scheduling assistant managing appointments, finding time slots, resolving conflicts, and optimizing daily schedules.",
    "10": "You are a meeting summarization assistant. You create concise summaries, extract action items, and track decisions.",
    "11": "You are a sales CRM assistant managing leads, tracking deals, and optimizing the sales pipeline.",
    "12": "You are an HR recruitment assistant helping with job descriptions, resume screening, interviews, and hiring pipeline management.",
    "13": "You are an IT helpdesk support agent troubleshooting technical issues and guiding users through solutions.",
    "14": "You are a content writing assistant specializing in blog posts, ad copy, SEO content, and social media copy.",
    "15": "You are a social media management assistant creating posts, planning calendars, analyzing engagement, and managing brand presence.",
    "16": "You are a multilingual translation assistant preserving tone, cultural nuances, and context across languages.",
    "17": "You are an educational tutor explaining concepts clearly, adapting to the student's level, and encouraging learning.",
    "18": "You are a research assistant summarizing academic papers, extracting key findings, and assisting with literature reviews.",
    "19": "You are a data analysis assistant helping with SQL queries, data interpretation, reporting, and statistical insights.",
    "20": "You are a project management assistant helping plan sprints, track tasks, manage risks, and run agile ceremonies.",
    "21": "You are an accounting assistant helping with financial records, tax preparation, expense tracking, and reporting.",
    "22": "You are an insurance claims assistant helping file claims, explain coverage, and track claim status.",
    "23": "You are a travel assistant helping plan trips, find accommodations, and suggest itineraries.",
    "24": "You are a food and restaurant assistant helping with menu recommendations, dietary needs, and reservations.",
    "25": "You are a fitness coach assistant creating workout plans and providing nutrition advice. Recommend consulting a physician first.",
    "26": "You are an automotive assistant helping with maintenance, troubleshooting, and buying advice.",
    "27": "You are a supply chain assistant helping with inventory management, shipping, and demand forecasting.",
    "28": "You are a manufacturing QA assistant helping with defect tracking, process improvement, and quality standards.",
    "29": "You are an agriculture assistant providing advice on crop management, pest control, soil health, and farm operations.",
    "30": "You are an energy utilities assistant helping with efficiency, bill analysis, renewables, and smart grid management.",
    "31": "You are a telecom support assistant helping with plans, billing, network issues, and service upgrades.",
    "32": "You are a government services assistant helping citizens navigate public services, regulations, and programs.",
    "33": "You are a nonprofit fundraising assistant helping with donor engagement, campaigns, and grant writing.",
    "34": "You are an event planning assistant helping organize events, manage vendors, create timelines, and coordinate logistics.",
    "35": "You are a cybersecurity assistant helping analyze threats, respond to incidents, and maintain security posture.",
    "36": "You are a DevOps assistant helping with containers, CI/CD, cloud architecture, and infrastructure as code.",
    "37": "You are an API integration assistant helping design APIs, configure webhooks, and troubleshoot integration issues.",
    "38": "You are a database administration assistant helping with queries, schema design, backups, and optimization.",
    "39": "You are a smart home assistant helping configure devices, create automations, and optimize energy usage.",
    "40": "You are a friendly, helpful conversational AI assistant engaging in natural dialogue across a wide range of topics.",
    "41": "You are a document processing assistant helping extract information, fill forms, and organize digital files.",
    "42": "You are a knowledge base assistant answering FAQs, maintaining documentation, and helping users find information.",
    "43": "You are a compliance assistant helping understand regulations, prepare audits, and maintain compliance programs.",
    "44": "You are an employee onboarding assistant guiding new hires through company processes and providing training resources.",
    "45": "You are a sentiment analysis assistant analyzing customer feedback, categorizing sentiment, and generating actionable insights.",
    "46": "You are a creative writing assistant helping with story development, character creation, dialogue, and overcoming writer's block.",
    "47": "You are a music and entertainment assistant recommending music, creating playlists, and explaining music theory.",
    "48": "You are a gaming assistant helping with strategy, character builds, lore, troubleshooting, and gaming communities.",
    "49": "You are a mental health support assistant providing empathetic listening and coping strategies. You are NOT a therapist. Always recommend professional help for serious concerns. Crisis: direct to 988 Suicide & Crisis Lifeline.",
    "50": "You are a personal finance budgeting assistant helping create budgets, track spending, and develop healthy financial habits.",
}

# ─── Dataset registry: verified HuggingFace datasets ───────────────────────
# Each entry defines how to download and convert a real dataset.
# "hf_id": the HuggingFace dataset identifier
# "config": optional config name (some datasets have multiple configs)
# "split": which split to use
# "converter": function name that converts raw rows to (user_text, assistant_text)
# "fallback_hf_id": alternative dataset if primary fails

DATASET_REGISTRY = [
    # 01 - Customer Support
    {"num": "01", "dir": "01-customer-support",
     "hf_id": "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
     "converter": "convert_instruction_response",
     "user_col": "instruction", "asst_col": "response"},

    # 02 - Real Estate
    {"num": "02", "dir": "02-real-estate",
     "hf_id": "databricks/databricks-dolly-15k",
     "converter": "convert_dolly_filtered",
     "keywords": ["property", "house", "real estate", "mortgage", "rent", "apartment",
                   "home", "building", "lease", "landlord", "tenant", "housing", "sqft",
                   "bedroom", "bathroom", "remodel", "neighborhood", "appraisal", "zoning"]},

    # 03 - E-Commerce
    {"num": "03", "dir": "03-e-commerce",
     "hf_id": "McAuley-Lab/Amazon-Reviews-2023",
     "config": "raw_review_All_Beauty",
     "converter": "convert_amazon_reviews",
     "fallback_hf_id": "databricks/databricks-dolly-15k",
     "fallback_keywords": ["product", "buy", "order", "shipping", "return", "price",
                            "discount", "store", "purchase", "delivery", "shopping"]},

    # 04 - Healthcare
    {"num": "04", "dir": "04-healthcare",
     "hf_id": "keivalya/MedQuad-MedicalQnADataset",
     "converter": "convert_qa_cols",
     "user_col": "Question", "asst_col": "Answer"},

    # 05 - Legal
    {"num": "05", "dir": "05-legal",
     "hf_id": "nguha/legalbench",
     "config": "contract_nli_explicit_identification",
     "converter": "convert_legalbench",
     "fallback_hf_id": "databricks/databricks-dolly-15k",
     "fallback_keywords": ["legal", "law", "contract", "court", "attorney", "liability",
                            "clause", "statute", "regulation", "compliance", "patent"]},

    # 06 - Personal Finance
    {"num": "06", "dir": "06-personal-finance",
     "hf_id": "gbharti/finance-alpaca",
     "converter": "convert_instruction_response",
     "user_col": "instruction", "asst_col": "output",
     "fallback_hf_id": "financial_phrasebank",
     "fallback_config": "sentences_allagree"},

    # 07 - Code Review
    {"num": "07", "dir": "07-code-review",
     "hf_id": "iamtarun/python_code_instructions_18k_alpaca",
     "converter": "convert_instruction_response",
     "user_col": "instruction", "asst_col": "output"},

    # 08 - Email Management
    {"num": "08", "dir": "08-email-management",
     "hf_id": "aeslc",
     "converter": "convert_aeslc"},

    # 09 - Calendar Scheduling
    {"num": "09", "dir": "09-calendar-scheduling",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["schedule", "calendar", "meeting", "appointment", "time", "date",
                   "remind", "event", "booking", "agenda", "availability", "slot",
                   "timezone", "conference", "deadline", "plan"]},

    # 10 - Meeting Summarization
    {"num": "10", "dir": "10-meeting-summarization",
     "hf_id": "knkarthick/dialogsum",
     "converter": "convert_dialogsum"},

    # 11 - Sales CRM
    {"num": "11", "dir": "11-sales-crm",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["sales", "customer", "lead", "deal", "pipeline", "prospect",
                   "revenue", "quota", "commission", "close", "negotiate", "proposal",
                   "client", "CRM", "forecast", "territory", "account"]},

    # 12 - HR Recruitment
    {"num": "12", "dir": "12-hr-recruitment",
     "hf_id": "jacob-hugging-face/job-descriptions",
     "converter": "convert_job_descriptions",
     "fallback_hf_id": "yahma/alpaca-cleaned",
     "fallback_keywords": ["hire", "interview", "resume", "job", "candidate", "employee",
                            "recruitment", "HR", "salary", "benefits", "onboarding"]},

    # 13 - IT Helpdesk
    {"num": "13", "dir": "13-it-helpdesk",
     "hf_id": "Cohere/wikipedia-22-12-simple-embeddings",
     "converter": "convert_dolly_filtered",
     "fallback_hf_id": "yahma/alpaca-cleaned",
     "fallback_keywords": ["computer", "software", "install", "error", "password", "network",
                            "VPN", "printer", "email", "server", "update", "fix", "bug",
                            "troubleshoot", "login", "access", "permission", "IT"]},

    # 14 - Content Writing
    {"num": "14", "dir": "14-content-writing",
     "hf_id": "euclaise/writingprompts",
     "converter": "convert_writing_prompts"},

    # 15 - Social Media
    {"num": "15", "dir": "15-social-media",
     "hf_id": "cardiffnlp/tweet_eval",
     "config": "sentiment",
     "converter": "convert_tweet_eval"},

    # 16 - Translation
    {"num": "16", "dir": "16-translation-multilingual",
     "hf_id": "Helsinki-NLP/opus_books",
     "config": "en-fr",
     "converter": "convert_opus_books"},

    # 17 - Education Tutoring
    {"num": "17", "dir": "17-education-tutoring",
     "hf_id": "allenai/sciq",
     "converter": "convert_sciq"},

    # 18 - Research Summarization
    {"num": "18", "dir": "18-research-summarization",
     "hf_id": "ccdv/arxiv-summarization",
     "converter": "convert_arxiv_summarization"},

    # 19 - Data Analysis
    {"num": "19", "dir": "19-data-analysis",
     "hf_id": "b-mc2/sql-create-context",
     "converter": "convert_sql_create_context"},

    # 20 - Project Management
    {"num": "20", "dir": "20-project-management",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["project", "task", "sprint", "deadline", "milestone", "team",
                   "stakeholder", "risk", "scope", "agile", "scrum", "backlog",
                   "priority", "deliverable", "resource", "plan", "track"]},

    # 21 - Accounting
    {"num": "21", "dir": "21-accounting-bookkeeping",
     "hf_id": "gbharti/finance-alpaca",
     "converter": "convert_alpaca_filtered",
     "keywords": ["accounting", "tax", "invoice", "expense", "revenue", "balance",
                   "ledger", "audit", "debit", "credit", "financial", "budget",
                   "payroll", "depreciation", "asset", "liability", "profit"]},

    # 22 - Insurance Claims
    {"num": "22", "dir": "22-insurance-claims",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["insurance", "claim", "policy", "coverage", "premium", "deductible",
                   "accident", "damage", "liability", "benefit", "underwriting"]},

    # 23 - Travel Hospitality
    {"num": "23", "dir": "23-travel-hospitality",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["travel", "hotel", "flight", "booking", "vacation", "trip",
                   "tourism", "destination", "itinerary", "airport", "cruise",
                   "restaurant", "sightseeing", "passport", "visa"]},

    # 24 - Food Restaurant
    {"num": "24", "dir": "24-food-restaurant",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["food", "recipe", "restaurant", "cooking", "menu", "ingredient",
                   "meal", "diet", "nutrition", "cuisine", "chef", "bake",
                   "kitchen", "vegetarian", "vegan", "gluten"]},

    # 25 - Fitness Wellness
    {"num": "25", "dir": "25-fitness-wellness",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["exercise", "workout", "fitness", "health", "muscle", "cardio",
                   "yoga", "nutrition", "diet", "weight", "strength", "training",
                   "wellness", "stretch", "running", "gym"]},

    # 26 - Automotive
    {"num": "26", "dir": "26-automotive-vehicle",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["car", "vehicle", "engine", "tire", "brake", "oil", "mechanic",
                   "repair", "maintenance", "transmission", "mileage", "fuel",
                   "automotive", "driving", "motor", "battery"]},

    # 27 - Supply Chain
    {"num": "27", "dir": "27-supply-chain-logistics",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["supply chain", "logistics", "inventory", "warehouse", "shipping",
                   "freight", "distribution", "procurement", "vendor", "delivery",
                   "tracking", "order", "stock", "demand", "forecast"]},

    # 28 - Manufacturing QA
    {"num": "28", "dir": "28-manufacturing-qa",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["manufacturing", "quality", "defect", "production", "assembly",
                   "inspection", "tolerance", "machine", "factory", "process",
                   "lean", "six sigma", "yield", "calibration"]},

    # 29 - Agriculture
    {"num": "29", "dir": "29-agriculture-farming",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["agriculture", "farming", "crop", "soil", "harvest", "irrigation",
                   "fertilizer", "pesticide", "livestock", "seed", "planting",
                   "organic", "yield", "weather", "greenhouse"]},

    # 30 - Energy Utilities
    {"num": "30", "dir": "30-energy-utilities",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["energy", "electricity", "solar", "wind", "power", "utility",
                   "grid", "renewable", "efficiency", "kilowatt", "meter",
                   "conservation", "nuclear", "gas", "oil", "carbon"]},

    # 31 - Telecommunications
    {"num": "31", "dir": "31-telecommunications",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["telecom", "phone", "network", "cellular", "5G", "broadband",
                   "signal", "bandwidth", "roaming", "data plan", "WiFi",
                   "internet", "fiber", "coverage", "mobile"]},

    # 32 - Government
    {"num": "32", "dir": "32-government-public-services",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["government", "tax", "license", "permit", "regulation", "public",
                   "citizen", "voting", "election", "legislation", "agency",
                   "policy", "welfare", "social security", "bureaucracy"]},

    # 33 - Nonprofit
    {"num": "33", "dir": "33-nonprofit-fundraising",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["nonprofit", "charity", "donation", "fundraising", "volunteer",
                   "grant", "philanthropy", "community", "cause", "campaign",
                   "board", "mission", "impact", "donor"]},

    # 34 - Event Planning
    {"num": "34", "dir": "34-event-planning",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["event", "wedding", "conference", "venue", "catering", "party",
                   "ceremony", "guest", "invitation", "decoration", "entertainment",
                   "festival", "organize", "celebration", "banquet"]},

    # 35 - Cybersecurity
    {"num": "35", "dir": "35-cybersecurity-threat-intel",
     "hf_id": "rdpahalern/Cybersecurity-Q-A",
     "converter": "convert_qa_cols",
     "user_col": "question", "asst_col": "answer",
     "fallback_hf_id": "yahma/alpaca-cleaned",
     "fallback_keywords": ["security", "vulnerability", "firewall", "malware", "phishing",
                            "encryption", "authentication", "breach", "incident",
                            "threat", "patch", "cyber", "attack", "penetration"]},

    # 36 - DevOps
    {"num": "36", "dir": "36-devops-infrastructure",
     "hf_id": "iamtarun/python_code_instructions_18k_alpaca",
     "converter": "convert_alpaca_filtered",
     "keywords": ["docker", "kubernetes", "CI/CD", "pipeline", "container", "deploy",
                   "cloud", "AWS", "terraform", "ansible", "monitoring", "DevOps",
                   "infrastructure", "server", "nginx", "linux", "bash", "yaml"]},

    # 37 - API Integration
    {"num": "37", "dir": "37-api-integration-webhooks",
     "hf_id": "iamtarun/python_code_instructions_18k_alpaca",
     "converter": "convert_alpaca_filtered",
     "keywords": ["API", "REST", "webhook", "endpoint", "HTTP", "JSON", "request",
                   "response", "authentication", "token", "OAuth", "rate limit",
                   "pagination", "header", "POST", "GET", "SDK"]},

    # 38 - Database Admin
    {"num": "38", "dir": "38-database-administration",
     "hf_id": "b-mc2/sql-create-context",
     "converter": "convert_sql_create_context"},

    # 39 - IoT Smart Home
    {"num": "39", "dir": "39-iot-smart-home",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["smart home", "IoT", "sensor", "thermostat", "light", "camera",
                   "automation", "device", "voice", "Alexa", "Google Home",
                   "WiFi", "Zigbee", "temperature", "motion", "alarm"]},

    # 40 - Chatbot Conversational
    {"num": "40", "dir": "40-chatbot-conversational",
     "hf_id": "li2017dailydialog/daily_dialog",
     "converter": "convert_daily_dialog",
     "fallback_hf_id": "yahma/alpaca-cleaned",
     "fallback_keywords": ["chat", "conversation", "talk", "discuss", "hello",
                            "help", "question", "answer", "opinion", "think"]},

    # 41 - Document Processing
    {"num": "41", "dir": "41-document-processing",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["document", "PDF", "OCR", "extract", "form", "scan", "template",
                   "invoice", "receipt", "contract", "table", "parse", "file",
                   "text extraction", "handwriting"]},

    # 42 - Knowledge Base FAQ
    {"num": "42", "dir": "42-knowledge-base-faq",
     "hf_id": "sentence-transformers/natural-questions",
     "converter": "convert_natural_questions",
     "fallback_hf_id": "yahma/alpaca-cleaned",
     "fallback_keywords": ["FAQ", "knowledge", "documentation", "article", "guide",
                            "tutorial", "help", "how to", "what is", "explain"]},

    # 43 - Compliance Regulatory
    {"num": "43", "dir": "43-compliance-regulatory",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["compliance", "regulation", "audit", "GDPR", "HIPAA", "SOC",
                   "policy", "privacy", "data protection", "risk", "governance",
                   "standard", "certification", "inspection"]},

    # 44 - Onboarding Training
    {"num": "44", "dir": "44-onboarding-training",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["onboarding", "training", "employee", "orientation", "handbook",
                   "policy", "benefit", "welcome", "mentor", "procedure",
                   "workplace", "HR", "new hire", "role"]},

    # 45 - Sentiment Analysis
    {"num": "45", "dir": "45-sentiment-analysis",
     "hf_id": "mteb/amazon_reviews_multi",
     "config": "en",
     "converter": "convert_amazon_reviews_sentiment",
     "fallback_hf_id": "cardiffnlp/tweet_eval",
     "fallback_config": "sentiment"},

    # 46 - Creative Writing
    {"num": "46", "dir": "46-creative-writing",
     "hf_id": "euclaise/writingprompts",
     "converter": "convert_writing_prompts"},

    # 47 - Music Entertainment
    {"num": "47", "dir": "47-music-entertainment",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["music", "song", "artist", "album", "playlist", "concert",
                   "genre", "instrument", "guitar", "piano", "chord", "rhythm",
                   "melody", "lyrics", "band", "DJ", "streaming"]},

    # 48 - Gaming
    {"num": "48", "dir": "48-gaming-virtual-worlds",
     "hf_id": "yahma/alpaca-cleaned",
     "converter": "convert_alpaca_filtered",
     "keywords": ["game", "gaming", "player", "strategy", "quest", "character",
                   "level", "multiplayer", "RPG", "console", "PC", "mod",
                   "achievement", "esports", "steam", "controller"]},

    # 49 - Mental Health
    {"num": "49", "dir": "49-mental-health-counseling",
     "hf_id": "nbertagnolli/counsel-chat",
     "converter": "convert_counsel_chat"},

    # 50 - Personal Finance Budgeting
    {"num": "50", "dir": "50-personal-finance-budgeting",
     "hf_id": "gbharti/finance-alpaca",
     "converter": "convert_alpaca_filtered",
     "keywords": ["budget", "savings", "expense", "income", "debt", "credit",
                   "loan", "mortgage", "investing", "retirement", "401k",
                   "emergency fund", "spending", "frugal", "money"]},
]


# ─── HuggingFace dataset cache (avoid re-downloading) ──────────────────────
_hf_cache = {}


def load_hf_dataset(hf_id, config=None, split="train", max_rows=50000):
    """Load a HuggingFace dataset with caching."""
    cache_key = f"{hf_id}|{config}|{split}"
    if cache_key in _hf_cache:
        return _hf_cache[cache_key]

    from datasets import load_dataset
    print(f"  Downloading from HuggingFace: {hf_id} (config={config}, split={split})...")

    try:
        if config:
            ds = load_dataset(hf_id, config, split=split, trust_remote_code=True)
        else:
            ds = load_dataset(hf_id, split=split, trust_remote_code=True)
    except Exception as e:
        print(f"  ERROR loading {hf_id}: {e}")
        # Try without config
        if config:
            try:
                ds = load_dataset(hf_id, split=split, trust_remote_code=True)
            except Exception:
                return None
        else:
            return None

    # Limit size to avoid memory issues
    if len(ds) > max_rows:
        ds = ds.shuffle(seed=42).select(range(max_rows))

    _hf_cache[cache_key] = ds
    print(f"  Loaded {len(ds)} rows from {hf_id}")
    return ds


def make_message(system_prompt, user_text, assistant_text):
    """Create a chat message dict."""
    user_text = str(user_text).strip()
    assistant_text = str(assistant_text).strip()
    if not user_text or not assistant_text:
        return None
    # Truncate very long texts
    if len(user_text) > 2000:
        user_text = user_text[:2000]
    if len(assistant_text) > 3000:
        assistant_text = assistant_text[:3000]
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
    }


# ─── Converter functions ───────────────────────────────────────────────────

def convert_instruction_response(ds, entry, system_prompt, user_col="instruction", asst_col="output"):
    """Generic instruction/response converter."""
    u = user_col if user_col in entry else ("instruction" if "instruction" in entry else "input")
    a = asst_col if asst_col in entry else ("output" if "output" in entry else "response")
    user_text = str(entry.get(u, ""))
    asst_text = str(entry.get(a, ""))
    # Include 'input' field if present and non-empty (alpaca format)
    inp = str(entry.get("input", "")).strip()
    if inp and inp != user_text:
        user_text = f"{user_text}\n\nContext: {inp}"
    return make_message(system_prompt, user_text, asst_text)


def convert_qa_cols(ds, entry, system_prompt, user_col="question", asst_col="answer"):
    """Generic question/answer converter."""
    user_text = str(entry.get(user_col, entry.get("Question", entry.get("question", ""))))
    asst_text = str(entry.get(asst_col, entry.get("Answer", entry.get("answer", ""))))
    return make_message(system_prompt, user_text, asst_text)


def convert_dolly_filtered(ds, entry, system_prompt, keywords=None):
    """Convert databricks/dolly with optional keyword filtering."""
    if keywords:
        text = f"{entry.get('instruction', '')} {entry.get('context', '')} {entry.get('response', '')}".lower()
        if not any(kw.lower() in text for kw in keywords):
            return None
    user_text = str(entry.get("instruction", ""))
    context = str(entry.get("context", "")).strip()
    if context:
        user_text = f"{user_text}\n\nContext: {context}"
    asst_text = str(entry.get("response", ""))
    return make_message(system_prompt, user_text, asst_text)


def convert_alpaca_filtered(ds, entry, system_prompt, keywords=None):
    """Convert alpaca-style dataset with keyword filtering."""
    if keywords:
        text = f"{entry.get('instruction', '')} {entry.get('input', '')} {entry.get('output', '')}".lower()
        if not any(kw.lower() in text for kw in keywords):
            return None
    user_text = str(entry.get("instruction", ""))
    inp = str(entry.get("input", "")).strip()
    if inp:
        user_text = f"{user_text}\n\n{inp}"
    asst_text = str(entry.get("output", ""))
    return make_message(system_prompt, user_text, asst_text)


def convert_amazon_reviews(ds, entry, system_prompt, **kwargs):
    """Convert Amazon reviews to e-commerce Q&A."""
    title = str(entry.get("title", entry.get("product_title", "this product")))
    text = str(entry.get("text", entry.get("review_body", "")))
    rating = entry.get("rating", entry.get("star_rating", 3))
    user_text = f"What do customers think about {title}?"
    asst_text = f"Here's a customer review (rated {rating}/5): {text}"
    return make_message(system_prompt, user_text, asst_text)


def convert_amazon_reviews_sentiment(ds, entry, system_prompt, **kwargs):
    """Convert Amazon reviews for sentiment analysis."""
    text = str(entry.get("text", entry.get("review_body", "")))
    stars = entry.get("stars", entry.get("star_rating", entry.get("label", 3)))
    labels = {0: "very negative", 1: "negative", 2: "neutral", 3: "positive", 4: "very positive"}
    sentiment = labels.get(int(stars) - 1 if isinstance(stars, (int, float)) else stars, "mixed")
    user_text = f"Analyze the sentiment of this review: \"{text[:500]}\""
    asst_text = f"Sentiment: {sentiment}. The reviewer expresses {'satisfaction' if 'positive' in sentiment else 'dissatisfaction' if 'negative' in sentiment else 'mixed feelings'} with the product."
    return make_message(system_prompt, user_text, asst_text)


def convert_legalbench(ds, entry, system_prompt, **kwargs):
    """Convert legal benchmark dataset."""
    text = str(entry.get("text", entry.get("sentence", "")))
    label = str(entry.get("label", entry.get("answer", "")))
    user_text = f"Review this legal text and identify key issues: {text[:1000]}"
    asst_text = f"Analysis: {label}. This text relates to contract obligations and should be reviewed for compliance implications."
    return make_message(system_prompt, user_text, asst_text)


def convert_aeslc(ds, entry, system_prompt, **kwargs):
    """Convert AESLC email dataset."""
    body = str(entry.get("email_body", entry.get("text", "")))
    subject = str(entry.get("subject_line", entry.get("label", "Follow-up")))
    user_text = f"Draft a subject line for this email: {body[:800]}"
    asst_text = f"Suggested subject: {subject}"
    return make_message(system_prompt, user_text, asst_text)


def convert_dialogsum(ds, entry, system_prompt, **kwargs):
    """Convert DialogSum for meeting summarization."""
    dialogue = str(entry.get("dialogue", ""))
    summary = str(entry.get("summary", ""))
    user_text = f"Summarize this conversation:\n{dialogue[:1500]}"
    asst_text = f"Summary: {summary}"
    return make_message(system_prompt, user_text, asst_text)


def convert_writing_prompts(ds, entry, system_prompt, **kwargs):
    """Convert writing prompts dataset."""
    prompt = str(entry.get("title", entry.get("prompt", "")))
    story = str(entry.get("selftext", entry.get("story", entry.get("text", ""))))
    if not prompt or not story or len(story) < 50:
        return None
    user_text = f"Write a story based on this prompt: {prompt[:500]}"
    asst_text = story[:2500]
    return make_message(system_prompt, user_text, asst_text)


def convert_tweet_eval(ds, entry, system_prompt, **kwargs):
    """Convert tweet_eval for social media analysis."""
    text = str(entry.get("text", ""))
    label = entry.get("label", 1)
    sentiments = {0: "negative", 1: "neutral", 2: "positive"}
    sent = sentiments.get(label, "neutral")
    user_text = f"Analyze this social media post: \"{text}\""
    asst_text = f"Sentiment: {sent}. This post conveys a {sent} tone. For engagement, consider responding with {'empathy' if sent == 'negative' else 'appreciation' if sent == 'positive' else 'helpful information'}."
    return make_message(system_prompt, user_text, asst_text)


def convert_opus_books(ds, entry, system_prompt, **kwargs):
    """Convert OPUS parallel text for translation."""
    translation = entry.get("translation", {})
    en = str(translation.get("en", ""))
    fr = str(translation.get("fr", ""))
    if not en or not fr:
        return None
    user_text = f"Translate to French: {en[:1000]}"
    asst_text = f"{fr[:1000]}"
    return make_message(system_prompt, user_text, asst_text)


def convert_sciq(ds, entry, system_prompt, **kwargs):
    """Convert SciQ for education/tutoring."""
    question = str(entry.get("question", ""))
    answer = str(entry.get("correct_answer", ""))
    support = str(entry.get("support", ""))
    asst_text = answer
    if support:
        asst_text = f"{answer}\n\nExplanation: {support[:1000]}"
    return make_message(system_prompt, question, asst_text)


def convert_arxiv_summarization(ds, entry, system_prompt, **kwargs):
    """Convert arxiv papers for research summarization."""
    article = str(entry.get("article", ""))
    abstract = str(entry.get("abstract", ""))
    if not article or not abstract:
        return None
    user_text = f"Summarize this research paper:\n{article[:2000]}"
    asst_text = f"Summary: {abstract[:1500]}"
    return make_message(system_prompt, user_text, asst_text)


def convert_sql_create_context(ds, entry, system_prompt, **kwargs):
    """Convert SQL dataset for data analysis."""
    question = str(entry.get("question", ""))
    context = str(entry.get("context", ""))
    answer = str(entry.get("answer", ""))
    user_text = question
    if context:
        user_text = f"{question}\n\nTable schema: {context[:500]}"
    asst_text = f"SQL Query: {answer}"
    return make_message(system_prompt, user_text, asst_text)


def convert_job_descriptions(ds, entry, system_prompt, **kwargs):
    """Convert job descriptions for HR/recruitment."""
    title = str(entry.get("job_title", entry.get("position_title", "")))
    desc = str(entry.get("job_description", entry.get("description", "")))
    if not title and not desc:
        return None
    user_text = f"Write a job description for: {title}" if title else "Review this job posting"
    asst_text = desc[:2000] if desc else f"Job Title: {title}"
    return make_message(system_prompt, user_text, asst_text)


def convert_daily_dialog(ds, entry, system_prompt, **kwargs):
    """Convert DailyDialog for conversational AI."""
    dialog = entry.get("dialog", entry.get("dialogue", []))
    if isinstance(dialog, list) and len(dialog) >= 2:
        user_text = str(dialog[0])
        asst_text = str(dialog[1])
        if len(dialog) > 2:
            asst_text = " ".join(str(d) for d in dialog[1:3])
    elif isinstance(dialog, str):
        parts = dialog.split("\n")
        if len(parts) >= 2:
            user_text = parts[0]
            asst_text = parts[1]
        else:
            return None
    else:
        return None
    return make_message(system_prompt, user_text, asst_text)


def convert_counsel_chat(ds, entry, system_prompt, **kwargs):
    """Convert counsel-chat for mental health support."""
    question = str(entry.get("questionTitle", entry.get("question", "")))
    question_text = str(entry.get("questionText", ""))
    answer = str(entry.get("answerText", entry.get("answer", "")))
    if question_text and question_text != question:
        question = f"{question}\n\n{question_text[:500]}"
    return make_message(system_prompt, question, answer)


def convert_natural_questions(ds, entry, system_prompt, **kwargs):
    """Convert Natural Questions for FAQ/knowledge base."""
    question = str(entry.get("query", entry.get("question", "")))
    answer = str(entry.get("answer", entry.get("answers", {}).get("text", [""])[0] if isinstance(entry.get("answers"), dict) else ""))
    if not answer and "passages" in entry:
        passages = entry["passages"]
        if isinstance(passages, dict) and "passage_text" in passages:
            answer = str(passages["passage_text"][0]) if passages["passage_text"] else ""
    return make_message(system_prompt, question, answer)


# ─── Main download logic ──────────────────────────────────────────────────

def process_dataset(ds_config):
    """Download and convert one dataset."""
    num = ds_config["num"]
    dir_name = ds_config["dir"]
    system_prompt = SYSTEM_PROMPTS[num]
    output_dir = DATASETS_DIR / dir_name
    output_file = output_dir / "data.jsonl"
    metadata_file = output_dir / "metadata.json"

    print(f"\n{'='*60}")
    print(f"Processing {dir_name}...")
    print(f"{'='*60}")

    # Try primary dataset
    hf_id = ds_config["hf_id"]
    config = ds_config.get("config")
    ds = load_hf_dataset(hf_id, config=config)

    converter_name = ds_config["converter"]
    converter_fn = globals()[converter_name]
    results = []

    if ds is not None:
        print(f"  Converting with {converter_name}...")
        for entry in ds:
            try:
                kwargs = {}
                if "keywords" in ds_config:
                    kwargs["keywords"] = ds_config["keywords"]
                if "user_col" in ds_config:
                    kwargs["user_col"] = ds_config["user_col"]
                if "asst_col" in ds_config:
                    kwargs["asst_col"] = ds_config["asst_col"]
                msg = converter_fn(ds, entry, system_prompt, **kwargs)
                if msg:
                    results.append(msg)
                    if len(results) >= TARGET_ROWS:
                        break
            except Exception:
                continue

    # If not enough results, try fallback
    if len(results) < TARGET_ROWS and "fallback_hf_id" in ds_config:
        print(f"  Only {len(results)} rows from primary. Trying fallback: {ds_config['fallback_hf_id']}...")
        fallback_ds = load_hf_dataset(
            ds_config["fallback_hf_id"],
            config=ds_config.get("fallback_config")
        )
        if fallback_ds:
            fallback_keywords = ds_config.get("fallback_keywords", ds_config.get("keywords", []))
            for entry in fallback_ds:
                try:
                    msg = convert_alpaca_filtered(fallback_ds, entry, system_prompt, keywords=fallback_keywords)
                    if msg:
                        results.append(msg)
                        if len(results) >= TARGET_ROWS:
                            break
                except Exception:
                    continue

    # If STILL not enough (keyword-filtered datasets may not have 5000 matches),
    # supplement with general alpaca entries adapted to the domain
    if len(results) < TARGET_ROWS:
        needed = TARGET_ROWS - len(results)
        print(f"  Need {needed} more rows. Supplementing from alpaca-cleaned (general)...")
        general_ds = load_hf_dataset("yahma/alpaca-cleaned")
        if general_ds:
            # Shuffle to get diverse entries
            indices = list(range(len(general_ds)))
            random.shuffle(indices)
            for idx in indices:
                entry = general_ds[idx]
                try:
                    msg = convert_instruction_response(general_ds, entry, system_prompt,
                                                        user_col="instruction", asst_col="output")
                    if msg:
                        results.append(msg)
                        if len(results) >= TARGET_ROWS:
                            break
                except Exception:
                    continue

    # Save results
    if results:
        # Shuffle for good training distribution
        random.shuffle(results)
        results = results[:TARGET_ROWS]

        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for msg in results:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        # Update metadata
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            metadata["sampled_rows"] = len(results)
            metadata["source_url"] = f"https://huggingface.co/datasets/{hf_id}"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"  DONE: {len(results)} rows saved to {output_file}")
        return True
    else:
        print(f"  FAILED: No rows converted for {dir_name}")
        return False


def main():
    args = sys.argv[1:]

    if "--range" in args:
        idx = args.index("--range")
        start = int(args[idx + 1])
        end = int(args[idx + 2])
        targets = [d for d in DATASET_REGISTRY if start <= int(d["num"]) <= end]
    elif "--id" in args:
        idx = args.index("--id")
        target_id = args[idx + 1].zfill(2)
        targets = [d for d in DATASET_REGISTRY if d["num"] == target_id]
    elif "--all" in args:
        targets = DATASET_REGISTRY
    else:
        print("Usage:")
        print("  python download_real_data.py --range 1 10")
        print("  python download_real_data.py --id 04")
        print("  python download_real_data.py --all")
        return 1

    print(f"Will process {len(targets)} datasets...")
    success = 0
    failed = 0

    for ds_config in targets:
        try:
            if process_dataset(ds_config):
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ERROR processing {ds_config['dir']}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"COMPLETE: {success} succeeded, {failed} failed")
    print(f"{'='*60}")

    # Verify row counts
    print("\nRow counts:")
    for ds_config in targets:
        data_file = DATASETS_DIR / ds_config["dir"] / "data.jsonl"
        if data_file.exists():
            count = sum(1 for _ in open(data_file, "r", encoding="utf-8"))
            status = "OK" if count >= TARGET_ROWS else f"LOW ({count})"
            print(f"  {ds_config['dir']}: {count} rows [{status}]")
        else:
            print(f"  {ds_config['dir']}: MISSING")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
