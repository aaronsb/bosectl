"""RFCOMM Bluetooth socket transport for BMAP devices."""

import sys
import time
from .errors import BmapConnectionError, BmapTimeoutError

RFCOMM_CHANNEL = 2  # BMAP protocol is always on RFCOMM channel 2


if sys.platform == "darwin":
    import objc
    from IOBluetooth import (
        IOBluetoothDevice,
        IOBluetoothRFCOMMChannel,
        NSObject,
    )
    from Foundation import NSRunLoop, NSDate, NSDefaultRunLoopMode
    from queue import Queue
    from threading import Event

    # Register metadata for openRFCOMMChannelSync to make sure out parameters are handled correctly
    objc.registerMetaDataForSelector(
        b"IOBluetoothDevice",
        b"openRFCOMMChannelSync:withChannelID:delegate:",
        dict(
            arguments={
                2: dict(type=objc._C_PTR + objc._C_ID, type_modifier=objc._C_OUT),
                3: dict(type=objc._C_USHT), # Channel ID
                4: dict(type=objc._C_ID)    # Delegate
            }
        )
    )

    class MacOsRfcommDelegate(NSObject):
        def init(self):
            self = objc.super(MacOsRfcommDelegate, self).init()
            if self is None:
                return None
            self.baseband_connected = False
            self.baseband_status = -1
            self.baseband_event = Event()

            self.channel_connected = False
            self.channel_status = -1
            self.channel_event = Event()

            self.received_queue = Queue()
            self.closed_event = Event()
            return self

        def connectionComplete_status_(self, device, status):
            self.baseband_status = status
            self.baseband_connected = (status == 0)
            self.baseband_event.set()

        def rfcommChannelOpenComplete_status_(self, channel, status):
            self.channel_status = status
            self.channel_connected = (status == 0)
            self.channel_event.set()

        @objc.typedSelector(b"v@:@^vQ")
        def rfcommChannelData_data_length_(self, channel, data_ptr, length):
            try:
                # Convert objc.varlist to python bytes
                chunk = bytes(data_ptr.as_buffer(length))
                self.received_queue.put(chunk)
            except Exception:
                try:
                    chunk = bytes(data_ptr[:length])
                    self.received_queue.put(chunk)
                except Exception:
                    pass

        def rfcommChannelClosed_(self, channel):
            self.closed_event.set()


    class MacOsRfcommTransport:
        """Raw RFCOMM Bluetooth IOBluetooth transport for macOS."""

        def __init__(self, mac, channel=RFCOMM_CHANNEL, timeout=3.0):
            self.mac = mac
            self.channel_id = channel
            self.timeout = timeout
            self.device = None
            self.channel = None
            self.delegate = None

        def connect(self):
            """Open the RFCOMM channel using native IOBluetooth."""
            try:
                self.device = IOBluetoothDevice.deviceWithAddressString_(self.mac)
                if not self.device:
                    raise BmapConnectionError("Device not found: %s" % self.mac)

                self.delegate = MacOsRfcommDelegate.alloc().init()
                run_loop = NSRunLoop.currentRunLoop()

                # 1. Query SDP first so macOS registers active Bluetooth services
                self.device.performSDPQuery_(None)
                start_sdp = time.time()
                while time.time() - start_sdp < 1.5:
                    run_loop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.05))

                # 2. Establish baseband connection asynchronously
                status = self.device.openConnection_(self.delegate)
                if status != 0:
                    raise BmapConnectionError("Failed to issue openConnection (status %d)" % status)

                # Wait up to 5 seconds for baseband connection to establish
                start_bb = time.time()
                while time.time() - start_bb < 5.0 and not self.delegate.baseband_event.is_set():
                    run_loop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.05))

                if not self.delegate.baseband_connected:
                    raise BmapConnectionError(
                        "Failed to establish baseband connection (status %d)" % self.delegate.baseband_status
                    )

                # 3. Open RFCOMM channel directly on the requested channel ID
                status, channel = self.device.openRFCOMMChannelSync_withChannelID_delegate_(
                    None, self.channel_id, self.delegate
                )
                if status != 0:
                    raise BmapConnectionError("Failed to open RFCOMM channel %d (status %d)" % (self.channel_id, status))

                # Wait for channel open complete
                start_ch = time.time()
                while time.time() - start_ch < 3.0 and not self.delegate.channel_event.is_set():
                    run_loop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.05))

                if not self.delegate.channel_connected:
                    raise BmapConnectionError("RFCOMM channel open failed (status %d)" % self.delegate.channel_status)

                self.channel = channel

                # 4. Flush any startup handshake/broadcast packets
                time.sleep(0.5)
                while not self.delegate.received_queue.empty():
                    try:
                        self.delegate.received_queue.get_nowait()
                    except Exception:
                        break
            except Exception as e:
                self.close()
                if isinstance(e, BmapConnectionError):
                    raise
                raise BmapConnectionError("Failed to connect to %s: %s" % (self.mac, e)) from e

        def close(self):
            """Close the channel."""
            if self.channel:
                try:
                    self.channel.closeChannel()
                except Exception:
                    pass
                self.channel = None
            self.device = None
            self.delegate = None

        def send_recv(self, packet, drain=False):
            """Send a BMAP packet and receive the response using NSRunLoop."""
            if not self.channel:
                raise BmapConnectionError("Not connected")

            # Clear delegate queue before sending
            while not self.delegate.received_queue.empty():
                try:
                    self.delegate.received_queue.get_nowait()
                except Exception:
                    break

            # Send
            # writeSync:length:
            status = self.channel.writeSync_length_(packet, len(packet))
            if status != 0:
                raise BmapConnectionError("Write failed with status %d" % status)

            # Brief delay for device to process (similar to original transport)
            time.sleep(0.2)

            # Wait and receive
            data = b""
            start_time = time.time()
            run_loop = NSRunLoop.currentRunLoop()

            # Wait for first response
            while time.time() - start_time < self.timeout:
                run_loop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.01))

                if not self.delegate.received_queue.empty():
                    data += self.delegate.received_queue.get()
                    break

                if self.delegate.closed_event.is_set():
                    raise BmapConnectionError("Connection closed by peer")

            if not data:
                raise BmapTimeoutError("No response from device")

            # Drain if requested
            if drain:
                drain_timeout = 0.5
                start_drain = time.time()
                while time.time() - start_drain < drain_timeout:
                    run_loop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.01))
                    if not self.delegate.received_queue.empty():
                        data += self.delegate.received_queue.get()
                        start_drain = time.time()  # reset drain timeout
                    if self.delegate.closed_event.is_set():
                        break

            return data

        def __enter__(self):
            self.connect()
            return self

        def __exit__(self, *exc):
            self.close()

else:
    import socket

    class LinuxRfcommTransport:
        """Raw RFCOMM Bluetooth socket transport for Linux."""

        def __init__(self, mac, channel=RFCOMM_CHANNEL, timeout=3.0):
            self.mac = mac
            self.channel = channel
            self.timeout = timeout
            self._sock = None

        def connect(self):
            """Open the RFCOMM socket to the device."""
            try:
                self._sock = socket.socket(
                    socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
                )
                self._sock.settimeout(self.timeout)
                self._sock.connect((self.mac, self.channel))
            except (OSError, socket.error) as e:
                self._sock = None
                raise BmapConnectionError(
                    "Failed to connect to %s: %s" % (self.mac, e)
                ) from e

        def close(self):
            """Close the socket."""
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None

        # Upper bound on chunks discarded before a send, so a device that
        # streams notifications cannot stall the request.
        _MAX_STALE_CHUNKS = 64

        def _discard_pending(self):
            """Drop bytes already waiting on the socket before a new request.

            Late replies and unsolicited STATUS notifications would otherwise
            be read as the answer to the next request. Mirrors the queue
            clear in the macOS transport.
            """
            try:
                self._sock.settimeout(0)
                for _ in range(self._MAX_STALE_CHUNKS):
                    if not self._sock.recv(4096):
                        break  # peer closed; the send will report it
            except (BlockingIOError, InterruptedError, socket.timeout):
                pass
            except OSError:
                pass  # a dead socket fails the send with a clear error
            finally:
                self._sock.settimeout(self.timeout)

        def send_recv(self, packet, drain=False):
            if not self._sock:
                raise BmapConnectionError("Not connected")
            self._discard_pending()
            try:
                self._sock.send(packet)
                time.sleep(0.2)
                data = self._sock.recv(4096)
            except socket.timeout:
                raise BmapTimeoutError("No response from device")
            except OSError as e:
                raise BmapConnectionError("Communication error: %s" % e) from e

            if drain:
                self._sock.settimeout(0.5)
                try:
                    while True:
                        more = self._sock.recv(4096)
                        if not more:
                            break
                        data += more
                except (socket.timeout, BlockingIOError):
                    pass
                self._sock.settimeout(self.timeout)

            return data

        def __enter__(self):
            self.connect()
            return self

        def __exit__(self, *exc):
            self.close()


# Dynamically map RfcommTransport based on OS
RfcommTransport = MacOsRfcommTransport if sys.platform == "darwin" else LinuxRfcommTransport
