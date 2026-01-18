class InvalidURL(RequestException, ValueError):
    """The URL provided was somehow invalid."""