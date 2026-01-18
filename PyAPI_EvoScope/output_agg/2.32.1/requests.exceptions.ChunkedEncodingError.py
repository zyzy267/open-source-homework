class ChunkedEncodingError(RequestException):
    """The server declared chunked encoding but sent an invalid chunk."""