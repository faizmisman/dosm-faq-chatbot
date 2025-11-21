from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class Citation(BaseModel):
    source: str
    snippet: str
    page_or_row: int | None = None

class PredictRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    tool_name: Optional[str] = None

class Prediction(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    failure_mode: str | None = None

class PredictResponse(BaseModel):
    prediction: Prediction
    latency_ms: int
    model_version: str
