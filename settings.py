import os

# Server Settings
DEFAULT_MSG_COUNT = os.getenv("MSG_COUNT") or 20
DEFAULT_MSG_LIMIT = os.getenv("MSG_LIMIT") or 20
DEFAULT_MSG_LIMIT_PERIOD_HOURS = os.getenv("MSG_LIMIT_PERIOD_HOURS") or 1
DEFAULT_BAN_PERIOD_HOURS = os.getenv("BAN_PERIOD_HOURS") or 4
DEFAULT_MAX_COMPLAINT_COUNT = os.getenv("MAX_COMPLAINT_COUNT") or 3
DEFAULT_MODERATION_CYCLE_SECS = os.getenv("MODERATION_CYCLE_SECS") or 5

# Database Settings
DEFAULT_MAX_CONNECTIONS = os.getenv("MAX_CONNECTIONS") or 1
