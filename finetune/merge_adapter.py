#!/usr/bin/env python3
"""
Claw Agents Provisioner — Adapter Merger

Merges a LoRA/QLoRA adapter with its base model to produce a single
standalone model. This is optional — adapters can also be loaded at
runtime without merging.

Use cases for merging:
    - Deploy a self-contained model without separate adapter files
    - Upload to HuggingFace Hub as a full model
    - Use with inference engines that don't support adapter loading

Usage:
    python merge_adapter.py --base-model mistralai/Mistral-7B-v0.3 \\
                            --adapter-path finetune/output/adapter/ \\
                            --output-dir finetune/output/merged/

    python merge_adapter.py --adapter-path finetune/output/adapter/ \\
                            --output-dir finetune/output/merged/ \\
                            --push-to-hub --hub-model-id username/my-model
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("merge_adapter")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Merge a LoRA/QLoRA adapter with its base model"
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default=None,
        help="HuggingFace model ID for the base model (auto-detected from adapter config if omitted)",
    )
    parser.add_argument(
        "--adapter-path",
        type=Path,
        required=True,
        help="Path to the trained adapter directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to save the merged model",
    )
    parser.add_argument(
        "--push-to-hub",
        action="store_true",
        help="Push merged model to HuggingFace Hub",
    )
    parser.add_argument(
        "--hub-model-id",
        type=str,
        help="HuggingFace Hub model ID for push",
    )
    parser.add_argument(
        "--torch-dtype",
        type=str,
        default="float16",
        choices=["float16", "bfloat16", "float32"],
        help="Dtype for the merged model weights",
    )
    parser.add_argument(
        "--safe-serialization",
        action="store_true",
        default=True,
        help="Save in safetensors format (recommended)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate paths and config without merging",
    )

    return parser.parse_args()


def detect_base_model(adapter_path: Path) -> str | None:
    """Try to detect the base model from adapter config files."""
    # Check training_metadata.json first
    metadata_path = adapter_path / "training_metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        if "base_model" in metadata:
            return metadata["base_model"]

    # Check adapter_config.json (PEFT format)
    config_path = adapter_path / "adapter_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if "base_model_name_or_path" in config:
            return config["base_model_name_or_path"]

    return None


def merge(args: argparse.Namespace) -> None:
    """Merge adapter with base model."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as e:
        logger.error(
            f"Missing dependency: {e}. Install with: pip install -r finetune/requirements.txt"
        )
        sys.exit(1)

    # Resolve base model
    base_model_id = args.base_model
    if base_model_id is None:
        base_model_id = detect_base_model(args.adapter_path)
        if base_model_id is None:
            logger.error(
                "Could not detect base model. Specify with --base-model."
            )
            sys.exit(1)
        logger.info(f"Auto-detected base model: {base_model_id}")

    # Determine dtype
    dtype_map = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    torch_dtype = dtype_map[args.torch_dtype]

    # Load base model
    logger.info(f"Loading base model: {base_model_id} ({args.torch_dtype})")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch_dtype,
        device_map="auto",
        trust_remote_code=True,
    )

    # Load tokenizer
    logger.info("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)

    # Load adapter
    logger.info(f"Loading adapter from: {args.adapter_path}")
    model = PeftModel.from_pretrained(
        base_model,
        str(args.adapter_path),
        torch_dtype=torch_dtype,
    )

    # Merge adapter into base model
    logger.info("Merging adapter weights into base model...")
    merged_model = model.merge_and_unload()

    # Save merged model
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving merged model to: {args.output_dir}")
    merged_model.save_pretrained(
        str(args.output_dir),
        safe_serialization=args.safe_serialization,
    )
    tokenizer.save_pretrained(str(args.output_dir))

    # Save merge metadata
    merge_metadata = {
        "base_model": base_model_id,
        "adapter_path": str(args.adapter_path),
        "merged": True,
        "torch_dtype": args.torch_dtype,
        "safe_serialization": args.safe_serialization,
    }
    with open(args.output_dir / "merge_metadata.json", "w", encoding="utf-8") as f:
        json.dump(merge_metadata, f, indent=2)

    logger.info("Merge complete!")

    # Push to hub if requested
    if args.push_to_hub and args.hub_model_id:
        logger.info(f"Pushing to HuggingFace Hub: {args.hub_model_id}")
        merged_model.push_to_hub(args.hub_model_id)
        tokenizer.push_to_hub(args.hub_model_id)
        logger.info("Push complete!")


def main() -> int:
    """CLI entry point."""
    args = parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN — Validating merge configuration ===")

        # Check adapter path
        if not args.adapter_path.exists():
            logger.error(f"Adapter path not found: {args.adapter_path}")
            return 1

        # Check for adapter files
        has_adapter = (
            (args.adapter_path / "adapter_config.json").exists()
            or (args.adapter_path / "adapter_model.safetensors").exists()
            or (args.adapter_path / "adapter_model.bin").exists()
        )
        if not has_adapter:
            logger.warning(
                f"No adapter_config.json or adapter weights found in {args.adapter_path}. "
                "This directory may not contain a trained adapter."
            )

        base_model = args.base_model or detect_base_model(args.adapter_path)
        logger.info(f"Base model:          {base_model or 'UNKNOWN (specify --base-model)'}")
        logger.info(f"Adapter path:        {args.adapter_path}")
        logger.info(f"Output dir:          {args.output_dir}")
        logger.info(f"Dtype:               {args.torch_dtype}")
        logger.info(f"Safe serialization:  {args.safe_serialization}")
        logger.info("=== Configuration valid ===")
        return 0

    try:
        merge(args)
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
