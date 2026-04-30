import logging
import os

import torch
from core.config import settings
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from labeling.prompts import format_messages

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None

MAX_NEW_TOKENS = 50


def _load_model_and_tokenizer() -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    os.environ["HF_HOME"] = settings.hf_home

    model_name = settings.llm_model_name
    logger.info("loading LLM %s", model_name)

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    if torch.cuda.is_available():
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map="cpu",
        )

    model.eval()
    logger.info("LLM loaded (device=%s)", next(model.parameters()).device)
    return model, tokenizer


def get_model_and_tokenizer() -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    global _model, _tokenizer
    if _model is None:
        _model, _tokenizer = _load_model_and_tokenizer()
    return _model, _tokenizer


def generate_label(articles: list[dict[str, str | None]]) -> str:
    model, tokenizer = get_model_and_tokenizer()

    messages = format_messages(articles)

    inputs = tokenizer.apply_chat_template(
        messages,
        return_tensors="pt",
        return_dict=True,
        add_generation_prompt=True,
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )

    generated_ids = outputs[0][inputs["input_ids"].shape[-1] :]
    label = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    if len(label) > 200:
        label = label[:197] + "..."

    return label
