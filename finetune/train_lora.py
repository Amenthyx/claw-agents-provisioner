#!/usr/bin/env python3
"""
Claw Agents Provisioner — LoRA Training Script

Full-precision LoRA (Low-Rank Adaptation) training using Hugging Face
PEFT + Transformers. Requires 24+ GB VRAM (A100, RTX 4090).

Configurable via CLI arguments or a training_config.json file.

Usage:
    python train_lora.py --base-model mistralai/Mistral-7B-v0.3 \\
                         --dataset finetune/output/training_data.jsonl \\
                         --output-dir finetune/output/adapter/ \\
                         --rank 32 --epochs 3

    python train_lora.py --config finetune/adapters/02-real-estate/training_config.json
"""

import argparse
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
logger = logging.getLogger("train_lora")


def load_training_config(config_path: Path) -> dict[str, Any]:
    """Load training configuration from a JSON file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments with training_config.json fallback."""
    parser = argparse.ArgumentParser(
        description="LoRA fine-tuning for Claw AI agent adapters"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to training_config.json (overrides CLI args)",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="mistralai/Mistral-7B-v0.3",
        help="HuggingFace model ID for the base model",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("finetune/output/training_data.jsonl"),
        help="Path to the training dataset (JSONL)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("finetune/output/adapter"),
        help="Directory to save the trained adapter",
    )
    parser.add_argument(
        "--rank", type=int, default=32, help="LoRA rank (16, 32, 64)"
    )
    parser.add_argument(
        "--lora-alpha", type=int, default=64, help="LoRA alpha scaling factor"
    )
    parser.add_argument(
        "--lora-dropout", type=float, default=0.05, help="LoRA dropout rate"
    )
    parser.add_argument(
        "--target-modules",
        type=str,
        nargs="+",
        default=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        help="Target modules for LoRA adaptation",
    )
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument(
        "--batch-size", type=int, default=4, help="Per-device batch size"
    )
    parser.add_argument(
        "--gradient-accumulation",
        type=int,
        default=4,
        help="Gradient accumulation steps",
    )
    parser.add_argument(
        "--learning-rate", type=float, default=2e-4, help="Learning rate"
    )
    parser.add_argument(
        "--warmup-steps", type=int, default=100, help="LR warmup steps"
    )
    parser.add_argument(
        "--max-seq-length", type=int, default=2048, help="Maximum sequence length"
    )
    parser.add_argument(
        "--logging-steps", type=int, default=10, help="Log every N steps"
    )
    parser.add_argument(
        "--save-steps", type=int, default=200, help="Save checkpoint every N steps"
    )
    parser.add_argument(
        "--fp16", action="store_true", default=True, help="Use FP16 training"
    )
    parser.add_argument(
        "--bf16", action="store_true", default=False, help="Use BF16 training (A100+)"
    )
    parser.add_argument(
        "--push-to-hub", action="store_true", help="Push adapter to HuggingFace Hub"
    )
    parser.add_argument(
        "--hub-model-id", type=str, help="HuggingFace Hub model ID for push"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config without training",
    )

    args = parser.parse_args()

    # Override with config file if provided
    if args.config and args.config.exists():
        config = load_training_config(args.config)
        for key, value in config.items():
            key_underscore = key.replace("-", "_")
            if hasattr(args, key_underscore) and value is not None:
                setattr(args, key_underscore, value)

    return args


def load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    """Load JSONL training dataset."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    data: list[dict[str, Any]] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed line {line_num}")

    logger.info(f"Loaded {len(data)} training examples from {dataset_path}")
    return data


def train(args: argparse.Namespace) -> None:
    """Run LoRA training."""
    # Lazy imports — only import heavy libraries when actually training
    try:
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
            Trainer,
            DataCollatorForSeq2Seq,
        )
        from peft import LoraConfig, get_peft_model, TaskType
        from datasets import Dataset
    except ImportError as e:
        logger.error(
            f"Missing dependency: {e}. Install with: pip install -r finetune/requirements.txt"
        )
        sys.exit(1)

    logger.info(f"Base model: {args.base_model}")
    logger.info(f"LoRA rank: {args.rank}, alpha: {args.lora_alpha}")
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Output: {args.output_dir}")
    logger.info(f"Epochs: {args.epochs}, batch size: {args.batch_size}")
    logger.info(
        f"VRAM available: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB"
        if torch.cuda.is_available()
        else "No GPU detected — training will be very slow on CPU"
    )

    # Load tokenizer
    logger.info("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load base model (full precision for LoRA)
    logger.info("Loading base model (full precision)...")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float16 if args.fp16 else (torch.bfloat16 if args.bf16 else torch.float32),
        device_map="auto",
        trust_remote_code=True,
    )

    # Configure LoRA
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=args.target_modules,
        bias="none",
    )

    logger.info("Applying LoRA adapter...")
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load and tokenize dataset
    raw_data = load_dataset(args.dataset)

    def format_chat(example: dict[str, Any]) -> str:
        """Format a chat example into a single string for tokenization."""
        messages = example.get("messages", [])
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"<|system|>\n{content}")
            elif role == "user":
                parts.append(f"<|user|>\n{content}")
            elif role == "assistant":
                parts.append(f"<|assistant|>\n{content}")
        return "\n".join(parts)

    def tokenize_fn(examples: dict[str, list]) -> dict[str, list]:
        """Tokenize examples for training."""
        texts = [format_chat({"messages": m}) for m in examples["messages"]]
        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=args.max_seq_length,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    dataset = Dataset.from_list(raw_data)
    tokenized_dataset = dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=dataset.column_names,
        desc="Tokenizing",
    )

    # Split into train/eval
    split = tokenized_dataset.train_test_split(test_size=0.05, seed=42)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=3,
        fp16=args.fp16,
        bf16=args.bf16,
        evaluation_strategy="steps",
        eval_steps=args.save_steps,
        load_best_model_at_end=True,
        report_to=["tensorboard"],
        logging_dir=str(args.output_dir / "logs"),
        push_to_hub=args.push_to_hub,
        hub_model_id=args.hub_model_id,
    )

    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding=True,
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        data_collator=data_collator,
    )

    # Train
    logger.info("Starting LoRA training...")
    trainer.train()

    # Save adapter
    logger.info(f"Saving adapter to {args.output_dir}...")
    model.save_pretrained(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))

    # Save adapter config metadata
    metadata = {
        "base_model": args.base_model,
        "method": "lora",
        "rank": args.rank,
        "alpha": args.lora_alpha,
        "target_modules": args.target_modules,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "dataset_path": str(args.dataset),
        "dataset_rows": len(raw_data),
        "training_complete": True,
    }
    metadata_path = args.output_dir / "training_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("LoRA training complete!")
    logger.info(f"Adapter saved to: {args.output_dir}")
    logger.info(f"TensorBoard logs: {args.output_dir / 'logs'}")


def main() -> int:
    """CLI entry point."""
    args = parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN — Validating configuration ===")
        logger.info(f"Base model:      {args.base_model}")
        logger.info(f"LoRA rank:       {args.rank}")
        logger.info(f"LoRA alpha:      {args.lora_alpha}")
        logger.info(f"Target modules:  {args.target_modules}")
        logger.info(f"Dataset:         {args.dataset}")
        logger.info(f"Output:          {args.output_dir}")
        logger.info(f"Epochs:          {args.epochs}")
        logger.info(f"Batch size:      {args.batch_size}")
        logger.info(f"Learning rate:   {args.learning_rate}")

        if not args.dataset.exists():
            logger.error(f"Dataset not found: {args.dataset}")
            return 1

        data = load_dataset(args.dataset)
        logger.info(f"Dataset rows:    {len(data)}")
        logger.info("=== Configuration valid ===")
        return 0

    try:
        train(args)
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
