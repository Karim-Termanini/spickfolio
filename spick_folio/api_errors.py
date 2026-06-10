class DownloadError(Exception):
    """Raised when a download job fails with a stable client-localizable code."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)
