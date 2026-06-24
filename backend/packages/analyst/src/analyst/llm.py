import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from analyst import providers
from analyst.config import settings
from analyst.providers import LLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
    return text.strip()


def _augment(messages: list[dict[str, str]], schema: type[BaseModel]) -> list[dict[str, str]]:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    suffix = f"\n\nRespond ONLY with a single valid JSON object matching this schema:\n{schema_json}"
    out = [dict(m) for m in messages]
    for m in out:
        if m["role"] == "system":
            m["content"] = m["content"] + suffix
            return out
    out.insert(0, {"role": "system", "content": suffix.strip()})
    return out


async def complete_structured(
    client: LLMClient,
    model: str,
    messages: list[dict[str, str]],
    schema: type[T],
) -> T:
    augmented = _augment(messages, schema)
    last_exc: Exception | None = None
    for attempt in (1, 2):
        raw = await client.complete(model=model, messages=augmented)
        try:
            return schema.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "analyst llm returned invalid structured output",
                extra={"attempt": attempt, "schema": schema.__name__},
            )
    raise ValueError(f"LLM returned invalid output for {schema.__name__}: {last_exc}")


async def complete_for_task(
    task: str, messages: list[dict[str, str]], schema: type[T]
) -> T:
    client = providers.build_client(
        settings.analyst_llm_provider,
        settings.analyst_llm_api_key,
        settings.analyst_llm_base_url,
        settings.analyst_request_timeout_seconds,
        providers.attribution_headers(
            settings.analyst_attribution_referer,
            settings.analyst_attribution_title,
        ),
    )
    return await complete_structured(client, settings.model_for(task), messages, schema)
