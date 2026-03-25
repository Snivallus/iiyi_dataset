import os
os.environ["CUDA_VISIBLE_DEVICES"] = "3,4" # Environment settings
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com" # Use the mirror endpoint for faster downloads in China mainland.

import gc
from pathlib import Path
import torch
import torch.distributed as dist
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation.utils import GenerationConfig

# -----------------------
# Model config
# -----------------------
MODEL_NAME = "baichuan-inc/Baichuan2-13B-Chat"
MODEL_REVISION = "v2.0"
CACHE_DIR = Path("./cache")

DTYPE = torch.bfloat16


def load_tokenizer():
    """Load tokenizer."""
    return AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        use_fast=False,
        trust_remote_code=True,
        cache_dir=CACHE_DIR,
    )


def load_model(temperature=0.7, top_p=0.9, max_new_tokens=512):
    """Load LLM model."""
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        device_map="auto",
        torch_dtype=DTYPE,
        trust_remote_code=True,
        cache_dir=CACHE_DIR,
    )

    model.generation_config = GenerationConfig.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        cache_dir=CACHE_DIR,
    )

    model.generation_config.temperature = temperature
    model.generation_config.top_p = top_p
    model.generation_config.max_new_tokens = max_new_tokens

    return model


def chat(model, tokenizer, prompt: str):
    """Simple chat wrapper."""
    messages = [{"role": "user", "content": prompt}]
    return model.chat(tokenizer, messages)


def main():
    tokenizer = load_tokenizer()
    model = None

    try:
        model = load_model()
        
        prompt = "解释一下“温故而知新”"
        response = chat(model, tokenizer, prompt)

        print("\n=== Model Response ===")
        print(response)

    finally:
        print("[CLEANUP] Releasing GPU memory...")
        if model is not None:
            del model
        if tokenizer is not None:
            del tokenizer
        if dist.is_initialized():
            dist.destroy_process_group()
        gc.collect()
        torch.cuda.synchronize()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()