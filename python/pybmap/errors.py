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


class BmapTimeoutError(BmapError):
    """Device did not respond in time."""


class BmapNotFoundError(BmapError):
    """No BMAP device found."""


class BmapDesyncError(BmapConnectionError):
    """A response carried a different address than the request.

    Seen after the headset drops and reconnects: responses queued before the
    drop are still in the socket, so each read returns the previous request's
    answer. Reopen the channel to clear it.
    """
