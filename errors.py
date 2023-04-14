class NotConnectedError(RuntimeError):
    """Operation is rejected because no established connection found"""
    def __init__(self):
        super().__init__(self.__doc__)


class NotExistError(RuntimeError):
    """Requested object is not present in database"""
    def __init__(self):
        super().__init__(self.__doc__)


class MsgLimitExceededError(RuntimeError):
    """Message limit is achieved. Please try again later."""
    def __init__(self):
        super().__init__(self.__doc__)


class BannedError(RuntimeError):
    """You have been banned. Please try again later."""
    def __init__(self):
        super().__init__(self.__doc__)
