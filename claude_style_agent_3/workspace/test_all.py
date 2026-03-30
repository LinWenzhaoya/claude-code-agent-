"""
Test suite for the user management system.
Run with: python test_all.py
"""

import sys
import traceback

from utils import hash_password, verify_password, validate_username, validate_password
from db import get_user, get_all_active_users
from auth import login, check_permission
from routes import handle_login, handle_list_users, handle_get_profile


def test_hash_password():
    h = hash_password("hello")
    assert h == "5d41402abc4b2a76b9719d911017c592", f"Expected md5 of 'hello', got {h}"


def test_verify_password():
    assert verify_password("hello", "5d41402abc4b2a76b9719d911017c592")
    assert not verify_password("wrong", "5d41402abc4b2a76b9719d911017c592")


def test_validate_username():
    ok, _ = validate_username("alice")
    assert ok, "alice should be valid"
    ok, _ = validate_username("ab")
    assert not ok, "2-char username should be invalid"
    ok, _ = validate_username("valid_user_123")
    assert ok, "alphanumeric with underscore should be valid"


def test_validate_password():
    ok, _ = validate_password("short")
    assert not ok, "Short password should be invalid"
    ok, _ = validate_password("longpassword!")
    assert ok, "Long password with special char should be valid"


def test_get_user():
    user = get_user("alice")
    assert user is not None, "alice should exist"
    assert user["role"] == "admin"
    assert user["active"] is True


def test_get_active_users():
    users = get_all_active_users()
    names = [u["username"] for u in users]
    assert "alice" in names, "alice should be active"
    assert "bob" in names, "bob should be active"
    assert "charlie" not in names, "charlie should not be active"


def test_login_success():
    result = login("alice", "hello")
    assert isinstance(result, str), f"Expected string, got {type(result)}"
    assert result.startswith("Bearer "), f"Expected bearer token, got: {result}"


def test_login_wrong_password():
    result = login("alice", "wrongpass")
    assert result.startswith("ERROR:"), f"Expected error, got: {result}"


def test_login_inactive_user():
    result = login("charlie", "abc123")
    assert result.startswith("ERROR:"), f"Expected error for inactive user, got: {result}"


def test_login_nonexistent():
    result = login("nobody", "whatever")
    assert result.startswith("ERROR:"), f"Expected error for nonexistent user, got: {result}"


def test_check_permission():
    admin = get_user("alice")
    regular = get_user("bob")
    assert check_permission(admin, "admin"), "Alice should have admin permission"
    assert not check_permission(regular, "admin"), "Bob should not have admin permission"
    assert check_permission(regular, "user"), "Bob should have user permission"


def test_handle_login_route():
    response = handle_login({"username": "alice", "password": "hello"})
    assert response["status"] == 200, f"Expected 200, got {response['status']}"
    assert "token" in response["body"], "Response should contain token"


def test_handle_login_bad_password():
    response = handle_login({"username": "alice", "password": "wrong"})
    assert response["status"] == 401, f"Expected 401, got {response['status']}"


def test_handle_list_users():
    response = handle_list_users({"authenticated_user": "alice"})
    assert response["status"] == 200, f"Expected 200, got {response['status']}"
    assert response["body"]["count"] >= 2, "Should have at least 2 active users"


def test_handle_list_users_no_auth():
    response = handle_list_users({})
    assert response["status"] == 401


def test_handle_get_profile():
    response = handle_get_profile({"username": "bob"})
    assert response["status"] == 200
    assert response["body"]["role"] == "user"


# --------------- Test runner ---------------

ALL_TESTS = [
    test_hash_password,
    test_verify_password,
    test_validate_username,
    test_validate_password,
    test_get_user,
    test_get_active_users,
    test_login_success,
    test_login_wrong_password,
    test_login_inactive_user,
    test_login_nonexistent,
    test_check_permission,
    test_handle_login_route,
    test_handle_login_bad_password,
    test_handle_list_users,
    test_handle_list_users_no_auth,
    test_handle_get_profile,
]


def main():
    passed = 0
    failed = 0
    errors = []

    for test_fn in ALL_TESTS:
        name = test_fn.__name__
        try:
            test_fn()
            passed += 1
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            tb = traceback.format_exc()
            errors.append((name, tb))
            print(f"  FAIL  {name}: {e}")

    print(f"\nResults: {passed} passed, {failed} failed, {passed + failed} total")

    if errors:
        print("\n--- Failure details ---")
        for name, tb in errors:
            print(f"\n{name}:\n{tb}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
