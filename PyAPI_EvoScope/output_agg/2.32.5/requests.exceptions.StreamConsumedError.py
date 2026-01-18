class StreamConsumedError(RequestException, TypeError):
    """The content for this response was already consumed."""