from typing import TypeVar

from pydantic import BaseModel

from analyst.config import settings
from llm.providers import attribution_headers, build_client
from llm.structured import complete_structured

T = TypeVar("T", bound=BaseModel)


async def complete_for_task(
    task: str, messages: list[dict[str, str]], schema: type[T]
) -> T:
    client = build_client(
        settings.analyst_llm_provider,
        settings.analyst_llm_api_key,
        settings.analyst_llm_base_url,
        settings.analyst_request_timeout_seconds,
        attribution_headers(
            settings.analyst_attribution_referer,
            settings.analyst_attribution_title,
        ),
    )
    return await complete_structured(client, settings.model_for(task), messages, schema)
