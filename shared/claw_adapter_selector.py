#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER -- Adapter Auto-Selection Engine
=============================================================================
Automatically selects the best LoRA adapter from the 50 available adapters
based on assessment use case, industry, and keyword matching.

Scans finetune/adapters/ and finetune/datasets/ for adapter configs and
metadata, scores each adapter by domain tag overlap with the requested
use case, and returns the top match with its full config bundle path.

Scoring algorithm:
  1. Exact use-case-to-adapter mapping           (+100 points)
  2. Domain tag overlap with query keywords       (+20 per tag match)
  3. Industry alias expansion                     (+15 per alias hit)
  4. Fuzzy substring matching on adapter name     (+10 per hit)
  5. Dataset size bonus (larger = more trained)   (+1-5 points)

Usage:
  python3 shared/claw_adapter_selector.py --use-case customer_support
  python3 shared/claw_adapter_selector.py --use-case legal --industry healthcare
  python3 shared/claw_adapter_selector.py --list
  python3 shared/claw_adapter_selector.py --info 01-customer-support
  python3 shared/claw_adapter_selector.py --match "code review security"

Output: Adapter ID, config path, system prompt path, and match score.

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi -- linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ADAPTERS_DIR = PROJECT_ROOT / "finetune" / "adapters"
DATASETS_DIR = PROJECT_ROOT / "finetune" / "datasets"

# -------------------------------------------------------------------------
# Colors (for terminal output)
# -------------------------------------------------------------------------
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[adapter]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[adapter]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[adapter]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[adapter]{NC} {msg}")


# -------------------------------------------------------------------------
# Use-case to adapter mapping (canonical keywords -> adapter directory)
# -------------------------------------------------------------------------
USE_CASE_MAP: Dict[str, str] = {
    # 01 - Customer Support
    "customer_support": "01-customer-support",
    "helpdesk": "01-customer-support",
    "customer_service": "01-customer-support",
    "support_ticket": "01-customer-support",
    # 02 - Real Estate
    "real_estate": "02-real-estate",
    "property": "02-real-estate",
    "housing": "02-real-estate",
    "real_estate_agent": "02-real-estate",
    # 03 - E-Commerce
    "e_commerce": "03-e-commerce",
    "ecommerce": "03-e-commerce",
    "retail": "03-e-commerce",
    "shopping": "03-e-commerce",
    "product_search": "03-e-commerce",
    # 04 - Healthcare
    "healthcare": "04-healthcare",
    "patient_triage": "04-healthcare",
    "medical": "04-healthcare",
    "symptom_check": "04-healthcare",
    "health": "04-healthcare",
    # 05 - Legal
    "legal": "05-legal",
    "legal_analysis": "05-legal",
    "contract_analysis": "05-legal",
    "contracts": "05-legal",
    "compliance_legal": "05-legal",
    # 06 - Personal Finance
    "personal_finance": "06-personal-finance",
    "financial_advisory": "06-personal-finance",
    "finance": "06-personal-finance",
    "investing": "06-personal-finance",
    "budgeting": "06-personal-finance",
    # 07 - Code Review
    "code_review": "07-code-review",
    "code_assistant": "07-code-review",
    "dev_workflow": "07-code-review",
    "git": "07-code-review",
    # 08 - Email Management
    "email": "08-email-management",
    "email_management": "08-email-management",
    "email_drafting": "08-email-management",
    # 09 - Calendar Scheduling
    "calendar": "09-calendar-scheduling",
    "scheduling": "09-calendar-scheduling",
    "time_management": "09-calendar-scheduling",
    # 10 - Meeting Summarization
    "meeting_summarization": "10-meeting-summarization",
    "meetings": "10-meeting-summarization",
    "action_items": "10-meeting-summarization",
    # 11 - Sales CRM
    "sales": "11-sales-crm",
    "sales_crm": "11-sales-crm",
    "crm": "11-sales-crm",
    "lead_qualification": "11-sales-crm",
    # 12 - HR Recruitment
    "hr": "12-hr-recruitment",
    "hr_recruitment": "12-hr-recruitment",
    "recruitment": "12-hr-recruitment",
    "job_matching": "12-hr-recruitment",
    # 13 - IT Helpdesk
    "it_helpdesk": "13-it-helpdesk",
    "it_support": "13-it-helpdesk",
    "troubleshooting": "13-it-helpdesk",
    "sysadmin": "13-it-helpdesk",
    # 14 - Content Writing
    "content_creation": "14-content-writing",
    "content_writing": "14-content-writing",
    "copywriting": "14-content-writing",
    "seo": "14-content-writing",
    # 15 - Social Media
    "social_media": "15-social-media",
    "social_media_management": "15-social-media",
    "engagement": "15-social-media",
    # 16 - Translation
    "translation": "16-translation-multilingual",
    "translation_localization": "16-translation-multilingual",
    "multilingual": "16-translation-multilingual",
    "localization": "16-translation-multilingual",
    # 17 - Education
    "education": "17-education-tutoring",
    "education_tutoring": "17-education-tutoring",
    "tutoring": "17-education-tutoring",
    # 18 - Research Summarization
    "research": "18-research-summarization",
    "research_summarization": "18-research-summarization",
    "academic": "18-research-summarization",
    "paper_summarization": "18-research-summarization",
    # 19 - Data Analysis
    "data_analysis": "19-data-analysis",
    "sql": "19-data-analysis",
    "reporting": "19-data-analysis",
    # 20 - Project Management
    "project_management": "20-project-management",
    "agile": "20-project-management",
    "task_tracking": "20-project-management",
    # 21 - Accounting
    "accounting": "21-accounting-bookkeeping",
    "accounting_bookkeeping": "21-accounting-bookkeeping",
    "bookkeeping": "21-accounting-bookkeeping",
    "tax": "21-accounting-bookkeeping",
    # 22 - Insurance
    "insurance": "22-insurance-claims",
    "insurance_claims": "22-insurance-claims",
    "claims": "22-insurance-claims",
    "risk_assessment": "22-insurance-claims",
    # 23 - Travel
    "travel": "23-travel-hospitality",
    "travel_booking": "23-travel-hospitality",
    "hospitality": "23-travel-hospitality",
    "booking": "23-travel-hospitality",
    # 24 - Food & Restaurant
    "restaurant": "24-food-restaurant",
    "food_ordering": "24-food-restaurant",
    "food": "24-food-restaurant",
    "menu": "24-food-restaurant",
    # 25 - Fitness
    "fitness": "25-fitness-wellness",
    "wellness": "25-fitness-wellness",
    "nutrition": "25-fitness-wellness",
    # 26 - Automotive
    "automotive": "26-automotive-vehicle",
    "automotive_diagnostics": "26-automotive-vehicle",
    "vehicle": "26-automotive-vehicle",
    "car_maintenance": "26-automotive-vehicle",
    # 27 - Supply Chain
    "supply_chain": "27-supply-chain-logistics",
    "logistics": "27-supply-chain-logistics",
    "inventory": "27-supply-chain-logistics",
    "fleet": "27-supply-chain-logistics",
    # 28 - Manufacturing
    "manufacturing": "28-manufacturing-qa",
    "manufacturing_process": "28-manufacturing-qa",
    "quality_control": "28-manufacturing-qa",
    "quality_assurance": "28-manufacturing-qa",
    # 29 - Agriculture
    "agriculture": "29-agriculture-farming",
    "agriculture_precision": "29-agriculture-farming",
    "farming": "29-agriculture-farming",
    "crop_management": "29-agriculture-farming",
    # 30 - Energy
    "energy": "30-energy-utilities",
    "energy_grid": "30-energy-utilities",
    "utilities": "30-energy-utilities",
    "sustainability": "30-energy-utilities",
    # 31 - Telecommunications
    "telecom": "31-telecommunications",
    "telecom_network": "31-telecommunications",
    "telecommunications": "31-telecommunications",
    "network_billing": "31-telecommunications",
    # 32 - Government
    "government": "32-government-public-services",
    "public_services": "32-government-public-services",
    "civic": "32-government-public-services",
    # 33 - Nonprofit
    "nonprofit": "33-nonprofit-fundraising",
    "fundraising": "33-nonprofit-fundraising",
    "donor_relations": "33-nonprofit-fundraising",
    # 34 - Event Planning
    "event_planning": "34-event-planning",
    "events": "34-event-planning",
    "coordination": "34-event-planning",
    # 35 - Cybersecurity
    "cybersecurity": "35-cybersecurity-threat-intel",
    "cybersecurity_soc": "35-cybersecurity-threat-intel",
    "threat_intelligence": "35-cybersecurity-threat-intel",
    "vulnerability": "35-cybersecurity-threat-intel",
    # 36 - DevOps
    "devops": "36-devops-infrastructure",
    "devops_incident_response": "36-devops-infrastructure",
    "incident_response": "36-devops-infrastructure",
    "kubernetes": "36-devops-infrastructure",
    "infrastructure": "36-devops-infrastructure",
    # 37 - API Integration
    "api_integration": "37-api-integration-webhooks",
    "webhooks": "37-api-integration-webhooks",
    "rest_api": "37-api-integration-webhooks",
    # 38 - Database Administration
    "database": "38-database-administration",
    "database_admin": "38-database-administration",
    "dba": "38-database-administration",
    "query_optimization": "38-database-administration",
    # 39 - IoT / Smart Home
    "iot": "39-iot-smart-home",
    "iot_device_management": "39-iot-smart-home",
    "smart_home": "39-iot-smart-home",
    "home_automation": "39-iot-smart-home",
    # 40 - Chatbot
    "chatbot": "40-chatbot-conversational",
    "conversational_ai": "40-chatbot-conversational",
    "dialogue": "40-chatbot-conversational",
    # 41 - Document Processing
    "document_processing": "41-document-processing",
    "ocr": "41-document-processing",
    "data_extraction": "41-document-processing",
    "invoice": "41-document-processing",
    # 42 - Knowledge Base
    "knowledge_base": "42-knowledge-base-faq",
    "faq": "42-knowledge-base-faq",
    "self_service": "42-knowledge-base-faq",
    "documentation": "42-knowledge-base-faq",
    # 43 - Compliance
    "compliance": "43-compliance-regulatory",
    "regulatory": "43-compliance-regulatory",
    "gdpr": "43-compliance-regulatory",
    "hipaa": "43-compliance-regulatory",
    "audit": "43-compliance-regulatory",
    # 44 - Onboarding
    "onboarding": "44-onboarding-training",
    "onboarding_training": "44-onboarding-training",
    "employee_training": "44-onboarding-training",
    # 45 - Sentiment Analysis
    "sentiment_analysis": "45-sentiment-analysis",
    "feedback": "45-sentiment-analysis",
    "reviews": "45-sentiment-analysis",
    "opinion_mining": "45-sentiment-analysis",
    # 46 - Creative Writing
    "creative_writing": "46-creative-writing",
    "storytelling": "46-creative-writing",
    "fiction": "46-creative-writing",
    "narrative": "46-creative-writing",
    # 47 - Music & Entertainment
    "music": "47-music-entertainment",
    "entertainment": "47-music-entertainment",
    "playlists": "47-music-entertainment",
    "music_theory": "47-music-entertainment",
    # 48 - Gaming
    "gaming": "48-gaming-virtual-worlds",
    "gaming_npc": "48-gaming-virtual-worlds",
    "virtual_worlds": "48-gaming-virtual-worlds",
    "npc_dialogue": "48-gaming-virtual-worlds",
    "game_mechanics": "48-gaming-virtual-worlds",
    # 49 - Mental Health
    "mental_health": "49-mental-health-counseling",
    "mental_health_support": "49-mental-health-counseling",
    "counseling": "49-mental-health-counseling",
    "therapy": "49-mental-health-counseling",
    # 50 - Personal Finance Budgeting
    "personal_finance_budgeting": "50-personal-finance-budgeting",
    "savings": "50-personal-finance-budgeting",
    "financial_literacy": "50-personal-finance-budgeting",
}

# Industry aliases — expand a broad industry term into specific keywords
# for better cross-matching against domain tags.
INDUSTRY_ALIASES: Dict[str, List[str]] = {
    "healthcare": ["healthcare", "medical", "health", "patient", "triage", "symptom"],
    "finance": ["finance", "banking", "investing", "budgeting", "accounting", "tax", "insurance"],
    "technology": ["code", "devops", "api", "database", "iot", "cybersecurity", "infrastructure"],
    "retail": ["e-commerce", "shopping", "product", "retail", "supply-chain", "inventory"],
    "education": ["education", "tutoring", "training", "onboarding", "learning"],
    "legal": ["legal", "compliance", "regulatory", "contracts", "audit", "GDPR", "HIPAA"],
    "hospitality": ["travel", "hospitality", "booking", "restaurant", "food", "events"],
    "manufacturing": ["manufacturing", "quality-control", "process", "supply-chain", "logistics"],
    "energy": ["energy", "utilities", "sustainability", "grid"],
    "agriculture": ["agriculture", "farming", "crop-management"],
    "government": ["government", "public-service", "civic", "regulatory"],
    "media": ["content-creation", "social-media", "creative-writing", "music", "entertainment"],
    "automotive": ["automotive", "vehicle", "maintenance", "diagnostics"],
    "telecom": ["telecom", "network", "billing", "telecommunications"],
    "hr": ["HR", "recruitment", "onboarding", "employee-experience", "job-matching"],
}


# -------------------------------------------------------------------------
# AdapterSelector -- main class
# -------------------------------------------------------------------------
class AdapterSelector:
    """Scans adapter directories, scores by domain overlap, returns best match."""

    def __init__(self, adapters_dir: Optional[Path] = None,
                 datasets_dir: Optional[Path] = None):
        self.adapters_dir = adapters_dir or ADAPTERS_DIR
        self.datasets_dir = datasets_dir or DATASETS_DIR
        self._adapters: List[Dict[str, Any]] = []
        self._loaded = False

    # -----------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------
    def load_adapters(self) -> List[Dict[str, Any]]:
        """Scan finetune/adapters/ and finetune/datasets/ for metadata.

        Returns a list of adapter info dicts, each containing:
          adapter_id, use_case_name, domain_tags, adapter_config,
          adapter_dir, dataset_dir, sampled_rows.
        """
        if self._loaded:
            return self._adapters

        self._adapters = []

        if not self.adapters_dir.is_dir():
            warn(f"Adapters directory not found: {self.adapters_dir}")
            return self._adapters

        for entry in sorted(self.adapters_dir.iterdir()):
            if not entry.is_dir():
                continue

            adapter_id = entry.name
            adapter_config_path = entry / "adapter_config.json"
            system_prompt_path = entry / "system_prompt.txt"
            training_config_path = entry / "training_config.json"
            dataset_dir = self.datasets_dir / adapter_id
            metadata_path = dataset_dir / "metadata.json"

            # Must have at least adapter_config.json
            if not adapter_config_path.is_file():
                continue

            # Load adapter config
            adapter_config = self._load_json(adapter_config_path)
            if adapter_config is None:
                continue

            # Load dataset metadata (optional but provides domain_tags)
            metadata = self._load_json(metadata_path) if metadata_path.is_file() else {}

            record = {
                "adapter_id": adapter_id,
                "use_case_name": metadata.get("use_case_name",
                                               adapter_config.get("use_case_name",
                                                                   adapter_id)),
                "domain_tags": [t.lower() for t in metadata.get("domain_tags", [])],
                "sampled_rows": metadata.get("sampled_rows", 0),
                "original_rows": metadata.get("original_rows", 0),
                "language": metadata.get("language", "en"),
                "license": metadata.get("license", "unknown"),
                "base_model": adapter_config.get("base_model_name_or_path", "unknown"),
                "lora_rank": adapter_config.get("r", 0),
                "adapter_dir": str(entry),
                "adapter_config_path": str(adapter_config_path),
                "system_prompt_path": str(system_prompt_path) if system_prompt_path.is_file() else None,
                "training_config_path": str(training_config_path) if training_config_path.is_file() else None,
                "dataset_dir": str(dataset_dir) if dataset_dir.is_dir() else None,
            }
            self._adapters.append(record)

        self._loaded = True
        log(f"Loaded {len(self._adapters)} adapter(s) from {self.adapters_dir}")
        return self._adapters

    # -----------------------------------------------------------------
    # Matching / Scoring
    # -----------------------------------------------------------------
    def match(self, use_case: str, industry: Optional[str] = None,
              keywords: Optional[List[str]] = None) -> List[Tuple[float, Dict[str, Any]]]:
        """Score and rank adapters for a given use case, industry, and keywords.

        Returns a list of (score, adapter_info) tuples sorted by score descending.
        """
        self.load_adapters()

        if not self._adapters:
            err("No adapters loaded. Check that finetune/adapters/ exists.")
            return []

        # Normalize the use_case query
        use_case_normalized = use_case.strip().lower().replace("-", "_").replace(" ", "_")

        # Build query tokens from all inputs
        query_tokens: List[str] = []
        query_tokens.extend(use_case_normalized.split("_"))
        if industry:
            industry_norm = industry.strip().lower().replace("-", "_").replace(" ", "_")
            query_tokens.extend(industry_norm.split("_"))
            # Expand industry aliases
            for alias_key, alias_terms in INDUSTRY_ALIASES.items():
                if alias_key in industry_norm or industry_norm in alias_key:
                    query_tokens.extend([t.lower() for t in alias_terms])
        if keywords:
            for kw in keywords:
                query_tokens.extend(kw.strip().lower().replace("-", "_").replace(" ", "_").split("_"))

        # Deduplicate while preserving order
        seen = set()
        unique_tokens: List[str] = []
        for t in query_tokens:
            if t and t not in seen:
                seen.add(t)
                unique_tokens.append(t)

        scored: List[Tuple[float, Dict[str, Any]]] = []

        for adapter in self._adapters:
            score = self._score_adapter(adapter, use_case_normalized, unique_tokens)
            scored.append((score, adapter))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _score_adapter(self, adapter: Dict[str, Any], use_case_key: str,
                       query_tokens: List[str]) -> float:
        """Compute a match score for a single adapter against the query."""
        score = 0.0
        adapter_id = adapter["adapter_id"]
        domain_tags = adapter["domain_tags"]
        adapter_name_tokens = set(adapter_id.lower().replace("-", " ").split())

        # 1. Exact use-case map match (+100)
        mapped_id = USE_CASE_MAP.get(use_case_key)
        if mapped_id and mapped_id == adapter_id:
            score += 100.0

        # 2. Domain tag overlap with query tokens (+20 per match)
        for token in query_tokens:
            for tag in domain_tags:
                tag_lower = tag.lower()
                if token == tag_lower or token in tag_lower or tag_lower in token:
                    score += 20.0
                    break  # One match per token, avoid double-counting

        # 3. Industry alias expansion hits against domain tags (+15)
        for token in query_tokens:
            for alias_key, alias_terms in INDUSTRY_ALIASES.items():
                lower_terms = [t.lower() for t in alias_terms]
                if token in lower_terms:
                    for tag in domain_tags:
                        if tag.lower() in lower_terms:
                            score += 15.0
                            break
                    break

        # 4. Fuzzy substring match on adapter directory name (+10)
        for token in query_tokens:
            if len(token) >= 3 and token in adapter_id.lower():
                score += 10.0
            elif len(token) >= 3:
                for name_tok in adapter_name_tokens:
                    if token in name_tok or name_tok in token:
                        score += 5.0
                        break

        # 5. Dataset size bonus (larger dataset = better trained)
        sampled = adapter.get("sampled_rows", 0)
        if sampled >= 10000:
            score += 5.0
        elif sampled >= 5000:
            score += 3.0
        elif sampled >= 1000:
            score += 1.0

        return round(score, 2)

    def select_best(self, use_case: str, industry: Optional[str] = None,
                    keywords: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Return the single best adapter match, or None if no adapters loaded.

        The returned dict includes the adapter info plus a 'match_score' field.
        """
        results = self.match(use_case, industry=industry, keywords=keywords)
        if not results:
            return None

        best_score, best_adapter = results[0]
        result = dict(best_adapter)
        result["match_score"] = best_score
        return result

    # -----------------------------------------------------------------
    # Info / Listing
    # -----------------------------------------------------------------
    def get_adapter_info(self, adapter_id: str) -> Optional[Dict[str, Any]]:
        """Return full adapter info for a given adapter_id (e.g. '01-customer-support')."""
        self.load_adapters()

        # Allow partial matching (e.g. '01' or 'customer-support')
        adapter_id_lower = adapter_id.strip().lower()
        for adapter in self._adapters:
            if adapter["adapter_id"].lower() == adapter_id_lower:
                return adapter
            if adapter["adapter_id"].lower().startswith(adapter_id_lower):
                return adapter
            if adapter_id_lower in adapter["adapter_id"].lower():
                return adapter

        return None

    def list_adapters(self) -> List[Dict[str, Any]]:
        """Return all 50 adapters with brief info."""
        self.load_adapters()
        return self._adapters

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    @staticmethod
    def _load_json(path: Path) -> Optional[Dict]:
        """Load a JSON file, returning None on error."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError) as exc:
            warn(f"Failed to load {path}: {exc}")
            return None


# -------------------------------------------------------------------------
# CLI Output Formatting
# -------------------------------------------------------------------------
def print_adapter_list(adapters: List[Dict[str, Any]]) -> None:
    """Print a formatted table of all adapters."""
    print(f"\n{BOLD}{CYAN}=== Adapter Auto-Selection Engine -- Adapter Catalog ==={NC}\n")
    print(f"  {BOLD}{'ID':<35} {'Name':<35} {'Tags':<40}{NC}")
    print(f"  {'_' * 35} {'_' * 35} {'_' * 40}")

    for adapter in adapters:
        aid = adapter["adapter_id"]
        name = adapter["use_case_name"][:33]
        tags = ", ".join(adapter["domain_tags"][:4])
        if len(adapter["domain_tags"]) > 4:
            tags += " ..."
        print(f"  {aid:<35} {name:<35} {DIM}{tags}{NC}")

    print(f"\n{BOLD}Total: {len(adapters)} adapter(s){NC}\n")


def print_adapter_info(adapter: Dict[str, Any]) -> None:
    """Print detailed info for a single adapter."""
    print(f"\n{BOLD}{CYAN}=== Adapter Info: {adapter['adapter_id']} ==={NC}\n")
    print(f"  {BOLD}Name:{NC}            {adapter['use_case_name']}")
    print(f"  {BOLD}Adapter ID:{NC}      {adapter['adapter_id']}")
    print(f"  {BOLD}Base Model:{NC}      {adapter.get('base_model', 'unknown')}")
    print(f"  {BOLD}LoRA Rank:{NC}       {adapter.get('lora_rank', 'N/A')}")
    print(f"  {BOLD}Language:{NC}        {adapter.get('language', 'en')}")
    print(f"  {BOLD}License:{NC}         {adapter.get('license', 'unknown')}")
    print(f"  {BOLD}Domain Tags:{NC}     {', '.join(adapter['domain_tags'])}")
    print(f"  {BOLD}Training Rows:{NC}   {adapter.get('sampled_rows', 0):,} sampled / {adapter.get('original_rows', 0):,} original")
    print()
    print(f"  {BOLD}Paths:{NC}")
    print(f"    Adapter dir:      {adapter.get('adapter_dir', 'N/A')}")
    print(f"    Adapter config:   {adapter.get('adapter_config_path', 'N/A')}")
    print(f"    System prompt:    {adapter.get('system_prompt_path', 'N/A')}")
    print(f"    Training config:  {adapter.get('training_config_path', 'N/A')}")
    print(f"    Dataset dir:      {adapter.get('dataset_dir', 'N/A')}")
    print()


def print_match_results(results: List[Tuple[float, Dict[str, Any]]],
                        query: str, top_n: int = 5) -> None:
    """Print ranked match results."""
    print(f"\n{BOLD}{CYAN}=== Adapter Match Results ==={NC}")
    print(f"  Query: {BOLD}{query}{NC}\n")

    if not results:
        print(f"  {DIM}No adapters found.{NC}\n")
        return

    shown = results[:top_n]
    print(f"  {BOLD}{'Rank':<6} {'Score':<10} {'Adapter ID':<35} {'Name':<35}{NC}")
    print(f"  {'_' * 6} {'_' * 10} {'_' * 35} {'_' * 35}")

    for i, (score, adapter) in enumerate(shown, 1):
        score_color = GREEN if score >= 100 else YELLOW if score >= 40 else DIM
        rank_marker = f"  #{i}"
        print(f"  {rank_marker:<6} {score_color}{score:>7.1f}{NC}   {adapter['adapter_id']:<35} {adapter['use_case_name']:<35}")

    if len(results) > top_n:
        remaining = len(results) - top_n
        print(f"\n  {DIM}... and {remaining} more adapter(s) with lower scores{NC}")

    # Highlight the best match
    best_score, best = results[0]
    if best_score > 0:
        print(f"\n  {GREEN}{BOLD}Best match:{NC} {best['adapter_id']} "
              f"({best['use_case_name']}) -- score {best_score:.1f}")
        print(f"  {BOLD}Config:{NC}     {best.get('adapter_config_path', 'N/A')}")
        if best.get("system_prompt_path"):
            print(f"  {BOLD}Prompt:{NC}     {best['system_prompt_path']}")
    else:
        print(f"\n  {RED}No strong match found. Consider refining your query.{NC}")

    print()


# -------------------------------------------------------------------------
# Main CLI
# -------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python3 shared/claw_adapter_selector.py [OPTIONS]")
        print()
        print("Commands:")
        print("  --use-case <name>               Select adapter by use case keyword")
        print("  --use-case <name> --industry <i> Narrow selection by industry")
        print("  --match <query>                  Free-text keyword match")
        print("  --list                           List all 50 adapters")
        print("  --info <adapter-id>              Show detailed adapter info")
        print()
        print("Examples:")
        print("  python3 shared/claw_adapter_selector.py --use-case customer_support")
        print("  python3 shared/claw_adapter_selector.py --use-case legal --industry healthcare")
        print("  python3 shared/claw_adapter_selector.py --match \"code review security\"")
        print("  python3 shared/claw_adapter_selector.py --list")
        print("  python3 shared/claw_adapter_selector.py --info 01-customer-support")
        sys.exit(1)

    selector = AdapterSelector()

    # Parse arguments manually (stdlib only, no argparse to keep it simple)
    args = sys.argv[1:]

    if args[0] == "--list":
        adapters = selector.list_adapters()
        print_adapter_list(adapters)

    elif args[0] == "--info":
        if len(args) < 2:
            err("--info requires an adapter ID. Example: --info 01-customer-support")
            sys.exit(1)
        adapter_id = args[1]
        adapter = selector.get_adapter_info(adapter_id)
        if adapter:
            print_adapter_info(adapter)
        else:
            err(f"Adapter not found: {adapter_id}")
            sys.exit(1)

    elif args[0] == "--use-case":
        if len(args) < 2:
            err("--use-case requires a use case name. Example: --use-case customer_support")
            sys.exit(1)
        use_case = args[1]
        industry = None
        keywords = None

        # Check for --industry flag
        if "--industry" in args:
            idx = args.index("--industry")
            if idx + 1 < len(args):
                industry = args[idx + 1]

        # Check for --keywords flag
        if "--keywords" in args:
            idx = args.index("--keywords")
            if idx + 1 < len(args):
                keywords = args[idx + 1].split(",")

        results = selector.match(use_case, industry=industry, keywords=keywords)
        query_desc = use_case
        if industry:
            query_desc += f" + industry:{industry}"
        print_match_results(results, query_desc)

    elif args[0] == "--match":
        if len(args) < 2:
            err("--match requires a search query. Example: --match \"code review security\"")
            sys.exit(1)
        query = " ".join(args[1:])
        tokens = query.lower().replace("-", " ").replace("_", " ").split()
        # Use the first token as use_case, rest as keywords
        use_case = tokens[0] if tokens else ""
        keywords = tokens[1:] if len(tokens) > 1 else None
        results = selector.match(use_case, keywords=keywords)
        print_match_results(results, query)

    else:
        err(f"Unknown option: {args[0]}")
        print("Run without arguments to see usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
