class NoSendingError(Exception):
    pass


class StatusException(Exception):
    pass


class NotTokenException(NoSendingError):
    pass


class SendMessageException(NoSendingError):
    pass
