import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl, unquote

logger = logging.getLogger(__name__)


def verify_init_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram Mini App initData HMAC signature.

    Returns verified user dict (id, first_name, username, etc.).
    Raises ValueError if signature is invalid.
    """
    logger.info("=== TG_AUTH raw init_data (first 300): %s", init_data[:300])
    parsed = dict(parse_qsl(init_data))
    logger.info("=== TG_AUTH parsed keys: %s", list(parsed.keys()))
    hash_value = parsed.pop("hash", "")
    if not hash_value:
        raise ValueError("Missing hash in initData")
    items = sorted(parsed.items())
    check_string = "\n".join(f"{k}={v}" for k, v in items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    logger.info("=== TG_AUTH expected: %s", expected)
    logger.info("=== TG_AUTH hash_value: %s", hash_value)
    if expected != hash_value:
        logger.warning("=== TG_AUTH MISMATCH (hash=%s expected=%s)", hash_value, expected)
        raise ValueError("HMAC mismatch — data tampered")
    logger.info("=== TG_AUTH OK")
    user_raw = parsed.get("user", "{}")
    if isinstance(user_raw, str):
        return json.loads(user_raw)
    return user_raw
