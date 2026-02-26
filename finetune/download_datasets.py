#!/usr/bin/env python3
"""
Claw Agents Provisioner — Dataset Downloader

Downloads all 50 use-case datasets from their sources (HuggingFace, Kaggle,
direct URLs). For each dataset:
    - Fetch from source
    - Sample/truncate to <=10,000 rows
    - Convert to JSONL format (messages format for fine-tuning)
    - Generate/update metadata.json
    - Save to finetune/datasets/<##-use-case>/

Usage:
    python download_datasets.py                    # Download all 50
    python download_datasets.py --use-case 02-real-estate  # Download one
    python download_datasets.py --list             # List all datasets with status
    python download_datasets.py --dry-run          # Show what would be downloaded
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("download_datasets")

DATASETS_DIR = Path(__file__).parent / "datasets"
MAX_ROWS = 10_000


# Registry of all 50 datasets with their download sources
DATASET_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "01-customer-support",
        "name": "Customer Support & Helpdesk",
        "source_type": "huggingface",
        "source_id": "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        "source_url": "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        "license": "Apache-2.0",
        "language": "en",
    },
    {
        "id": "02-real-estate",
        "name": "Real Estate Agent",
        "source_type": "huggingface",
        "source_id": "housing_market_qa",
        "source_url": "https://huggingface.co/datasets/RealEstate/housing-qa",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "03-e-commerce",
        "name": "E-Commerce Assistant",
        "source_type": "huggingface",
        "source_id": "amazon_products_qa",
        "source_url": "https://huggingface.co/datasets/AmazonScience/amazon-product-qa",
        "license": "Apache-2.0",
        "language": "en",
    },
    {
        "id": "04-healthcare",
        "name": "Healthcare Triage",
        "source_type": "huggingface",
        "source_id": "medquad",
        "source_url": "https://huggingface.co/datasets/keivalya/MedQuad-MedicalQnADataset",
        "license": "CC0-1.0",
        "language": "en",
    },
    {
        "id": "05-legal",
        "name": "Legal Document Review",
        "source_type": "huggingface",
        "source_id": "casehold",
        "source_url": "https://huggingface.co/datasets/casehold/casehold",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "06-personal-finance",
        "name": "Personal Finance Advisor",
        "source_type": "huggingface",
        "source_id": "financial_phrasebank",
        "source_url": "https://huggingface.co/datasets/financial_phrasebank",
        "license": "CC-BY-SA-3.0",
        "language": "en",
    },
    {
        "id": "07-code-review",
        "name": "Code Review & Dev Workflow",
        "source_type": "huggingface",
        "source_id": "code_review",
        "source_url": "https://huggingface.co/datasets/mhassanen/code-review-instruction-dataset",
        "license": "Apache-2.0",
        "language": "en",
    },
    {
        "id": "08-email-management",
        "name": "Email Management & Drafting",
        "source_type": "huggingface",
        "source_id": "aeslc",
        "source_url": "https://huggingface.co/datasets/aeslc",
        "license": "Apache-2.0",
        "language": "en",
    },
    {
        "id": "09-calendar-scheduling",
        "name": "Calendar & Scheduling",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "10-meeting-summarization",
        "name": "Meeting Summarization",
        "source_type": "huggingface",
        "source_id": "ami_meeting_corpus",
        "source_url": "https://huggingface.co/datasets/edinburghcstr/ami",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "11-sales-crm",
        "name": "Sales & CRM Assistant",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "12-hr-recruitment",
        "name": "HR & Recruitment",
        "source_type": "huggingface",
        "source_id": "job_descriptions",
        "source_url": "https://huggingface.co/datasets/jacob-hugging-face/job-descriptions",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "13-it-helpdesk",
        "name": "IT Helpdesk & Troubleshooting",
        "source_type": "huggingface",
        "source_id": "askubuntu",
        "source_url": "https://huggingface.co/datasets/embedding-data/AskUbuntu",
        "license": "CC-BY-SA-3.0",
        "language": "en",
    },
    {
        "id": "14-content-writing",
        "name": "Content Writing & Marketing",
        "source_type": "huggingface",
        "source_id": "writing_prompts",
        "source_url": "https://huggingface.co/datasets/euclaise/writingprompts",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "15-social-media",
        "name": "Social Media Management",
        "source_type": "huggingface",
        "source_id": "tweet_eval",
        "source_url": "https://huggingface.co/datasets/tweet_eval",
        "license": "Apache-2.0",
        "language": "en",
    },
    {
        "id": "16-translation-multilingual",
        "name": "Translation & Multilingual",
        "source_type": "huggingface",
        "source_id": "opus_books",
        "source_url": "https://huggingface.co/datasets/opus_books",
        "license": "CC-BY-4.0",
        "language": "multi",
    },
    {
        "id": "17-education-tutoring",
        "name": "Education & Tutoring",
        "source_type": "huggingface",
        "source_id": "sciq",
        "source_url": "https://huggingface.co/datasets/allenai/sciq",
        "license": "CC-BY-NC-3.0",
        "language": "en",
    },
    {
        "id": "18-research-summarization",
        "name": "Research & Summarization",
        "source_type": "huggingface",
        "source_id": "scientific_papers",
        "source_url": "https://huggingface.co/datasets/scientific_papers",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "19-data-analysis",
        "name": "Data Analysis & Reporting",
        "source_type": "huggingface",
        "source_id": "wikisql",
        "source_url": "https://huggingface.co/datasets/wikisql",
        "license": "CC-BY-SA-4.0",
        "language": "en",
    },
    {
        "id": "20-project-management",
        "name": "Project Management",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "21-accounting-bookkeeping",
        "name": "Accounting & Bookkeeping",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "22-insurance-claims",
        "name": "Insurance Claims Processing",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "23-travel-hospitality",
        "name": "Travel & Hospitality",
        "source_type": "huggingface",
        "source_id": "travel_qa",
        "source_url": "https://huggingface.co/datasets/nampdn-ai/travel-qa",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "24-food-restaurant",
        "name": "Food & Restaurant",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "25-fitness-wellness",
        "name": "Fitness & Wellness",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "26-automotive-vehicle",
        "name": "Automotive & Vehicle",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "27-supply-chain-logistics",
        "name": "Supply Chain & Logistics",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "28-manufacturing-qa",
        "name": "Manufacturing & QA",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "29-agriculture-farming",
        "name": "Agriculture & Farming",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "30-energy-utilities",
        "name": "Energy & Utilities",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "31-telecommunications",
        "name": "Telecommunications",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "32-government-public-services",
        "name": "Government & Public Services",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "33-nonprofit-fundraising",
        "name": "Nonprofit & Fundraising",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "34-event-planning",
        "name": "Event Planning & Coordination",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "35-cybersecurity-threat-intel",
        "name": "Cybersecurity & Threat Intel",
        "source_type": "huggingface",
        "source_id": "cve_descriptions",
        "source_url": "https://huggingface.co/datasets/CyberNative/CyberSecurityQA",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "36-devops-infrastructure",
        "name": "DevOps & Infrastructure",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "37-api-integration-webhooks",
        "name": "API Integration & Webhooks",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "38-database-administration",
        "name": "Database Administration",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "39-iot-smart-home",
        "name": "IoT & Smart Home",
        "source_type": "huggingface",
        "source_id": "snips",
        "source_url": "https://huggingface.co/datasets/snips_built_in_intents",
        "license": "CC0-1.0",
        "language": "en",
    },
    {
        "id": "40-chatbot-conversational",
        "name": "Chatbot & Conversational AI",
        "source_type": "huggingface",
        "source_id": "daily_dialog",
        "source_url": "https://huggingface.co/datasets/daily_dialog",
        "license": "CC-BY-NC-SA-4.0",
        "language": "en",
    },
    {
        "id": "41-document-processing",
        "name": "Document Processing & OCR",
        "source_type": "huggingface",
        "source_id": "docvqa",
        "source_url": "https://huggingface.co/datasets/lmms-lab/DocVQA",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "42-knowledge-base-faq",
        "name": "Knowledge Base & FAQ",
        "source_type": "huggingface",
        "source_id": "faq_qa",
        "source_url": "https://huggingface.co/datasets/clips/mfaq",
        "license": "CC-BY-SA-4.0",
        "language": "en",
    },
    {
        "id": "43-compliance-regulatory",
        "name": "Compliance & Regulatory",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "44-onboarding-training",
        "name": "Onboarding & Training",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "45-sentiment-analysis",
        "name": "Sentiment Analysis & Feedback",
        "source_type": "huggingface",
        "source_id": "amazon_reviews",
        "source_url": "https://huggingface.co/datasets/amazon_reviews_multi",
        "license": "Apache-2.0",
        "language": "en",
    },
    {
        "id": "46-creative-writing",
        "name": "Creative Writing & Storytelling",
        "source_type": "huggingface",
        "source_id": "writing_prompts",
        "source_url": "https://huggingface.co/datasets/euclaise/writingprompts",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "47-music-entertainment",
        "name": "Music & Entertainment",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "48-gaming-virtual-worlds",
        "name": "Gaming & Virtual Worlds",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
    {
        "id": "49-mental-health-counseling",
        "name": "Mental Health & Counseling",
        "source_type": "huggingface",
        "source_id": "counsel_chat",
        "source_url": "https://huggingface.co/datasets/nbertagnolli/counsel-chat",
        "license": "CC-BY-4.0",
        "language": "en",
    },
    {
        "id": "50-personal-finance-budgeting",
        "name": "Personal Finance & Budgeting",
        "source_type": "synthetic",
        "source_url": "https://github.com/Amenthyx/claw-agents-provisioner",
        "license": "MIT",
        "language": "en",
    },
]


def download_huggingface(dataset_info: dict[str, Any], output_dir: Path) -> int:
    """
    Download a dataset from HuggingFace Datasets Hub.

    Returns the number of rows saved.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("Install 'datasets' library: pip install datasets")
        return 0

    source_id = dataset_info.get("source_id", "")
    logger.info(f"Downloading from HuggingFace: {source_id}")

    try:
        ds = load_dataset(source_id, split="train", trust_remote_code=True)
        if len(ds) > MAX_ROWS:
            ds = ds.shuffle(seed=42).select(range(MAX_ROWS))

        # Convert to JSONL with messages format
        data_path = output_dir / "data.jsonl"
        count = 0
        with open(data_path, "w", encoding="utf-8") as f:
            for row in ds:
                # Try to extract Q&A pairs from various column formats
                messages = convert_row_to_messages(row, dataset_info)
                if messages:
                    f.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
                    count += 1

        logger.info(f"Saved {count} rows to {data_path}")
        return count

    except Exception as e:
        logger.error(f"Failed to download {source_id}: {e}")
        return 0


def convert_row_to_messages(
    row: dict[str, Any], dataset_info: dict[str, Any]
) -> list[dict[str, str]] | None:
    """Convert a raw dataset row to chat message format."""
    system_content = f"You are a helpful assistant specialized in {dataset_info['name']}."

    # Try common column patterns
    if "instruction" in row and "response" in row:
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": str(row["instruction"])},
            {"role": "assistant", "content": str(row["response"])},
        ]
    if "question" in row and "answer" in row:
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": str(row["question"])},
            {"role": "assistant", "content": str(row["answer"])},
        ]
    if "input" in row and "output" in row:
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": str(row["input"])},
            {"role": "assistant", "content": str(row["output"])},
        ]
    if "text" in row:
        # Single text — use as assistant response with generic prompt
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Help me with {dataset_info['name'].lower()}."},
            {"role": "assistant", "content": str(row["text"])[:2000]},
        ]
    if "messages" in row:
        return row["messages"]

    return None


def download_synthetic(dataset_info: dict[str, Any], output_dir: Path) -> int:
    """
    For synthetic datasets, the seed data.jsonl is already present.
    This function just verifies and counts rows.
    """
    data_path = output_dir / "data.jsonl"
    if data_path.exists():
        count = sum(1 for line in open(data_path, "r", encoding="utf-8") if line.strip())
        logger.info(f"Synthetic dataset already present: {count} rows")
        return count
    else:
        logger.warning(f"No seed data found at {data_path}")
        return 0


def update_metadata(dataset_info: dict[str, Any], output_dir: Path, row_count: int) -> None:
    """Update the metadata.json for a dataset."""
    metadata_path = output_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        metadata["sampled_rows"] = row_count
    else:
        metadata = {
            "use_case_id": dataset_info["id"],
            "use_case_name": dataset_info["name"],
            "source_url": dataset_info["source_url"],
            "source_name": dataset_info.get("source_id", dataset_info["name"]),
            "license": dataset_info["license"],
            "original_rows": row_count,
            "sampled_rows": row_count,
            "format": "jsonl",
            "columns": ["messages"],
            "language": dataset_info["language"],
            "domain_tags": [dataset_info["id"].split("-", 1)[1]],
            "recommended_base_model": "mistralai/Mistral-7B-v0.3",
            "recommended_lora_rank": 32,
        }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def download_one(dataset_info: dict[str, Any]) -> bool:
    """Download a single dataset."""
    dataset_id = dataset_info["id"]
    output_dir = DATASETS_DIR / dataset_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"--- Processing {dataset_id}: {dataset_info['name']} ---")

    source_type = dataset_info.get("source_type", "synthetic")
    if source_type == "huggingface":
        row_count = download_huggingface(dataset_info, output_dir)
    else:
        row_count = download_synthetic(dataset_info, output_dir)

    if row_count > 0:
        update_metadata(dataset_info, output_dir, row_count)
        return True

    return False


def list_datasets() -> None:
    """List all 50 datasets with their status."""
    print(f"{'#':<4} {'ID':<35} {'Name':<35} {'Status':<10} {'Rows':<8}")
    print("-" * 92)

    for i, ds in enumerate(DATASET_REGISTRY, 1):
        ds_dir = DATASETS_DIR / ds["id"]
        data_path = ds_dir / "data.jsonl"
        metadata_path = ds_dir / "metadata.json"

        if data_path.exists():
            row_count = sum(1 for line in open(data_path, "r", encoding="utf-8") if line.strip())
            status = "OK" if metadata_path.exists() else "NO META"
        else:
            row_count = 0
            status = "MISSING"

        print(f"{i:<4} {ds['id']:<35} {ds['name']:<35} {status:<10} {row_count:<8}")


def main() -> int:
    """CLI entry point."""
    if "--list" in sys.argv:
        list_datasets()
        return 0

    if "--use-case" in sys.argv:
        idx = sys.argv.index("--use-case")
        if idx + 1 < len(sys.argv):
            target_id = sys.argv[idx + 1]
            for ds in DATASET_REGISTRY:
                if ds["id"] == target_id:
                    success = download_one(ds)
                    return 0 if success else 1
            logger.error(f"Unknown use case: {target_id}")
            return 1

    dry_run = "--dry-run" in sys.argv

    # Download all
    success_count = 0
    fail_count = 0

    for ds in DATASET_REGISTRY:
        if dry_run:
            logger.info(f"[DRY RUN] Would download: {ds['id']} from {ds['source_url']}")
            success_count += 1
        else:
            if download_one(ds):
                success_count += 1
            else:
                fail_count += 1

    logger.info(f"Complete: {success_count} succeeded, {fail_count} failed")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
