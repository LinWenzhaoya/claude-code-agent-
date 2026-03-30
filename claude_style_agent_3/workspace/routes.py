"""
Route handlers for the user management API.
Each handler simulates processing an HTTP-like request.
"""

from auth import login, logout, check_permission
from db import get_user, get_all_active_users
from utils import format_user_display, validate_username, sanitize_input


def handle_login(request):
    """
    Handle a login request.
    request: dict with 'username' and 'password' keys.
    Returns: dict with 'status' and 'body'.
    """
    username = sanitize_input(request.get("username", ""))
    password = request.get("password", "")

    result = login(username, password)

    if result.startswith("ERROR:"):
        return {
            "status": 401,
            "body": {"error": result.replace("ERROR: ", "")},
        }

    return {
        "status": 200,
        "body": {"token": result},
    }


def handle_logout(request):
    """Handle a logout request."""
    username = sanitize_input(request.get("username", ""))
    if not username:
        return {"status": 400, "body": {"error": "Username required."}}

    logout(username)
    return {"status": 200, "body": {"message": "Logged out successfully."}}


def handle_list_users(request):
    """
    Handle a request to list all active users.
    Requires admin role.
    """
    requesting_user = request.get("authenticated_user")
    if not requesting_user:
        return {"status": 401, "body": {"error": "Not authenticated."}}

    user_data = get_user(requesting_user)
    if not check_permission(user_data, "admin"):
        return {"status": 403, "body": {"error": "Admin role required."}}

    users = get_all_active_users()
    user_list = [format_user_display(u) for u in users]
    return {
        "status": 200,
        "body": {"users": user_list, "count": len(user_list)},
    }


def handle_get_profile(request):
    """Handle a request to get a user's profile."""
    username = sanitize_input(request.get("username", ""))

    valid, msg = validate_username(username)
    if not valid:
        return {"status": 400, "body": {"error": msg}}

    user = get_user(username)
    if not user:
        return {"status": 404, "body": {"error": "User not found."}}

    return {
        "status": 200,
        "body": {
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "profile": user.get("profile", {}),
            "display": format_user_display(user),
        },
    }
