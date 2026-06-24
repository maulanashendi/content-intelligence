import analyst.llm as alm
from analyst.config import AnalystSettings
from pydantic import BaseModel


class _Schema(BaseModel):
    x: str


async def test_complete_for_task_wires_settings(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_client(provider, api_key, base_url, timeout, headers):
        captured["provider"] = provider
        return "CLIENT"

    async def fake_complete_structured(client, model, messages, schema):
        captured["client"] = client
        captured["model"] = model
        return _Schema(x="ok")

    monkeypatch.setattr(alm, "build_client", fake_build_client)
    monkeypatch.setattr(alm, "complete_structured", fake_complete_structured)
    # pin settings to known defaults so the test is independent of .env
    monkeypatch.setattr(alm, "settings", AnalystSettings(_env_file=None))

    out = await alm.complete_for_task("analyze", [{"role": "user", "content": "hi"}], _Schema)

    assert out.x == "ok"
    assert captured["client"] == "CLIENT"
    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-4o"
