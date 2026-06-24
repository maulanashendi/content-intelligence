from pydantic import BaseModel


class ClusterInsightLLM(BaseModel):
    label: str
    what_happened: str | None = None
    parties_involved: list[str] | None = None
    editorial_angle: str | None = None
    summary: list[str] | None = None


class ClusterLabelLLM(BaseModel):
    label: str
