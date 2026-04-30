import logging
import os
from typing import Any

from core.config import settings

from labeling.prompts import format_messages

logger = logging.getLogger(__name__)

_llm: Any | None = None

MODEL_REPO_ID = "bartowski/gemma-2-2b-it-GGUF"
MODEL_FILENAME = "gemma-2-2b-it-Q4_K_M.gguf"
MAX_TOKENS = 24


def _load_llama_class() -> type[Any]:
    try:
        from llama_cpp import Llama
    except ModuleNotFoundError as exc:
        raise RuntimeError("llama-cpp-python is not installed for the labeling package") from exc

    return Llama


def get_llm() -> Any:
    global _llm
    if _llm is None:
        os.environ.setdefault("HF_HOME", settings.hf_home)
        llama_cls = _load_llama_class()
        logger.info(
            "loading labeling llm",
            extra={"repo_id": MODEL_REPO_ID, "model_filename": MODEL_FILENAME},
        )
        _llm = llama_cls.from_pretrained(
            repo_id=MODEL_REPO_ID,
            filename=MODEL_FILENAME,
            n_ctx=2048,
            n_gpu_layers=-1,
            verbose=False,
        )
    return _llm


def generate_label(articles: list[dict[str, str | None]]) -> str:
    llm = get_llm()
    messages = format_messages(articles)
    response = llm.create_chat_completion(
        messages=messages,
        temperature=0,
        max_tokens=MAX_TOKENS,
    )
    content = response["choices"][0]["message"]["content"]
    return content.strip().splitlines()[0].strip(" .,:;!?\"'")
