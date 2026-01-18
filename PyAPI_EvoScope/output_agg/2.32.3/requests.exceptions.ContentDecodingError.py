class ContentDecodingError(RequestException, BaseHTTPError):
    """Failed to decode response content."""