# Adapter Catalog

> 50 pre-built LoRA/QLoRA adapter configurations for domain-specific fine-tuning.

## Overview

Each adapter directory contains three files:

| File | Purpose |
|------|---------|
| `adapter_config.json` | LoRA rank, target modules, base model, dataset path |
| `system_prompt.txt` | Enriched system prompt for API-only models (Claude, GPT, DeepSeek) |
| `training_config.json` | Epochs, learning rate, batch size, VRAM estimate |

## Usage

### Train an adapter

```bash
# Using claw.sh
./claw.sh finetune --adapter customer-support

# Using training scripts directly
python finetune/train_lora.py --adapter 01-customer-support
python finetune/train_qlora.py --adapter 01-customer-support

# Dry run (validate config without training)
./claw.sh finetune --adapter customer-support --dry-run
```

### Use system prompt (API-only models)

For models that don't support LoRA adapters (Claude, GPT, DeepSeek), use the enriched system prompt:

```bash
cat finetune/adapters/01-customer-support/system_prompt.txt
```

## Adapter Index

| # | Adapter | LoRA Rank | VRAM (GB) |
|---|---------|-----------|-----------|
| 01 | 01-customer-support | 32 | 10 |
| 02 | 02-real-estate | 32 | 10 |
| 03 | 03-e-commerce | 32 | 10 |
| 04 | 04-healthcare | 64 | 12 |
| 05 | 05-legal | 64 | 12 |
| 06 | 06-personal-finance | 32 | 10 |
| 07 | 07-code-review | 32 | 10 |
| 08 | 08-email-management | 32 | 10 |
| 09 | 09-calendar-scheduling | 16 | 8 |
| 10 | 10-meeting-summarization | 32 | 10 |
| 11 | 11-sales-crm | 32 | 10 |
| 12 | 12-hr-recruitment | 32 | 10 |
| 13 | 13-it-helpdesk | 32 | 10 |
| 14 | 14-content-writing | 32 | 10 |
| 15 | 15-social-media | 32 | 10 |
| 16 | 16-translation-multilingual | 32 | 10 |
| 17 | 17-education-tutoring | 32 | 10 |
| 18 | 18-research-summarization | 32 | 10 |
| 19 | 19-data-analysis | 64 | 12 |
| 20 | 20-project-management | 32 | 10 |
| 21 | 21-accounting-bookkeeping | 32 | 10 |
| 22 | 22-insurance-claims | 64 | 12 |
| 23 | 23-travel-hospitality | 32 | 10 |
| 24 | 24-food-restaurant | 16 | 8 |
| 25 | 25-fitness-wellness | 16 | 8 |
| 26 | 26-automotive-vehicle | 32 | 10 |
| 27 | 27-supply-chain-logistics | 32 | 10 |
| 28 | 28-manufacturing-qa | 64 | 12 |
| 29 | 29-agriculture-farming | 32 | 10 |
| 30 | 30-energy-utilities | 32 | 10 |
| 31 | 31-telecommunications | 32 | 10 |
| 32 | 32-government-public-services | 32 | 10 |
| 33 | 33-nonprofit-fundraising | 32 | 10 |
| 34 | 34-event-planning | 16 | 8 |
| 35 | 35-cybersecurity-threat-intel | 64 | 12 |
| 36 | 36-devops-infrastructure | 64 | 12 |
| 37 | 37-api-integration-webhooks | 32 | 10 |
| 38 | 38-database-administration | 64 | 12 |
| 39 | 39-iot-smart-home | 32 | 10 |
| 40 | 40-chatbot-conversational | 16 | 8 |
| 41 | 41-document-processing | 32 | 10 |
| 42 | 42-knowledge-base-faq | 16 | 8 |
| 43 | 43-compliance-regulatory | 64 | 12 |
| 44 | 44-onboarding-training | 32 | 10 |
| 45 | 45-sentiment-analysis | 32 | 10 |
| 46 | 46-creative-writing | 32 | 10 |
| 47 | 47-music-entertainment | 16 | 8 |
| 48 | 48-gaming-virtual-worlds | 32 | 10 |
| 49 | 49-mental-health-counseling | 64 | 12 |
| 50 | 50-personal-finance-budgeting | 32 | 10 |

## LoRA Rank Guide

| Rank | Use Case | VRAM | Quality |
|------|----------|------|---------|
| 16 | Simple tasks, lightweight adapters | ~8 GB | Good |
| 32 | General-purpose (default) | ~10 GB | Better |
| 64 | Complex domains (legal, medical, security) | ~12 GB | Best |

## Adapter Config Schema

```json
{
  "base_model_name_or_path": "mistralai/Mistral-7B-v0.3",
  "task_type": "CAUSAL_LM",
  "r": 32,
  "lora_alpha": 64,
  "lora_dropout": 0.05,
  "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
  "bias": "none",
  "dataset_path": "finetune/datasets/01-customer-support/data.jsonl",
  "use_case_id": "01-customer-support",
  "use_case_name": "Customer Support & Helpdesk"
}
```

## Training Config Schema

```json
{
  "num_train_epochs": 3,
  "learning_rate": 2e-4,
  "per_device_train_batch_size": 4,
  "gradient_accumulation_steps": 4,
  "warmup_steps": 100,
  "max_seq_length": 2048,
  "vram_estimate_gb": 10,
  "output_dir": "finetune/output/01-customer-support"
}
```
