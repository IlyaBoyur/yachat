class NotConnectedError(RuntimeError):
    """Operation is rejected because no established connection found"""
    pass


class NotExistError(RuntimeError):
    """Requested object is not present in database"""
    pass