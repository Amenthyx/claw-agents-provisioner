#!/usr/bin/env python3
"""
Claw Agents Provisioner — QLoRA Training Script

4-bit quantized LoRA fine-tuning using bitsandbytes NF4 quantization.
Requires only 8-16 GB VRAM (RTX 3060/3070/3080).

Uses the same interface as train_lora.py but loads the base model in 4-bit
precision using bitsandbytes, reducing VRAM by ~4x.

Usage:
    python train_qlora.py --base-model mistralai/Mistral-7B-v0.3 \\
                          --dataset finetune/output/training_data.jsonl \\
                          --output-dir finetune/output/adapter/ \\
                          --rank 32 --epochs 3

    python train_qlora.py --config finetune/adapters/02-real-estate/training_config.json
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
logger = logging.getLogger("train_qlora")


def load_training_config(config_path: Path) -> dict[str, Any]:
    """Load training configuration from a JSON file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments with training_config.json fallback."""
    parser = argparse.ArgumentParser(
        description="QLoRA (4-bit quantized) fine-tuning for Claw AI agent adapters"
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
        "--batch-size", type=int, default=2, help="Per-device batch size (smaller for QLoRA)"
    )
    parser.add_argument(
        "--gradient-accumulation",
        type=int,
        default=8,
        help="Gradient accumulation steps (higher to compensate smaller batch)",
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
        "--double-quant",
        action="store_true",
        default=True,
        help="Use double quantization (recommended for QLoRA)",
    )
    parser.add_argument(
        "--quant-type",
        type=str,
        default="nf4",
        choices=["nf4", "fp4"],
        help="Quantization type: nf4 (default, better) or fp4",
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
    """Run QLoRA training with 4-bit quantization."""
    try:
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
            Trainer,
            DataCollatorForSeq2Seq,
            BitsAndBytesConfig,
        )
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
        from datasets import Dataset
    except ImportError as e:
        logger.error(
            f"Missing dependency: {e}. Install with: pip install -r finetune/requirements.txt"
        )
        sys.exit(1)

    logger.info(f"Base model: {args.base_model}")
    logger.info(f"Quantization: 4-bit {args.quant_type.upper()}, double quant: {args.double_quant}")
    logger.info(f"LoRA rank: {args.rank}, alpha: {args.lora_alpha}")
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Output: {args.output_dir}")

    if torch.cuda.is_available():
        vram_gb = torch.cuda.get_device_properties(0).total_mem / 1e9
        logger.info(f"VRAM available: {vram_gb:.1f} GB")
        if vram_gb < 8:
            logger.warning(
                "Less than 8 GB VRAM detected. QLoRA may fail for 7B models. "
                "Consider using Phi-3 Mini (3.8B) or reducing max_seq_length."
            )
    else:
        logger.warning("No GPU detected — QLoRA requires CUDA-capable GPU")

    # 4-bit quantization config (NF4)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=args.quant_type,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=args.double_quant,
    )

    # Load tokenizer
    logger.info("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load base model in 4-bit
    logger.info("Loading base model in 4-bit quantized mode...")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)

    # Configure LoRA
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=args.target_modules,
        bias="none",
    )

    logger.info("Applying QLoRA adapter...")
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load and tokenize dataset
    raw_data = load_dataset(args.dataset)

    def format_chat(example: dict[str, Any]) -> str:
        """Format a chat example into a single string."""
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
        """Tokenize examples."""
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

    split = tokenized_dataset.train_test_split(test_size=0.05, seed=42)

    # Training arguments (optimized for QLoRA / low VRAM)
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
        fp16=False,  # QLoRA uses bf16 compute, not fp16
        bf16=True,
        optim="paged_adamw_8bit",  # 8-bit Adam for additional VRAM savings
        evaluation_strategy="steps",
        eval_steps=args.save_steps,
        load_best_model_at_end=True,
        report_to=["tensorboard"],
        logging_dir=str(args.output_dir / "logs"),
        push_to_hub=args.push_to_hub,
        hub_model_id=args.hub_model_id,
        gradient_checkpointing=True,  # Trade compute for memory
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        data_collator=data_collator,
    )

    # Train
    logger.info("Starting QLoRA training (4-bit quantized)...")
    trainer.train()

    # Save adapter (only adapter weights, not the quantized base model)
    logger.info(f"Saving QLoRA adapter to {args.output_dir}...")
    model.save_pretrained(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))

    # Save metadata
    metadata = {
        "base_model": args.base_model,
        "method": "qlora",
        "quantization": f"4-bit {args.quant_type}",
        "double_quant": args.double_quant,
        "rank": args.rank,
        "alpha": args.lora_alpha,
        "target_modules": args.target_modules,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "dataset_path": str(args.dataset),
        "dataset_rows": len(raw_data),
        "optimizer": "paged_adamw_8bit",
        "gradient_checkpointing": True,
        "training_complete": True,
    }
    metadata_path = args.output_dir / "training_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("QLoRA training complete!")
    logger.info(f"Adapter saved to: {args.output_dir}")


def main() -> int:
    """CLI entry point."""
    args = parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN — Validating QLoRA configuration ===")
        logger.info(f"Base model:        {args.base_model}")
        logger.info(f"Quantization:      4-bit {args.quant_type}")
        logger.info(f"Double quant:      {args.double_quant}")
        logger.info(f"LoRA rank:         {args.rank}")
        logger.info(f"Target modules:    {args.target_modules}")
        logger.info(f"Dataset:           {args.dataset}")
        logger.info(f"Output:            {args.output_dir}")
        logger.info(f"Epochs:            {args.epochs}")
        logger.info(f"Batch size:        {args.batch_size}")
        logger.info(f"Grad accumulation: {args.gradient_accumulation}")
        logger.info(f"Effective batch:   {args.batch_size * args.gradient_accumulation}")

        if not args.dataset.exists():
            logger.error(f"Dataset not found: {args.dataset}")
            return 1

        data = load_dataset(args.dataset)
        logger.info(f"Dataset rows:      {len(data)}")
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
