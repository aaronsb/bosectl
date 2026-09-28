"""Exception types for BMAP protocol errors."""


class BmapError(Exception):
    """Base exception for all BMAP errors."""


class BmapConnectionError(BmapError):
    """Failed to connect to the device.

    ``errno`` carries the OS error code when the failure came from the
    socket connect (e.g. EBUSY, ECONNREFUSED), otherwise None.
    """

    def __init__(self, message, errno=None):
        super().__init__(message)
        self.errno = errno


class BmapBusyError(BmapConnectionError):
    """The device refused the channel as busy (EBUSY) even after retries.

    Seen when a new connection follows closely on the previous one: the
    headset is still tearing down the old RFCOMM link. Waiting a few
    seconds clears it; it is not a pairing or Bluetooth-off problem.
    """


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


class BmapDesyncError(BmapConnectionError):
    """A response carried a different address than the request.

    Seen after the headset drops and reconnects: responses queued before the
    drop are still in the socket, so each read returns the previous request's
    answer. Reopen the channel to clear it.
    """
