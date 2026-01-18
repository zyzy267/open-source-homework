class InvalidHeader(RequestException, ValueError):
    """The header value provided was somehow invalid."""