"""Telegram Mini App initData validation.

The client sends Telegram.WebApp.initData in the X-Telegram-Init-Data header.
It is verified server-side using the bot token and is never trusted from the
browser without this signature check.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from urllib.parse import parse_qsl

from fastapi import HTTPException


def is_debug() -> bool:
    return os.getenv("DEBUG", "false").lower() == "true"


def validate_init_data(init_data: str) -> dict:
    """Return validated Telegram user data or raise 401.

    The algorithm follows Telegram's official WebApp validation procedure.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(503, "Telegram authentication is not configured")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise HTTPException(401, "Telegram authentication is missing a signature")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(401, "Telegram authentication signature is invalid")

    try:
        auth_date = int(values["auth_date"])
        user = json.loads(values["user"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(401, "Telegram authentication payload is invalid") from exc

    # Re-opening a very old signed payload must not create a reusable login.
    now = int(datetime.now(timezone.utc).timestamp())
    if now - auth_date > 86_400:
        raise HTTPException(401, "Telegram authentication has expired")
    return user
