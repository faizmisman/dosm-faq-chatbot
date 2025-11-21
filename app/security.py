from fastapi import Header, HTTPException
from app.config import settings

async def require_api_key(x_api_key: str | None = Header(default=None)):
    """Dependency to enforce API key if configured.
    If settings.API_KEY is None, auth is bypassed (open mode)."""
    if settings.API_KEY is None:
        return
    if x_api_key is None or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
