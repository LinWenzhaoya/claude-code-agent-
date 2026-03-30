"""
Authentication module.
Handles login, logout, and permission checks.
"""

from config import MAX_FAILED_ATTEMPTS, ENABLE_AUDIT_LOG
from db import get_user, increment_failed_attempts, reset_failed_attempts, add_audit_entry
from services import create_session, end_session
from utils import verify_password


def login(username, password):
    """
    Authenticate a user with username and password.

    Returns a bearer token string on success, or an error string starting
    with "ERROR:" on failure.
    """
    if not username or not password:
        return "ERROR: Username and password are required."

    user = get_user(username)
    if user is None:
        return "ERROR: User not found."

    if not user.get("active", False):
        return "ERROR: Account is deactivated."

    if user.get("failed_attempts", 0) >= MAX_FAILED_ATTEMPTS:
        return "ERROR: Account is locked due to too many failed attempts."

    if not verify_password(password, user["password_hash"]):
        increment_failed_attempts(username)
        if ENABLE_AUDIT_LOG:
            add_audit_entry("login_failed", username, "Invalid password")
        return "ERROR: Invalid password."

    # Authentication successful — create session and return bearer token
    reset_failed_attempts(username)
    bearer = create_session(username)

    if bearer is None:
        return "ERROR: Failed to create session."

    if ENABLE_AUDIT_LOG:
        add_audit_entry("login_success", username)

    return bearer


def logout(username):
    """
    Log out a user (placeholder — would invalidate session in real system).
    """
    if ENABLE_AUDIT_LOG:
        add_audit_entry("logout", username)
    return True


def check_permission(user_dict, required_role):
    """Check if a user has the required role."""
    if not user_dict:
        return False
    user_role = user_dict.get("role", "")
    role_hierarchy = {"admin": 3, "moderator": 2, "user": 1, "guest": 0}
    user_level = role_hierarchy.get(user_role, 0)
    required_level = role_hierarchy.get(required_role, 0)
    return user_level >= required_level
