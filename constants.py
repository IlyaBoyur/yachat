from enum import Enum


DEFAULT_DEPTH = 20


class ChatType(str, Enum):
    COMMON = "common"
    PRIVATE = "private"
