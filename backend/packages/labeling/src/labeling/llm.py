import logging
import os
from typing import Any

from core.config import settings

from labeling.prompts import format_dedup_messages, format_extract_messages, format_messages

logger = logging.getLogger(__name__)

_llm: Any | None = None

MODEL_REPO_ID = "bartowski/gemma-2-2b-it-GGUF"
MODEL_FILENAME = "gemma-2-2b-it-Q4_K_M.gguf"


def _load_llama_class() -> type[Any]:
    try:
        from llama_cpp import Llama
    except ModuleNotFoundError as exc:
        raise RuntimeError("llama-cpp-python is not installed for the labeling package") from exc

    return Llama


def _resolve_model_path() -> str:
    """Resolve the cached model path without making network calls."""
    from huggingface_hub import hf_hub_download

    return hf_hub_download(
        repo_id=MODEL_REPO_ID,
        filename=MODEL_FILENAME,
        local_files_only=True,
    )


def get_llm() -> Any:
    global _llm
    if _llm is None:
        os.environ.setdefault("HF_HOME", settings.hf_home)
        llama_cls = _load_llama_class()
        model_path = _resolve_model_path()
        logger.info(
            "loading labeling llm",
            extra={"model_path": model_path},
        )
        _llm = llama_cls(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=-1,
            verbose=False,
        )
    return _llm


def _chat(messages: list[dict[str, str]], max_tokens: int) -> str:
    llm = get_llm()
    response = llm.create_chat_completion(messages=messages, temperature=0, max_tokens=max_tokens)
    return response["choices"][0]["message"]["content"]


def generate_label(articles: list[dict[str, str | None]]) -> str:
    raw = _chat(format_messages(articles), max_tokens=24)
    return raw.strip().splitlines()[0].strip(" .,:;!?\"'")


def _clean_line(line: str) -> str:
    """Strip whitespace and markdown bold markers so **KLAIM:** parses as KLAIM:."""
    return line.strip().strip("*").strip()


def extract_article_claims(title: str, content: str) -> dict[str, Any]:
    """Returns {"main_entity": str | None, "information_claims": list[str]}."""
    raw = _chat(format_extract_messages(title, content), max_tokens=512)
    main_entity: str | None = None
    information_claims: list[str] = []
    for raw_line in raw.splitlines():
        line = _clean_line(raw_line)
        if line.upper().startswith("ENTITAS:"):
            value = _clean_line(line[len("ENTITAS:"):])
            if value:
                main_entity = value
        elif line.upper().startswith("KLAIM:"):
            value = _clean_line(line[len("KLAIM:"):])
            if value:
                information_claims.append(value)
    return {"main_entity": main_entity, "information_claims": information_claims}


def deduplicate_claims(all_claims: list[list[str]]) -> list[str]:
    """Returns deduplicated unique claims across all articles in a cluster."""
    if not any(all_claims):
        return []
    raw = _chat(format_dedup_messages(all_claims), max_tokens=512)
    unique: list[str] = []
    for raw_line in raw.splitlines():
        line = _clean_line(raw_line)
        if line.upper().startswith("KLAIM:"):
            value = _clean_line(line[len("KLAIM:"):])
            if value:
                unique.append(value)
    return unique
