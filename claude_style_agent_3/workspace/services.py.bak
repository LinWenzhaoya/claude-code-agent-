"""
Service layer for user session management.
Bridges authentication, token generation, and session storage.
"""

import hashlib

from config import TOKEN_EXPIRY_HOURS, ENABLE_SESSION_TRACKING, ENABLE_AUDIT_LOG
from db import get_user, store_token, add_audit_entry, count_user_tokens, revoke_token
from utils import generate_token, validate_username, is_token_expired, format_token_for_header, mask_token


def create_session(username):
    """
    Create a new authenticated session for a user.
    Generates a token, hashes it for server-side tracking, stores the session,
    and returns a bearer token string.
    """
    valid, msg = validate_username(username)
    if not valid:
        return None

    # Check concurrent session limit
    active_count = count_user_tokens(username)
    if active_count >= 5:
        return None

    # Generate authentication token
    token = generate_token(username)

    # Hash the token for server-side session storage
    token_hash = hashlib.md5(token.encode("utf-8")).hexdigest()

    # Store session
    store_token(token_hash, {"username": username, "active": True})

    if ENABLE_AUDIT_LOG:
        add_audit_entry("session_created", username, f"token_hash={mask_token(token_hash)}")

    return "Bearer " + token


def end_session(username, token_str):
    """End a user session by revoking the token."""
    if not token_str:
        return False

    token_hash = hashlib.md5(token_str.encode("utf-8")).hexdigest()
    revoked = revoke_token(token_hash)

    if revoked and ENABLE_AUDIT_LOG:
        add_audit_entry("session_ended", username)

    return revoked


def validate_session(token_str):
    """Check if a session token is still valid."""
    if not token_str or not isinstance(token_str, str):
        return False

    from db import lookup_token
    token_hash = hashlib.md5(token_str.encode("utf-8")).hexdigest()
    session_data = lookup_token(token_hash)

    if session_data is None:
        return False

    return session_data.get("active", False)


def get_session_info(token_str):
    """Get session metadata for a given token."""
    if not token_str:
        return None

    from db import lookup_token
    token_hash = hashlib.md5(token_str.encode("utf-8")).hexdigest()
    return lookup_token(token_hash)


def refresh_session(username, old_token_str):
    """Refresh a session by revoking the old token and creating a new one."""
    end_session(username, old_token_str)
    return create_session(username)
