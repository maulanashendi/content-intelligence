import asyncio
import logging
import os
import re
from typing import Any

from core.config import settings
from llm.providers import attribution_headers, build_client
from llm.structured import complete_structured

from labeling.prompts import (
    format_cluster_insight_messages,
    format_cluster_insight_messages_api,
    format_dedup_messages,
    format_extract_messages,
    format_insight_messages,
    format_label_messages_api,
    format_messages,
)
from labeling.schemas import ClusterInsightLLM, ClusterLabelLLM

logger = logging.getLogger(__name__)

_llm: Any | None = None
_llm_lock = asyncio.Lock()

MODEL_REPO_ID = "bartowski/gemma-2-2b-it-GGUF"
MODEL_FILENAME = "gemma-2-2b-it-Q4_K_M.gguf"


def _load_llama_class() -> type[Any]:
    try:
        from llama_cpp import Llama
    except ModuleNotFoundError as exc:
        raise RuntimeError("llama-cpp-python is not installed for the labeling package") from exc

    return Llama


def _resolve_model_path() -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download(
        repo_id=MODEL_REPO_ID,
        filename=MODEL_FILENAME,
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
        # n_threads=4: matches OMP_NUM_THREADS in the Docker image so all BLAS/OpenMP
        # pools are capped at the same value — prevents a single Gemma inference from
        # saturating all 12 host cores when the embedder is also running.
        _llm = llama_cls(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=0,
            n_threads=4,
            verbose=False,
        )
    return _llm


def _chat_sync(messages: list[dict[str, str]], max_tokens: int) -> str:
    llm = get_llm()
    response = llm.create_chat_completion(messages=messages, temperature=0, max_tokens=max_tokens)
    return response["choices"][0]["message"]["content"]


async def _chat(messages: list[dict[str, str]], max_tokens: int) -> str:
    async with _llm_lock:
        return await asyncio.to_thread(_chat_sync, messages, max_tokens)


async def _label_local(articles: list[dict[str, str | None]]) -> str:
    raw = await _chat(format_messages(articles), max_tokens=24)
    return raw.strip().splitlines()[0].strip(" .,:;!?\"'")


_PIHAK_NONE_MARKERS = {"tidak disebutkan", "tidak ada", "tidak diketahui", "-", "n/a"}

CLUSTER_INSIGHT_MAX_TOKENS = 600
_N_CTX = 4096

# Tolerates: leading numbers/bullets, markdown bold open/close, space around colon.
_FIELD_RE = re.compile(
    r"^[\s\d.\-•]*"
    r"(?:\*+)?"
    r"(?P<key>LABEL|APA_TERJADI|APA\s+TERJADI|SUDUT|PIHAK|KLAIM)"
    r"(?:\*+)?"
    r"\s*:\s*"
    r"(?P<value>.*)",
    re.IGNORECASE,
)


def _strip_label(value: str) -> str:
    return value.strip(" .,:;!?\"'")


def _token_len(messages: list[dict[str, str]]) -> int:
    """Count tokens using the loaded LLM tokenizer (call within _llm_lock)."""
    llm = get_llm()
    text = " ".join(m.get("content", "") for m in messages)
    return len(llm.tokenize(text.encode()))


def _parse_cluster_insight(raw: str) -> dict[str, Any]:
    label: str | None = None
    what_happened_parts: list[str] = []
    parties: list[str] = []
    editorial_angle: str | None = None
    summary: list[str] = []

    for raw_line in raw.splitlines():
        m = _FIELD_RE.match(raw_line.strip())
        if not m:
            continue
        key = re.sub(r"\s+", "_", m.group("key").upper())
        value = m.group("value").strip().strip("*").strip()
        if not value:
            continue

        if key == "LABEL" and label is None:
            label = _strip_label(value)
        elif key == "APA_TERJADI":
            what_happened_parts.append(value)
        elif key == "SUDUT" and editorial_angle is None:
            editorial_angle = value
        elif key == "PIHAK":
            if value.lower() not in _PIHAK_NONE_MARKERS:
                parties.append(value)
        elif key == "KLAIM":
            summary.append(value)

    return {
        "label": label,
        "what_happened": " ".join(what_happened_parts) or None,
        "parties_involved": parties or None,
        "editorial_angle": editorial_angle,
        "summary": summary or None,
    }


def _cluster_insight_sync(reps: list[dict]) -> dict[str, Any]:
    """Trim-then-generate: runs inside asyncio.to_thread under _llm_lock."""
    budget = _N_CTX - 128 - CLUSTER_INSIGHT_MAX_TOKENS
    trimmed = list(reps)

    while len(trimmed) > 1:
        messages = format_cluster_insight_messages(trimmed)
        if _token_len(messages) <= budget:
            break
        trimmed = trimmed[:-1]
        logger.warning(
            "cluster insight prompt trimmed to fit n_ctx budget",
            extra={"reps_remaining": len(trimmed)},
        )

    messages = format_cluster_insight_messages(trimmed)
    llm = get_llm()
    response = llm.create_chat_completion(
        messages=messages,
        temperature=0,
        max_tokens=CLUSTER_INSIGHT_MAX_TOKENS,
    )
    raw = response["choices"][0]["message"]["content"]
    result = _parse_cluster_insight(raw)

    if not any(result.values()):
        logger.warning(
            "cluster insight parser matched zero fields",
            extra={"raw_snippet": raw[:200]},
        )
    return result


async def _cluster_insight_local(reps: list[dict]) -> dict[str, Any]:
    async with _llm_lock:
        return await asyncio.to_thread(_cluster_insight_sync, reps)


def _build_labeling_client():
    return build_client(
        settings.labeling_provider,
        settings.labeling_llm_api_key,
        settings.labeling_llm_base_url,
        settings.labeling_request_timeout_seconds,
        attribution_headers(
            settings.labeling_attribution_referer,
            settings.labeling_attribution_title,
        ),
    )


async def _cluster_insight_api(reps: list[dict]) -> dict[str, Any]:
    client = _build_labeling_client()
    result = await complete_structured(
        client,
        settings.labeling_model,
        format_cluster_insight_messages_api(reps),
        ClusterInsightLLM,
    )
    return result.model_dump()


async def _label_api(articles: list[dict[str, str | None]]) -> str:
    client = _build_labeling_client()
    result = await complete_structured(
        client,
        settings.labeling_model,
        format_label_messages_api(articles),
        ClusterLabelLLM,
    )
    return result.label.strip()


async def generate_cluster_insight(reps: list[dict]) -> dict[str, Any]:
    if settings.labeling_provider == "local":
        return await _cluster_insight_local(reps)
    return await _cluster_insight_api(reps)


async def generate_label(articles: list[dict[str, str | None]]) -> str:
    if settings.labeling_provider == "local":
        return await _label_local(articles)
    return await _label_api(articles)


async def generate_label_and_insight(
    articles: list[dict[str, str | None]],
) -> dict[str, Any]:
    """Returns {label, what_happened, parties_involved, editorial_angle}.

    Parser is tolerant of markdown bold and arbitrary leading bullets — Gemma 2B
    often wraps the prefixes (e.g. **LABEL:**) despite the format instruction.
    """
    raw = await _chat(format_insight_messages(articles), max_tokens=384)

    label: str | None = None
    what_happened_parts: list[str] = []
    parties: list[str] = []
    editorial_angle: str | None = None

    for raw_line in raw.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("LABEL:"):
            value = _strip_label(line[len("LABEL:"):])
            if value and label is None:
                label = value
        elif upper.startswith("APA_TERJADI:") or upper.startswith("APA TERJADI:"):
            prefix_len = len("APA_TERJADI:") if upper.startswith("APA_TERJADI:") else len("APA TERJADI:")
            value = _clean_line(line[prefix_len:])
            if value:
                what_happened_parts.append(value)
        elif upper.startswith("PIHAK:"):
            value = _clean_line(line[len("PIHAK:"):])
            if value and value.lower() not in _PIHAK_NONE_MARKERS:
                parties.append(value)
        elif upper.startswith("SUDUT:"):
            value = _clean_line(line[len("SUDUT:"):])
            if value and editorial_angle is None:
                editorial_angle = value

    return {
        "label": label,
        "what_happened": " ".join(what_happened_parts) or None,
        "parties_involved": parties or None,
        "editorial_angle": editorial_angle,
    }


def _clean_line(line: str) -> str:
    """Strip whitespace and markdown bold markers so **KLAIM:** parses as KLAIM:."""
    return line.strip().strip("*").strip()


async def extract_article_claims(title: str, content: str) -> dict[str, Any]:
    """Returns {"main_entity": str | None, "information_claims": list[str]}."""
    raw = await _chat(format_extract_messages(title, content), max_tokens=512)
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


async def deduplicate_claims(all_claims: list[list[str]]) -> list[str]:
    """Returns deduplicated unique claims across all articles in a cluster."""
    if not any(all_claims):
        return []
    raw = await _chat(format_dedup_messages(all_claims), max_tokens=512)
    unique: list[str] = []
    for raw_line in raw.splitlines():
        line = _clean_line(raw_line)
        if line.upper().startswith("KLAIM:"):
            value = _clean_line(line[len("KLAIM:"):])
            if value:
                unique.append(value)
    return unique
