import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

logger = logging.getLogger(__name__)


def verify_init_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram Mini App initData HMAC signature.

    Returns verified user dict (id, first_name, username, etc.).
    Raises ValueError if signature is invalid.
    """
    parsed = dict(parse_qsl(init_data))
    hash_value = parsed.pop("hash", "")
    if not hash_value:
        raise ValueError("Missing hash in initData")
    items = sorted(parsed.items())
    check_string = "\n".join(f"{k}={v}" for k, v in items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if expected != hash_value:
        raise ValueError("HMAC mismatch — data tampered")
    user_raw = parsed.get("user", "{}")
    if isinstance(user_raw, str):
        return json.loads(user_raw)
    return user_raw
