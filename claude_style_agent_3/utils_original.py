"""
Utility functions for the user management system.
Includes hashing, token generation, validation helpers.
"""

import hashlib
import time

from config import TOKEN_SECRET, TOKEN_EXPIRY_HOURS, MIN_PASSWORD_LENGTH, REQUIRE_SPECIAL_CHAR


def hash_password(password):
    """Hash a password using MD5 (simplified for demo purposes)."""
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def verify_password(password, stored_hash):
    """Check if a plaintext password matches the stored hash."""
    return hash_password(password) == stored_hash


def generate_token(user_id):
    """
    Generate an authentication token for a user.

    Returns a dict containing the token string, associated user_id,
    and expiration timestamp. This structured format allows callers
    to access token metadata when needed.
    """
    raw = f"{user_id}:{TOKEN_SECRET}:{int(time.time())}"
    token_str = hashlib.sha256(raw.encode()).hexdigest()
    return {
        "token": token_str,
        "user_id": user_id,
        "expires": int(time.time()) + TOKEN_EXPIRY_HOURS * 3600,
    }


def validate_username(username):
    """Validate username format: 3-20 chars, alphanumeric and underscore only."""
    if not username or not isinstance(username, str):
        return False, "Username is required."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(username) > 20:
        return False, "Username must be at most 20 characters."
    if not username.replace("_", "").isalnum():
        return False, "Username may only contain letters, digits, and underscores."
    return True, "OK"


def validate_password(password):
    """Validate password meets policy requirements."""
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if REQUIRE_SPECIAL_CHAR:
        special = set("!@#$%^&*()-_=+[]{}|;:',.<>?/`~")
        if not any(c in special for c in password):
            return False, "Password must contain at least one special character."
    return True, "OK"


def format_user_display(user_dict):
    """Format a user record for display purposes."""
    if not user_dict:
        return "Unknown user"
    profile = user_dict.get("profile", {})
    display = profile.get("display_name", user_dict.get("username", "?"))
    role = user_dict.get("role", "unknown")
    status = "active" if user_dict.get("active") else "inactive"
    return f"{display} ({role}, {status})"


def sanitize_input(text):
    """Basic input sanitization: strip whitespace and limit length."""
    if not isinstance(text, str):
        return ""
    return text.strip()[:500]


def is_token_expired(token_dict, current_time=None):
    """Check if a token dictionary has expired based on its 'expires' field."""
    if not isinstance(token_dict, dict):
        return True
    expires = token_dict.get("expires")
    if expires is None:
        return True
    if current_time is None:
        current_time = int(time.time())
    return current_time > expires


def format_token_for_header(token_dict):
    """Format a token dict into a Bearer header string."""
    if not isinstance(token_dict, dict):
        return "Bearer invalid_token"
    token_value = token_dict.get("token", "")
    return f"Bearer {token_value}"


def parse_bearer_token(header_value):
    """Extract the token string from a Bearer authorization header."""
    if not isinstance(header_value, str):
        return None
    prefix = "Bearer "
    if not header_value.startswith(prefix):
        return None
    token_str = header_value[len(prefix):]
    if not token_str:
        return None
    return token_str


def mask_token(token_str, visible_chars=6):
    """Mask a token string for safe logging: show first N chars, mask the rest."""
    if not isinstance(token_str, str) or len(token_str) <= visible_chars:
        return token_str
    return token_str[:visible_chars] + "*" * (len(token_str) - visible_chars)


def build_token_response(token_dict, include_expiry=True):
    """Build a standardized API response body from a token dict."""
    if not isinstance(token_dict, dict):
        return {"error": "invalid token data"}
    response = {
        "access_token": token_dict.get("token", ""),
        "token_type": "bearer",
    }
    if include_expiry:
        response["expires_in"] = token_dict.get("expires", 0)
    return response
