class FromDocStringRuntimeError(RuntimeError):

    def __init__(self):
        super().__init__(self.__doc__)


class NotConnectedError(FromDocStringRuntimeError):
    """Operation is rejected because no established connection found"""


class NotExistError(FromDocStringRuntimeError):
    """Requested object is not present in database"""


class MsgLimitExceededError(FromDocStringRuntimeError):
    """Message limit is achieved. Please try again later."""


class BannedError(FromDocStringRuntimeError):
    """You have been banned. Please try again later."""


class MaxMembersError(FromDocStringRuntimeError):
    """Max member count is exceeded."""


class ValidationError(RuntimeError):
    pass
