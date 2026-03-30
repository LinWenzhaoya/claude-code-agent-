"""
In-memory database layer for user management.
Simulates a simple user store with CRUD operations.
"""

from config import DATABASE

# In-memory user store (simulating a database)
_USERS = {
    "alice": {
        "username": "alice",
        "password_hash": "5d41402abc4b2a76b9719d911017c592",  # md5("hello")
        "role": "admin",
        "email": "alice@example.com",
        "active": True,
        "failed_attempts": 0,
        "profile": {"display_name": "Alice Admin", "department": "Engineering"},
    },
    "bob": {
        "username": "bob",
        "password_hash": "7d793037a0760186574b0282f2f435e7",  # md5("world")
        "role": "user",
        "email": "bob@example.com",
        "active": True,
        "failed_attempts": 0,
        "profile": {"display_name": "Bob User", "department": "Marketing"},
    },
    "charlie": {
        "username": "charlie",
        "password_hash": "e99a18c428cb38d5f260853678922e03",  # md5("abc123")
        "role": "user",
        "email": "charlie@example.com",
        "active": False,
        "failed_attempts": 3,
        "profile": {"display_name": "Charlie Inactive", "department": "Sales"},
    },
}

# Audit log store
_AUDIT_LOG = []


def get_user(username):
    """Look up a user by username. Returns user dict or None."""
    return _USERS.get(username)


def get_user_by_id(user_id):
    """Look up a user by their username (used as ID). Returns user dict or None."""
    return _USERS.get(user_id)


def get_all_active_users():
    """Return list of all active users."""
    return [u for u in _USERS.values() if u.get("active")]


def update_user_field(username, field, value):
    """Update a single field on a user record."""
    user = _USERS.get(username)
    if user is None:
        return False
    user[field] = value
    return True


def increment_failed_attempts(username):
    """Increment failed login attempts counter."""
    user = _USERS.get(username)
    if user:
        user["failed_attempts"] = user.get("failed_attempts", 0) + 1
        return user["failed_attempts"]
    return -1


def reset_failed_attempts(username):
    """Reset failed login attempts counter to zero."""
    return update_user_field(username, "failed_attempts", 0)


def add_audit_entry(action, username, detail=""):
    """Append an entry to the audit log."""
    entry = {
        "action": action,
        "username": username,
        "detail": detail,
    }
    _AUDIT_LOG.append(entry)
    return entry


def get_audit_log(username=None):
    """Retrieve audit log entries, optionally filtered by username."""
    if username:
        return [e for e in _AUDIT_LOG if e["username"] == username]
    return list(_AUDIT_LOG)


# --- Token store (session tokens) ---

_TOKEN_STORE = {}


def store_token(token_value, user_data):
    """Store a token in the in-memory token store for session tracking."""
    _TOKEN_STORE[token_value] = {
        "user": user_data,
        "created_at": None,  # would be timestamp in real system
    }
    return True


def lookup_token(token_value):
    """Look up a token in the store. Returns associated user data or None."""
    entry = _TOKEN_STORE.get(token_value)
    if entry is None:
        return None
    return entry.get("user")


def revoke_token(token_value):
    """Remove a token from the store (logout / invalidation)."""
    if token_value in _TOKEN_STORE:
        del _TOKEN_STORE[token_value]
        return True
    return False


def get_all_tokens():
    """Return all active tokens in the store."""
    return list(_TOKEN_STORE.keys())


def count_user_tokens(username):
    """Count how many active tokens a user has."""
    count = 0
    for token_value, entry in _TOKEN_STORE.items():
        user = entry.get("user", {})
        if user.get("username") == username:
            count += 1
    return count


def cleanup_expired_tokens(current_time):
    """Remove expired tokens from the token store."""
    expired_token_keys = []
    for token_value, entry in _TOKEN_STORE.items():
        token_created = entry.get("created_at")
        if token_created and current_time - token_created > 86400:
            expired_token_keys.append(token_value)
    for token_key in expired_token_keys:
        del _TOKEN_STORE[token_key]
    return len(expired_token_keys)
