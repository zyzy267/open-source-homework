class InvalidSchema(RequestException, ValueError):
    """The URL scheme provided is either invalid or unsupported."""