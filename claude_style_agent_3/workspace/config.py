"""
Application configuration for the user management system.
"""

APP_NAME = "UserManager"
APP_VERSION = "2.1.0"

# Database settings
DATABASE = {
    "host": "localhost",
    "port": 5432,
    "name": "user_mgmt",
    "user": "admin",
    "password": "changeme",
}

# Authentication settings
TOKEN_SECRET = "super-secret-key-2024"
TOKEN_EXPIRY_HOURS = 24
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 30

# Password policy
MIN_PASSWORD_LENGTH = 8
REQUIRE_SPECIAL_CHAR = True

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Rate limiting
RATE_LIMIT_PER_MINUTE = 60
RATE_LIMIT_BURST = 10

# Feature flags
ENABLE_TWO_FACTOR = False
ENABLE_AUDIT_LOG = True
ENABLE_SESSION_TRACKING = True
