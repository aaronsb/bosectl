"""Exception types for BMAP protocol errors."""


class BmapError(Exception):
    """Base exception for all BMAP errors."""


class BmapConnectionError(BmapError):
    """Failed to connect to the device."""


class BmapAuthError(BmapError):
    """Operation requires authentication."""


class BmapDeviceError(BmapError):
    """Device returned an error response."""

    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code


class BmapInvalidArgError(BmapError):
    """Caller supplied invalid or incomplete arguments."""


class BmapTimeoutError(BmapError):
    """Device did not respond in time."""


class BmapNotFoundError(BmapError):
    """No BMAP device found."""
