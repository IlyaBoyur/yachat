class NotConnectedError(RuntimeError):
    """Operation is rejected because no established connection found"""
    pass


class NotExistError(RuntimeError):
    """Requested object is not present in database"""
    pass


class MsgLimitExceededError(RuntimeError):
    """Message limit is achieved. Please try again later."""
    pass
