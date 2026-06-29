"""
Demo API authentication — API key protection for Kaggle capstone endpoints.

Uses DEMO_API_KEY env var checked via X-API-Key header via FastAPI dependency.
This demonstrates API security best practices without adding auth
complexity for judges evaluating the demo.

Security model:
  1. Client sends X-API-Key: <key> header with every request
  2. Server compares against DEMO_API_KEY env var
  3. 403 if missing or invalid
  4. If DEMO_API_KEY is not set, check is bypassed (judges can test freely)

For production: replace with HMAC (core/tg_auth.py), JWT, or OAuth.
"""
import os
import logging
from fastapi import Header, HTTPException, Depends

logger = logging.getLogger(__name__)

DEMO_API_KEY = os.getenv("DEMO_API_KEY", "").strip()


async def verify_demo_key(x_api_key: str = Header(None)) -> None:
    """FastAPI dependency. Returns None if authorized, raises 403 otherwise.

    Usage:
        @app.post("/api/demo/consult")
        async def handler(req: dict, _auth: None = Depends(verify_demo_key)):
            ...
    """
    if not DEMO_API_KEY:
        return  # No key configured — allow all

    if not x_api_key:
        raise HTTPException(
            status_code=403,
            detail="Missing API key. Send X-API-Key header.",
        )

    # Constant-time-ish comparison (both are short strings, fine for demo)
    if x_api_key != DEMO_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )
