class PriceNotFoundError(BaseException):
    """Could not find the requested commodity price."""
    pass


class BadDataError(BaseException):
    """The data given is incorrect or malformed."""
    pass
