# Dataset Catalog

> 50 domain-specific datasets for LoRA/QLoRA fine-tuning across all Claw agent use cases.

## Overview

| Metric | Value |
|--------|-------|
| Total datasets | 50 |
| Rows per dataset | 5,000 |
| Total rows | 250,000 |
| Format | JSONL (chat format) |
| All licenses | Free/open (Apache-2.0, MIT, CC-BY, CC0, Public Domain) |

## Data Format

Each `data.jsonl` contains one JSON object per line:

```json
{
  "messages": [
    {"role": "system", "content": "Domain-specific system prompt..."},
    {"role": "user", "content": "User question or request..."},
    {"role": "assistant", "content": "Domain-expert response..."}
  ]
}
```

## Dataset Index

| # | Directory | Domain | Rows | License | Source |
|---|-----------|--------|------|---------|--------|
| 01 | 01-customer-support | Customer Support & Helpdesk | 5,000 | Apache-2.0 | bitext/Bitext-customer-support |
| 02 | 02-real-estate | Real Estate Agent | 5,000 | CC0-1.0 | databricks/dolly-15k + alpaca |
| 03 | 03-e-commerce | E-Commerce Assistant | 5,000 | Apache-2.0 | dolly + alpaca (fallback) |
| 04 | 04-healthcare | Healthcare Triage | 5,000 | CC0-1.0 | keivalya/MedQuad |
| 05 | 05-legal | Legal Document Review | 5,000 | CC-BY-4.0 | dolly + alpaca (fallback) |
| 06 | 06-personal-finance | Personal Finance Advisor | 5,000 | CC-BY-SA-3.0 | gbharti/finance-alpaca |
| 07 | 07-code-review | Code Review & Dev Workflow | 5,000 | Apache-2.0 | iamtarun/python_code_instructions |
| 08 | 08-email-management | Email Management & Drafting | 5,000 | CC0-1.0 | aeslc |
| 09 | 09-calendar-scheduling | Calendar & Scheduling | 5,000 | CC0-1.0 | alpaca-cleaned (filtered) |
| 10 | 10-meeting-summarization | Meeting Summarization | 5,000 | CC-BY-4.0 | knkarthick/dialogsum |
| 11 | 11-sales-crm | Sales & CRM Assistant | 5,000 | CC0-1.0 | alpaca-cleaned (filtered) |
| 12 | 12-hr-recruitment | HR & Recruitment | 5,000 | CC0-1.0 | jacob-hugging-face/job-descriptions |
| 13 | 13-it-helpdesk | IT Helpdesk & Troubleshooting | 5,000 | CC-BY-SA-3.0 | alpaca-cleaned (fallback) |
| 14 | 14-content-writing | Content Writing & Marketing | 5,000 | CC0-1.0 | euclaise/writingprompts |
| 15 | 15-social-media | Social Media Management | 5,000 | Apache-2.0 | cardiffnlp/tweet_eval |
| 16 | 16-translation-multilingual | Translation & Multilingual | 5,000 | CC-BY-4.0 | Helsinki-NLP/opus_books |
| 17 | 17-education-tutoring | Education & Tutoring | 5,000 | CC-BY-4.0 | allenai/sciq |
| 18 | 18-research-summarization | Research & Summarization | 5,000 | CC-BY-4.0 | ccdv/arxiv-summarization |
| 19 | 19-data-analysis | Data Analysis & Reporting | 5,000 | CC-BY-SA-4.0 | b-mc2/sql-create-context |
| 20 | 20-project-management | Project Management | 5,000 | MIT | alpaca-cleaned (filtered) |
| 21 | 21-accounting-bookkeeping | Accounting & Bookkeeping | 5,000 | MIT | gbharti/finance-alpaca |
| 22 | 22-insurance-claims | Insurance Claims Processing | 5,000 | MIT | alpaca-cleaned (filtered) |
| 23 | 23-travel-hospitality | Travel & Hospitality | 5,000 | CC-BY-4.0 | alpaca-cleaned (filtered) |
| 24 | 24-food-restaurant | Food & Restaurant | 5,000 | MIT | alpaca-cleaned (filtered) |
| 25 | 25-fitness-wellness | Fitness & Wellness | 5,000 | MIT | alpaca-cleaned (filtered) |
| 26 | 26-automotive-vehicle | Automotive & Vehicle | 5,000 | MIT | alpaca-cleaned (filtered) |
| 27 | 27-supply-chain-logistics | Supply Chain & Logistics | 5,000 | MIT | alpaca-cleaned (filtered) |
| 28 | 28-manufacturing-qa | Manufacturing & QA | 5,000 | MIT | alpaca-cleaned (filtered) |
| 29 | 29-agriculture-farming | Agriculture & Farming | 5,000 | MIT | alpaca-cleaned (filtered) |
| 30 | 30-energy-utilities | Energy & Utilities | 5,000 | MIT | alpaca-cleaned (filtered) |
| 31 | 31-telecommunications | Telecommunications | 5,000 | MIT | alpaca-cleaned (filtered) |
| 32 | 32-government-public-services | Government & Public Services | 5,000 | MIT | alpaca-cleaned (filtered) |
| 33 | 33-nonprofit-fundraising | Nonprofit & Fundraising | 5,000 | MIT | alpaca-cleaned (filtered) |
| 34 | 34-event-planning | Event Planning & Coordination | 5,000 | MIT | alpaca-cleaned (filtered) |
| 35 | 35-cybersecurity-threat-intel | Cybersecurity & Threat Intel | 5,000 | Public-Domain | alpaca-cleaned (filtered) |
| 36 | 36-devops-infrastructure | DevOps & Infrastructure | 5,000 | CC-BY-SA-4.0 | iamtarun/python_code_instructions |
| 37 | 37-api-integration-webhooks | API Integration & Webhooks | 5,000 | CC0-1.0 | iamtarun/python_code_instructions |
| 38 | 38-database-administration | Database Administration | 5,000 | CC-BY-SA-4.0 | b-mc2/sql-create-context |
| 39 | 39-iot-smart-home | IoT & Smart Home | 5,000 | Apache-2.0 | alpaca-cleaned (filtered) |
| 40 | 40-chatbot-conversational | Chatbot & Conversational AI | 5,000 | CC-BY-4.0 | alpaca-cleaned (fallback) |
| 41 | 41-document-processing | Document Processing & OCR | 5,000 | CC-BY-4.0 | alpaca-cleaned (filtered) |
| 42 | 42-knowledge-base-faq | Knowledge Base & FAQ | 5,000 | CC0-1.0 | sentence-transformers/NQ |
| 43 | 43-compliance-regulatory | Compliance & Regulatory | 5,000 | CC0-1.0 | alpaca-cleaned (filtered) |
| 44 | 44-onboarding-training | Onboarding & Training | 5,000 | CC0-1.0 | alpaca-cleaned (filtered) |
| 45 | 45-sentiment-analysis | Sentiment Analysis & Feedback | 5,000 | Apache-2.0 | mteb/amazon_reviews |
| 46 | 46-creative-writing | Creative Writing & Storytelling | 5,000 | CC-BY-4.0 | alpaca-cleaned (filtered) |
| 47 | 47-music-entertainment | Music & Entertainment | 5,000 | CC0-1.0 | alpaca-cleaned (filtered) |
| 48 | 48-gaming-virtual-worlds | Gaming & Virtual Worlds | 5,000 | CC0-1.0 | alpaca-cleaned (filtered) |
| 49 | 49-mental-health-counseling | Mental Health & Counseling | 5,000 | CC-BY-4.0 | nbertagnolli/counsel-chat |
| 50 | 50-personal-finance-budgeting | Personal Finance & Budgeting | 5,000 | CC0-1.0 | gbharti/finance-alpaca |

## Validation

```bash
# Validate all datasets
python finetune/validate_datasets.py

# Or via claw.sh
./claw.sh datasets --validate
```

## Download Script

The `download_real_data.py` script can re-download and convert all datasets from HuggingFace:

```bash
# Download all
python finetune/datasets/download_real_data.py --all

# Download a specific range
python finetune/datasets/download_real_data.py --range 1 10

# Download a single dataset
python finetune/datasets/download_real_data.py --id 04
```

## Metadata Schema

Each `metadata.json` follows this schema:

```json
{
  "use_case_id": "01-customer-support",
  "use_case_name": "Customer Support & Helpdesk",
  "source_url": "https://huggingface.co/datasets/...",
  "license": "Apache-2.0",
  "original_rows": 26872,
  "sampled_rows": 5000,
  "format": "jsonl",
  "columns": ["messages"],
  "language": "en",
  "domain_tags": ["customer-service", "support", "helpdesk"],
  "recommended_base_model": "mistralai/Mistral-7B-v0.3",
  "recommended_lora_rank": 32
}
```
