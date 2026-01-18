class MissingSchema(RequestException, ValueError):
    """The URL scheme (e.g. http or https) is missing."""