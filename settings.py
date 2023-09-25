import os
from dotenv import load_dotenv

load_dotenv()

# Server Settings
DEFAULT_HOST = os.getenv("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("PORT", 8001))
DEFAULT_SERVER_BUFFER_LIMIT = int(os.getenv("BUFFER_LIMIT", 2**16))
DEFAULT_MSG_COUNT = int(os.getenv("MSG_COUNT", 20))
DEFAULT_MSG_LIMIT = int(os.getenv("MSG_LIMIT", 20))
DEFAULT_MSG_LIMIT_PERIOD_HOURS = int(os.getenv("MSG_LIMIT_PERIOD_HOURS", 1))
DEFAULT_BAN_PERIOD_HOURS = int(os.getenv("BAN_PERIOD_HOURS", 4))
DEFAULT_MAX_COMPLAINT_COUNT = int(os.getenv("MAX_COMPLAINT_COUNT", 3))
DEFAULT_MODERATION_CYCLE_SECS = int(os.getenv("MODERATION_CYCLE_SECS", 5))
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "Europe/Moscow")

# Database Settings
DEFAULT_MAX_CONNECTIONS = int(os.getenv("MAX_CONNECTIONS", 1))
DEFAULT_DB_CONNECTION_WAIT_SECS = float(os.getenv("DB_CONNECTION_WAIT_SECS", 0.001))
