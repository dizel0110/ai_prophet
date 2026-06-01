import hashlib
import hmac
import json
import logging
from urllib.parse import unquote

logger = logging.getLogger(__name__)


def verify_init_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram Mini App initData HMAC signature.

    IMPORTANT: uses raw URL-encoded values for HMAC check (Telegram signs
    the URL-encoded form, not decoded). Only decodes 'user' after verification.

    Fields excluded from HMAC check: hash, signature.

    Returns verified user dict (id, first_name, username, etc.).
    Raises ValueError if signature is invalid.
    """
    logger.info("=== TG_AUTH raw init_data (first 300): %s", init_data[:300])
    pairs = init_data.split("&") if init_data else []
    parsed_raw = {}
    for pair in pairs:
        if "=" in pair:
            k, v = pair.split("=", 1)
            parsed_raw[k] = v
    logger.info("=== TG_AUTH parsed keys: %s", list(parsed_raw.keys()))
    hash_value = parsed_raw.pop("hash", "")
    parsed_raw.pop("signature", None)
    if not hash_value:
        raise ValueError("Missing hash in initData")
    items = sorted(parsed_raw.items())
    check_string = "\n".join(f"{k}={v}" for k, v in items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    logger.info("=== TG_AUTH check_string (first 300): %s", check_string[:300])
    logger.info("=== TG_AUTH hash_value: %s", hash_value)
    logger.info("=== TG_AUTH expected:     %s", expected)
    if expected != hash_value:
        logger.warning("=== TG_AUTH MISMATCH")
        raise ValueError("HMAC mismatch — data tampered")
    user_raw = unquote(parsed_raw.get("user", "{}"))
    return json.loads(user_raw)
