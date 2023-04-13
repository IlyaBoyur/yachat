from enum import Enum


DEFAULT_DEPTH = 20
DEFAULT_MSG_LIMIT = 20
DEFAULT_MSG_LIMIT_PERIOD_HOURS = 1


class ChatType(str, Enum):
    COMMON = "common"
    PRIVATE = "private"
